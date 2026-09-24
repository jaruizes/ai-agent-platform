from uuid import uuid4

import pytest

from app.business.tool_service import ToolService
from app.domain.tool import McpServer


class FakeRepository:
    def __init__(self, with_server: bool = True):
        self.server = (
            McpServer(
                id=uuid4(),
                name="google-workspace",
                description="Google Workspace MCP",
                command="node",
                args=[],
                cwd=None,
                environment={},
                enabled=True,
                source="TEST",
            )
            if with_server
            else None
        )
        self.created = None

    async def get_tool_by_name(self, name):
        return None

    async def get_mcp_server_by_name(self, name):
        if self.server and name == self.server.name:
            return self.server
        return None

    async def create_tool(self, tool):
        self.created = tool
        return tool


class FakeExecutor:
    async def execute(self, tool, arguments):
        raise AssertionError("not used")


@pytest.mark.asyncio
async def test_registers_google_drive_reader_against_existing_mcp_server():
    repository = FakeRepository(with_server=True)
    service = ToolService(repository, FakeExecutor())

    tool = await service.create_tool(
        name="google-drive-read-file",
        description="Read Drive file",
        instructions="",
        implementation_type="GOOGLE_DRIVE_READ",
        configuration={"server": "google-workspace"},
        input_schema={"type": "object"},
    )

    assert tool.implementation_type == "GOOGLE_DRIVE_READ"
    assert tool.configuration["server"] == "google-workspace"
    assert repository.created == tool


@pytest.mark.asyncio
async def test_rejects_google_drive_reader_when_mcp_server_is_missing():
    service = ToolService(FakeRepository(with_server=False), FakeExecutor())

    with pytest.raises(ValueError, match="does not exist"):
        await service.create_tool(
            name="google-drive-read-file",
            description="Read Drive file",
            instructions="",
            implementation_type="GOOGLE_DRIVE_READ",
            configuration={"server": "google-workspace"},
            input_schema={"type": "object"},
        )
