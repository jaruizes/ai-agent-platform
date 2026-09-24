import json
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.business.ports import ToolRepositoryPort
from app.domain.tool import Tool
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient
from app.infrastructure.knowledge.parsers import DocumentParser


class InfrastructureToolExecutor:
    GOOGLE_NATIVE_READERS = {
        "application/vnd.google-apps.document": ("docs_get_text", "documentId"),
        "application/vnd.google-apps.spreadsheet": ("sheets_get_text", "spreadsheetId"),
        "application/vnd.google-apps.presentation": ("slides_get_text", "presentationId"),
    }

    def __init__(
        self,
        repository: ToolRepositoryPort,
        mcp_client: McpStdioClient,
        parser: DocumentParser | None = None,
        *,
        mcp_workspace_root: str = "/opt/workspace",
    ):
        self._repository = repository
        self._mcp_client = mcp_client
        self._parser = parser or DocumentParser()
        self._mcp_workspace_root = Path(mcp_workspace_root).resolve()

    async def execute(self, tool: Tool, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool.implementation_type == "MCP":
            return await self._execute_mcp(tool, arguments)
        if tool.implementation_type == "GOOGLE_DRIVE_READ":
            return await self._execute_google_drive_read(tool, arguments)
        raise NotImplementedError(
            f"Tool implementation type '{tool.implementation_type}' is not supported yet"
        )

    async def _execute_mcp(self, tool: Tool, arguments: dict[str, Any]) -> dict[str, Any]:
        server_name = tool.configuration["server"]
        remote_tool_name = tool.configuration["tool"]
        server = await self._repository.get_mcp_server_by_name(server_name)
        if not server:
            raise LookupError(f"MCP server '{server_name}' does not exist")

        raw = await self._mcp_client.call_tool(server, remote_tool_name, arguments)
        return {
            "implementation": "MCP",
            "server": server.name,
            "tool": remote_tool_name,
            "output": self._normalize_mcp_result(raw),
        }

    async def _execute_google_drive_read(
        self,
        tool: Tool,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        server_name = str(tool.configuration.get("server") or "")
        if not server_name:
            raise ValueError("GOOGLE_DRIVE_READ tool requires configuration.server")
        server = await self._repository.get_mcp_server_by_name(server_name)
        if not server:
            raise LookupError(f"MCP server '{server_name}' does not exist")

        file_id = str(arguments.get("fileId") or "").strip()
        if not file_id:
            raise ValueError("fileId is required")

        metadata_raw = await self._mcp_client.call_tool(
            server,
            "drive_get_file",
            {"fileId": file_id},
        )
        metadata = self._normalize_mcp_result(metadata_raw)
        if not isinstance(metadata, dict):
            raise RuntimeError("Google Drive MCP returned invalid file metadata")

        mime_type = str(metadata.get("mimeType") or "")
        name = str(metadata.get("name") or file_id)

        if mime_type == "application/vnd.google-apps.folder":
            raise ValueError(
                f"'{name}' is a Google Drive folder; use google-drive-list-folder"
            )

        native_reader = self.GOOGLE_NATIVE_READERS.get(mime_type)
        if native_reader:
            remote_tool, id_argument = native_reader
            raw = await self._mcp_client.call_tool(
                server,
                remote_tool,
                {id_argument: file_id},
            )
            output = self._normalize_mcp_result(raw)
            return {
                "implementation": "GOOGLE_DRIVE_READ",
                "server": server.name,
                "reader": remote_tool,
                "file": metadata,
                "output": output,
            }

        if mime_type.startswith("application/vnd.google-apps."):
            raise ValueError(
                f"Google-native Drive type '{mime_type}' is not supported for "
                f"semantic reading yet: {name}"
            )

        safe_name = self._safe_filename(name)
        workspace_id = uuid4().hex
        relative_output = f"workspace/google-drive-reader/{workspace_id}/{safe_name}"
        local_directory = self._mcp_workspace_root / "google-drive-reader" / workspace_id
        local_path = local_directory / safe_name

        if local_path.resolve() != local_path or not local_path.resolve().is_relative_to(
            self._mcp_workspace_root
        ):
            raise RuntimeError("Refusing to read a Drive download outside MCP workspace")

        try:
            await self._mcp_client.call_tool(
                server,
                "drive_download_file",
                {
                    "fileId": file_id,
                    "outputPath": relative_output,
                    "overwrite": False,
                },
            )
            if not local_path.exists():
                raise RuntimeError(
                    "Google Drive MCP reported a download but the file is not "
                    f"available at {local_path}"
                )

            parsed = self._parser.parse(
                str(local_path),
                name=name,
                mime_type=mime_type or None,
            )
            text = self._parsed_text(parsed)
            return {
                "implementation": "GOOGLE_DRIVE_READ",
                "server": server.name,
                "reader": "drive_download_file+DocumentParser",
                "file": metadata,
                "output": {
                    "fileId": file_id,
                    "name": name,
                    "mimeType": mime_type,
                    "title": parsed.title,
                    "text": text,
                    "characterCount": len(text),
                    "metadata": parsed.metadata,
                },
            }
        finally:
            shutil.rmtree(local_directory, ignore_errors=True)

    @staticmethod
    def _parsed_text(parsed: Any) -> str:
        parts: list[str] = []
        for segment in parsed.segments:
            value = str(segment.text or "").strip()
            if not value:
                continue
            metadata = segment.metadata or {}
            if metadata:
                label = ", ".join(
                    f"{key}={value}" for key, value in sorted(metadata.items())
                )
                parts.append(f"[{label}]\n{value}")
            else:
                parts.append(value)
        return "\n\n".join(parts)

    @staticmethod
    def _safe_filename(value: str) -> str:
        name = Path(value).name
        name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip()
        return name or "drive-file"

    @classmethod
    def _normalize_mcp_result(cls, result: dict[str, Any]) -> Any:
        structured = result.get("structuredContent")
        if structured is not None:
            return structured

        content = result.get("content") or []
        text_items = [
            item.get("text", "")
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        text_items = [item for item in text_items if item]

        if len(text_items) == 1:
            return cls._decode_text_payload(text_items[0])
        if text_items:
            return [cls._decode_text_payload(item) for item in text_items]

        return content

    @staticmethod
    def _decode_text_payload(value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
