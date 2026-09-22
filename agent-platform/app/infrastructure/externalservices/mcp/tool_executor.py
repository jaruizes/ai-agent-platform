import json
from typing import Any

from app.business.ports import ToolRepositoryPort
from app.domain.tool import Tool
from app.infrastructure.externalservices.mcp.stdio_client import McpStdioClient


class InfrastructureToolExecutor:
    def __init__(self, repository: ToolRepositoryPort, mcp_client: McpStdioClient):
        self._repository = repository
        self._mcp_client = mcp_client

    async def execute(self, tool: Tool, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool.implementation_type == "MCP":
            return await self._execute_mcp(tool, arguments)
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
