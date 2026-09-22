from typing import Any
from uuid import UUID, uuid4

from jsonschema import validate

from app.business.ports import ToolExecutorPort, ToolRepositoryPort
from app.domain.tool import McpServer, Tool


class ToolService:
    def __init__(self, repository: ToolRepositoryPort, executor: ToolExecutorPort):
        self._repository = repository
        self._executor = executor

    async def list_tools(self, enabled_only: bool = False) -> list[Tool]:
        return await self._repository.list_tools(enabled_only)

    async def get_tool(self, tool_id: UUID) -> Tool | None:
        return await self._repository.get_tool(tool_id)

    async def create_tool(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        implementation_type: str,
        configuration: dict[str, Any],
        input_schema: dict[str, Any],
        side_effect: str = "READ",
        approval_policy: str = "NEVER",
        enabled: bool = True,
        source: str = "USER",
        only_if_missing: bool = False,
    ) -> Tool:
        existing = await self._repository.get_tool_by_name(name)
        if existing:
            if only_if_missing:
                return existing
            raise ValueError(f"Tool '{name}' already exists")

        side_effect = side_effect.upper()
        approval_policy = approval_policy.upper()
        self._validate_tool_policy(side_effect, approval_policy)

        if implementation_type.upper() == "MCP":
            server_name = configuration.get("server")
            remote_tool = configuration.get("tool")
            if not server_name or not remote_tool:
                raise ValueError("MCP tools require configuration.server and configuration.tool")
            if not await self._repository.get_mcp_server_by_name(server_name):
                raise ValueError(f"MCP server '{server_name}' does not exist")

        return await self._repository.create_tool(
            Tool(
                id=uuid4(),
                name=name,
                description=description,
                instructions=instructions,
                implementation_type=implementation_type.upper(),
                configuration=configuration,
                input_schema=input_schema,
                side_effect=side_effect,
                approval_policy=approval_policy,
                enabled=enabled,
                source=source,
            )
        )

    async def update_tool(
        self,
        tool_id: UUID,
        *,
        name: str,
        description: str,
        instructions: str,
        implementation_type: str,
        configuration: dict[str, Any],
        input_schema: dict[str, Any],
        side_effect: str,
        approval_policy: str,
        enabled: bool,
    ) -> Tool | None:
        existing = await self._repository.get_tool(tool_id)
        if not existing:
            return None
        side_effect = side_effect.upper()
        approval_policy = approval_policy.upper()
        self._validate_tool_policy(side_effect, approval_policy)
        tool = Tool(
            id=tool_id,
            name=name,
            description=description,
            instructions=instructions,
            implementation_type=implementation_type.upper(),
            configuration=configuration,
            input_schema=input_schema,
            side_effect=side_effect,
            approval_policy=approval_policy,
            enabled=enabled,
            source=existing.source,
        )
        return await self._repository.update_tool(tool)

    @staticmethod
    def _validate_tool_policy(side_effect: str, approval_policy: str) -> None:
        allowed_side_effects = {"NONE", "READ", "WRITE", "EXTERNAL_ACTION"}
        allowed_approval_policies = {"NEVER", "OPTIONAL", "REQUIRED"}
        if side_effect not in allowed_side_effects:
            raise ValueError(
                "sideEffect must be one of NONE, READ, WRITE, EXTERNAL_ACTION"
            )
        if approval_policy not in allowed_approval_policies:
            raise ValueError(
                "approvalPolicy must be one of NEVER, OPTIONAL, REQUIRED"
            )

    async def delete_tool(self, tool_id: UUID) -> bool:
        return await self._repository.delete_tool(tool_id)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = await self._repository.get_tool_by_name(tool_name)
        if not tool or not tool.enabled:
            raise LookupError(f"Tool '{tool_name}' not found or disabled")
        if tool.input_schema:
            validate(instance=arguments, schema=tool.input_schema)
        return await self._executor.execute(tool, arguments)

    async def list_mcp_servers(self, enabled_only: bool = False) -> list[McpServer]:
        return await self._repository.list_mcp_servers(enabled_only)

    async def create_mcp_server(
        self,
        *,
        name: str,
        description: str,
        command: str,
        args: list[str],
        cwd: str | None,
        environment: dict[str, str],
        enabled: bool = True,
        source: str = "USER",
        only_if_missing: bool = False,
    ) -> McpServer:
        existing = await self._repository.get_mcp_server_by_name(name)
        if existing:
            if only_if_missing:
                return existing
            raise ValueError(f"MCP server '{name}' already exists")
        return await self._repository.create_mcp_server(
            McpServer(
                id=uuid4(),
                name=name,
                description=description,
                command=command,
                args=args,
                cwd=cwd,
                environment=environment,
                enabled=enabled,
                source=source,
            )
        )

    async def update_mcp_server(
        self,
        server_id: UUID,
        *,
        name: str,
        description: str,
        command: str,
        args: list[str],
        cwd: str | None,
        environment: dict[str, str],
        enabled: bool,
    ) -> McpServer | None:
        existing = await self._repository.get_mcp_server(server_id)
        if not existing:
            return None
        return await self._repository.update_mcp_server(
            McpServer(
                id=server_id,
                name=name,
                description=description,
                command=command,
                args=args,
                cwd=cwd,
                environment=environment,
                enabled=enabled,
                source=existing.source,
            )
        )

    async def delete_mcp_server(self, server_id: UUID) -> bool:
        return await self._repository.delete_mcp_server(server_id)
