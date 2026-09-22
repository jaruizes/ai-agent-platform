from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.business.tool_service import ToolService
from app.domain.tool import McpServer, Tool
from app.infrastructure.api.rest.tool_schemas import (
    McpServerRequest,
    McpServerResponse,
    ToolRequest,
    ToolResponse,
)


def _tool_response(tool: Tool) -> ToolResponse:
    return ToolResponse(
        id=tool.id,
        name=tool.name,
        description=tool.description,
        instructions=tool.instructions,
        implementationType=tool.implementation_type,
        configuration=tool.configuration,
        inputSchema=tool.input_schema,
        sideEffect=tool.side_effect,
        approvalPolicy=tool.approval_policy,
        enabled=tool.enabled,
        source=tool.source,
    )


def _server_response(server: McpServer) -> McpServerResponse:
    return McpServerResponse(
        id=server.id,
        name=server.name,
        description=server.description,
        command=server.command,
        args=server.args,
        cwd=server.cwd,
        environment=server.environment,
        enabled=server.enabled,
        source=server.source,
    )


def create_tool_router(service: ToolService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.get("/tools", response_model=list[ToolResponse])
    async def list_tools() -> list[ToolResponse]:
        return [_tool_response(tool) for tool in await service.list_tools()]

    @router.post("/tools", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
    async def create_tool(request: ToolRequest) -> ToolResponse:
        try:
            tool = await service.create_tool(
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                implementation_type=request.implementationType,
                configuration=request.configuration,
                input_schema=request.inputSchema,
                side_effect=request.sideEffect,
                approval_policy=request.approvalPolicy,
                enabled=request.enabled,
            )
            return _tool_response(tool)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/tools/{tool_id}", response_model=ToolResponse)
    async def update_tool(tool_id: UUID, request: ToolRequest) -> ToolResponse:
        try:
            tool = await service.update_tool(
                tool_id,
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                implementation_type=request.implementationType,
                configuration=request.configuration,
                input_schema=request.inputSchema,
                side_effect=request.sideEffect,
                approval_policy=request.approvalPolicy,
                enabled=request.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not tool:
            raise HTTPException(status_code=404, detail="Tool not found")
        return _tool_response(tool)

    @router.delete("/tools/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_tool(tool_id: UUID, response: Response) -> Response:
        if not await service.delete_tool(tool_id):
            raise HTTPException(status_code=404, detail="Tool not found")
        return response

    @router.get("/mcp-servers", response_model=list[McpServerResponse])
    async def list_mcp_servers() -> list[McpServerResponse]:
        return [_server_response(server) for server in await service.list_mcp_servers()]

    @router.post("/mcp-servers", response_model=McpServerResponse, status_code=status.HTTP_201_CREATED)
    async def create_mcp_server(request: McpServerRequest) -> McpServerResponse:
        try:
            server = await service.create_mcp_server(**request.model_dump())
            return _server_response(server)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/mcp-servers/{server_id}", response_model=McpServerResponse)
    async def update_mcp_server(server_id: UUID, request: McpServerRequest) -> McpServerResponse:
        server = await service.update_mcp_server(server_id, **request.model_dump())
        if not server:
            raise HTTPException(status_code=404, detail="MCP server not found")
        return _server_response(server)

    @router.delete("/mcp-servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_mcp_server(server_id: UUID, response: Response) -> Response:
        if not await service.delete_mcp_server(server_id):
            raise HTTPException(status_code=404, detail="MCP server not found")
        return response

    return router
