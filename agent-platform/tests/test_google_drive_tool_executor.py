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
        if tool_name == "docs_create_with_text":
            return self._text(
                {
                    "documentId": "generated-doc",
                    "title": arguments["title"],
                    "characterCount": len(arguments["text"]),
                    "destinationFolderId": arguments.get("destinationFolderId"),
                }
            )
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



class FakeArtifactService:
    async def get(self, artifact_id):
        return type(
            "ArtifactValue",
            (),
            {
                "id": artifact_id,
                "artifact_type": "FINAL_DELIVERABLE",
                "title": "Final RFP response",
                "content": {"markdown": "# Final response\n\nApproved content."},
                "ref": lambda self: {
                    "artifactId": str(self.id),
                    "type": self.artifact_type,
                    "title": self.title,
                },
            },
        )()


def artifact_writer_tool() -> Tool:
    return Tool(
        id=uuid4(),
        name="google-docs-create-from-artifact",
        description="write artifact",
        instructions="",
        implementation_type="GOOGLE_DOCS_ARTIFACT_WRITE",
        configuration={"server": "google-workspace"},
        input_schema={"type": "object"},
        side_effect="WRITE",
        approval_policy="REQUIRED",
    )


@pytest.mark.asyncio
async def test_google_docs_writer_materializes_artifact_without_text_argument(tmp_path: Path):
    client = FakeMcpClient(tmp_path, metadata={})
    executor = InfrastructureToolExecutor(
        FakeRepository(server()),
        client,
        artifact_service=FakeArtifactService(),
        mcp_workspace_root=str(tmp_path / "workspace"),
    )
    artifact_id = str(uuid4())

    result = await executor.execute(
        artifact_writer_tool(),
        {
            "artifactId": artifact_id,
            "destinationFolderId": "folder-1",
        },
    )

    assert result["implementation"] == "GOOGLE_DOCS_ARTIFACT_WRITE"
    assert result["artifact"]["artifactId"] == artifact_id
    assert client.calls == [
        (
            "docs_create_with_text",
            {
                "title": "Final RFP response",
                "text": "# Final response\n\nApproved content.",
                "destinationFolderId": "folder-1",
            },
        )
    ]
