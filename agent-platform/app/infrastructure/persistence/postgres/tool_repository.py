import json
from uuid import UUID

from app.domain.tool import McpServer, Tool
from app.infrastructure.persistence.postgres.database import Database


class PostgresToolRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_tools(self, enabled_only: bool = False) -> list[Tool]:
        sql = "SELECT * FROM tools"
        if enabled_only:
            sql += " WHERE enabled = true"
        sql += " ORDER BY name"
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(sql)
            return [self._tool(row) for row in rows]

    async def get_tool(self, tool_id: UUID) -> Tool | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tools WHERE id=$1", tool_id)
            return self._tool(row) if row else None

    async def get_tool_by_name(self, name: str) -> Tool | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tools WHERE name=$1", name)
            return self._tool(row) if row else None

    async def create_tool(self, tool: Tool) -> Tool:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO tools(id,name,description,instructions,implementation_type,configuration,input_schema,side_effect,approval_policy,enabled,source) VALUES($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8,$9,$10,$11)",
                tool.id, tool.name, tool.description, tool.instructions, tool.implementation_type,
                json.dumps(tool.configuration), json.dumps(tool.input_schema),
                tool.side_effect, tool.approval_policy, tool.enabled, tool.source,
            )
        return tool

    async def update_tool(self, tool: Tool) -> Tool:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "UPDATE tools SET name=$2,description=$3,instructions=$4,implementation_type=$5,configuration=$6::jsonb,input_schema=$7::jsonb,side_effect=$8,approval_policy=$9,enabled=$10,updated_at=now() WHERE id=$1",
                tool.id, tool.name, tool.description, tool.instructions, tool.implementation_type,
                json.dumps(tool.configuration), json.dumps(tool.input_schema),
                tool.side_effect, tool.approval_policy, tool.enabled,
            )
        return tool

    async def delete_tool(self, tool_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM tools WHERE id=$1", tool_id) == "DELETE 1"

    async def list_mcp_servers(self, enabled_only: bool = False) -> list[McpServer]:
        sql = "SELECT * FROM mcp_servers"
        if enabled_only:
            sql += " WHERE enabled = true"
        sql += " ORDER BY name"
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(sql)
            return [self._server(row) for row in rows]

    async def get_mcp_server(self, server_id: UUID) -> McpServer | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM mcp_servers WHERE id=$1", server_id)
            return self._server(row) if row else None

    async def get_mcp_server_by_name(self, name: str) -> McpServer | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM mcp_servers WHERE name=$1", name)
            return self._server(row) if row else None

    async def create_mcp_server(self, server: McpServer) -> McpServer:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO mcp_servers(id,name,description,command,args,cwd,environment,enabled,source) VALUES($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb,$8,$9)",
                server.id, server.name, server.description, server.command, json.dumps(server.args),
                server.cwd, json.dumps(server.environment), server.enabled, server.source,
            )
        return server

    async def update_mcp_server(self, server: McpServer) -> McpServer:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "UPDATE mcp_servers SET name=$2,description=$3,command=$4,args=$5::jsonb,cwd=$6,environment=$7::jsonb,enabled=$8,updated_at=now() WHERE id=$1",
                server.id, server.name, server.description, server.command, json.dumps(server.args),
                server.cwd, json.dumps(server.environment), server.enabled,
            )
        return server

    async def delete_mcp_server(self, server_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM mcp_servers WHERE id=$1", server_id) == "DELETE 1"

    @staticmethod
    def _decode_json(value):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _tool(cls, row) -> Tool:
        return Tool(
            id=row["id"], name=row["name"], description=row["description"],
            instructions=row["instructions"], implementation_type=row["implementation_type"],
            configuration=dict(cls._decode_json(row["configuration"]) or {}),
            input_schema=dict(cls._decode_json(row["input_schema"]) or {}),
            side_effect=row["side_effect"],
            approval_policy=row["approval_policy"],
            enabled=row["enabled"], source=row["source"],
        )

    @classmethod
    def _server(cls, row) -> McpServer:
        return McpServer(
            id=row["id"], name=row["name"], description=row["description"],
            command=row["command"],
            args=list(cls._decode_json(row["args"]) or []),
            cwd=row["cwd"],
            environment=dict(cls._decode_json(row["environment"]) or {}),
            enabled=row["enabled"], source=row["source"],
        )
