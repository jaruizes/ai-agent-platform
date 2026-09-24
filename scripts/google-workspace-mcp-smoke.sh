#!/usr/bin/env bash
set -euo pipefail

TEST_FILE_ID="${GOOGLE_DRIVE_TEST_FILE_ID:-}"

echo "== Google Workspace MCP / Tool smoke test =="

echo "1/3 Google API authentication"
docker compose exec -T agent-platform \
  node /opt/mcp/google-workspace/dist/doctor.js

echo
echo "2/3 MCP tool discovery"
docker compose exec -T agent-platform python - <<'PY'
import asyncio
from uuid import uuid4

from app.domain.tool import McpServer
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient

server = McpServer(
    id=uuid4(),
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
    source="SMOKE",
)

expected = {
    "drive_search_files",
    "drive_list_folder",
    "drive_get_file",
    "drive_download_file",
    "drive_export_file",
    "docs_get_text",
    "sheets_get_text",
    "slides_get_text",
}

async def main():
    tools = await McpStdioClient(timeout_seconds=30).list_tools(server)
    names = {item.get("name") for item in tools}
    missing = expected - names
    if missing:
        raise SystemExit(f"Missing MCP tools: {sorted(missing)}")
    print("MCP tools OK:")
    for name in sorted(expected):
        print(f"  - {name}")

asyncio.run(main())
PY

if [[ -z "$TEST_FILE_ID" ]]; then
  echo
  echo "3/3 High-level reader skipped."
  echo "Set GOOGLE_DRIVE_TEST_FILE_ID to test google-drive-read-file with a real file."
  echo
  echo "Google Workspace MCP smoke test PASSED."
  exit 0
fi

echo
echo "3/3 High-level google-drive-read-file"
docker compose exec -T -e GOOGLE_DRIVE_TEST_FILE_ID="$TEST_FILE_ID" agent-platform python - <<'PY'
import asyncio
import os
from uuid import uuid4

from app.domain.tool import McpServer, Tool
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient
from app.infrastructure.externalservices.mcp.tool_executor import InfrastructureToolExecutor
from app.infrastructure.knowledge.parsers import DocumentParser

server = McpServer(
    id=uuid4(),
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
    source="SMOKE",
)

class Repository:
    async def get_mcp_server_by_name(self, name):
        return server if name == "google-workspace" else None

tool = Tool(
    id=uuid4(),
    name="google-drive-read-file",
    description="Read Google Drive file",
    instructions="",
    implementation_type="GOOGLE_DRIVE_READ",
    configuration={"server": "google-workspace"},
    input_schema={},
)

async def main():
    executor = InfrastructureToolExecutor(
        Repository(),
        McpStdioClient(timeout_seconds=60),
        DocumentParser(),
        mcp_workspace_root="/opt/workspace",
    )
    result = await executor.execute(
        tool,
        {"fileId": os.environ["GOOGLE_DRIVE_TEST_FILE_ID"]},
    )
    output = result.get("output") or {}
    text = output.get("text") if isinstance(output, dict) else None
    if isinstance(output, dict) and "output" in output:
        nested = output.get("output") or {}
        text = nested.get("text") if isinstance(nested, dict) else text
    print("Reader:", result.get("reader"))
    print("File:", (result.get("file") or {}).get("name"))
    if isinstance(text, str):
        print("Characters:", len(text))
        print("Preview:", text[:500].replace("\n", " "))
        if not text.strip():
            raise SystemExit("Reader returned empty text")
    else:
        print("Output:", str(output)[:1000])

asyncio.run(main())
PY

echo
echo "Google Workspace MCP + google-drive-read-file smoke test PASSED."
