import os

import pytest

from app.domain.tool import McpServer
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_google_workspace_mcp_exposes_expected_read_tools() -> None:
    if os.getenv("RUN_GOOGLE_WORKSPACE_MCP_INTEGRATION") != "1":
        pytest.skip(
            "Set RUN_GOOGLE_WORKSPACE_MCP_INTEGRATION=1 to run the real MCP smoke test"
        )

    server = McpServer(
        id=__import__("uuid").uuid4(),
        name="google-workspace",
        description="Google Workspace MCP",
        command="node",
        args=["/opt/mcp/google-workspace/dist/server.js"],
        cwd="/opt/mcp/google-workspace",
        environment={
            "GOOGLE_OAUTH_CREDENTIALS": "/run/secrets/google/google-oauth-credentials.json",
            "GOOGLE_OAUTH_TOKEN": "/run/secrets/google/google-token.json",
        },
        enabled=True,
        source="TEST",
    )
    client = McpStdioClient(timeout_seconds=30)

    tools = {item.get("name") for item in await client.list_tools(server)}

    assert {
        "drive_search_files",
        "drive_list_folder",
        "drive_get_file",
        "drive_download_file",
        "drive_export_file",
        "docs_get_text",
        "docs_create_with_text",
        "sheets_get_text",
        "slides_get_text",
    }.issubset(tools)
