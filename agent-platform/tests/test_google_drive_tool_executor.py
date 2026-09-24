import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.tool import McpServer, Tool
from app.infrastructure.externalservices.mcp.tool_executor import InfrastructureToolExecutor


class FakeRepository:
    def __init__(self, server: McpServer):
        self.server = server

    async def get_mcp_server_by_name(self, name: str):
        return self.server if name == self.server.name else None


class FakeMcpClient:
    def __init__(self, root: Path, *, metadata: dict, native_output: dict | None = None):
        self.root = root
        self.metadata = metadata
        self.native_output = native_output
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, server, tool_name: str, arguments: dict):
        self.calls.append((tool_name, arguments))
        if tool_name == "drive_get_file":
            return self._text(self.metadata)
        if tool_name in {"docs_get_text", "sheets_get_text", "slides_get_text"}:
            return self._text(self.native_output or {})
        if tool_name == "drive_download_file":
            output = self.root / arguments["outputPath"]
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                "Customer requests a six month migration and stronger observability.",
                encoding="utf-8",
            )
            return self._text(
                {
                    "fileId": arguments["fileId"],
                    "outputPath": arguments["outputPath"],
                }
            )
        raise AssertionError(f"Unexpected MCP call: {tool_name}")

    @staticmethod
    def _text(value: dict):
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(value),
                }
            ]
        }


def server() -> McpServer:
    return McpServer(
        id=uuid4(),
        name="google-workspace",
        description="test",
        command="node",
        args=[],
        cwd=None,
        environment={},
        enabled=True,
        source="TEST",
    )


def tool() -> Tool:
    return Tool(
        id=uuid4(),
        name="google-drive-read-file",
        description="read drive",
        instructions="",
        implementation_type="GOOGLE_DRIVE_READ",
        configuration={"server": "google-workspace"},
        input_schema={
            "type": "object",
            "properties": {"fileId": {"type": "string"}},
            "required": ["fileId"],
        },
    )


@pytest.mark.asyncio
async def test_google_drive_reader_uses_native_docs_reader(tmp_path: Path):
    workspace = tmp_path / "workspace"
    client = FakeMcpClient(
        tmp_path,
        metadata={
            "id": "doc-1",
            "name": "RFP",
            "mimeType": "application/vnd.google-apps.document",
        },
        native_output={
            "documentId": "doc-1",
            "title": "RFP",
            "text": "Customer needs a migration.",
            "characterCount": 27,
        },
    )
    executor = InfrastructureToolExecutor(
        FakeRepository(server()),
        client,
        mcp_workspace_root=str(workspace),
    )

    result = await executor.execute(tool(), {"fileId": "doc-1"})

    assert result["reader"] == "docs_get_text"
    assert result["output"]["text"] == "Customer needs a migration."
    assert [name for name, _ in client.calls] == [
        "drive_get_file",
        "docs_get_text",
    ]


@pytest.mark.asyncio
async def test_google_drive_reader_downloads_parses_and_cleans_binary(tmp_path: Path):
    workspace = tmp_path / "workspace"
    client = FakeMcpClient(
        tmp_path,
        metadata={
            "id": "file-1",
            "name": "requirements.txt",
            "mimeType": "text/plain",
        },
    )
    executor = InfrastructureToolExecutor(
        FakeRepository(server()),
        client,
        mcp_workspace_root=str(workspace),
    )

    result = await executor.execute(tool(), {"fileId": "file-1"})

    assert result["reader"] == "drive_download_file+DocumentParser"
    assert "six month migration" in result["output"]["text"]
    assert result["output"]["characterCount"] > 0
    assert [name for name, _ in client.calls] == [
        "drive_get_file",
        "drive_download_file",
    ]
    assert not (workspace / "google-drive-reader").exists() or not any(
        (workspace / "google-drive-reader").iterdir()
    )
