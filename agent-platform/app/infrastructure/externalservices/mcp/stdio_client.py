import asyncio
import json
import os
from typing import Any

from app.domain.tool import McpServer


class McpStdioClient:
    def __init__(
        self,
        timeout_seconds: float = 60.0,
        max_message_bytes: int = 16 * 1024 * 1024,
    ):
        self._timeout_seconds = timeout_seconds
        self._max_message_bytes = max_message_bytes

    async def list_tools(self, server: McpServer) -> list[dict[str, Any]]:
        if not server.enabled:
            raise RuntimeError(f"MCP server '{server.name}' is disabled")

        env = os.environ.copy()
        env.update(server.environment)

        process = await asyncio.create_subprocess_exec(
            server.command,
            *server.args,
            cwd=server.cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=self._max_message_bytes,
        )
        try:
            await self._request(
                process,
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-agent-platform",
                        "version": "0.9.0",
                    },
                },
            )
            await self._notify(process, "notifications/initialized", {})
            result = await self._request(process, 2, "tools/list", {})
            tools = result.get("tools") or []
            if not isinstance(tools, list):
                raise RuntimeError("MCP tools/list returned an invalid tools payload")
            return [tool for tool in tools if isinstance(tool, dict)]
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    process.kill()
                    await process.wait()

    async def call_tool(
        self,
        server: McpServer,
        remote_tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not server.enabled:
            raise RuntimeError(f"MCP server '{server.name}' is disabled")

        env = os.environ.copy()
        env.update(server.environment)

        process = await asyncio.create_subprocess_exec(
            server.command,
            *server.args,
            cwd=server.cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=self._max_message_bytes,
        )
        try:
            await self._request(
                process,
                1,
                "initialize",
                {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ai-agent-platform",
                        "version": "0.4.0",
                    },
                },
            )
            await self._notify(process, "notifications/initialized", {})
            result = await self._request(
                process,
                2,
                "tools/call",
                {
                    "name": remote_tool_name,
                    "arguments": arguments,
                },
            )
            if result.get("isError"):
                details = json.dumps(result, ensure_ascii=False)[:4000]
                raise RuntimeError(
                    f"MCP tool '{remote_tool_name}' returned an error: {details}"
                )
            return result
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=2)
                except TimeoutError:
                    process.kill()
                    await process.wait()

    async def _request(
        self,
        process: asyncio.subprocess.Process,
        request_id: int,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        await self._write(
            process,
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
        )

        while True:
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(),
                    timeout=self._timeout_seconds,
                )
            except TimeoutError as exc:
                raise RuntimeError(
                    f"MCP request '{method}' timed out after "
                    f"{self._timeout_seconds} seconds"
                ) from exc
            except (ValueError, asyncio.LimitOverrunError) as exc:
                raise RuntimeError(
                    f"MCP response exceeded the configured message limit of "
                    f"{self._max_message_bytes} bytes. Increase MCP_MAX_MESSAGE_BYTES "
                    "or make the tool return a bounded/reference-based result."
                ) from exc

            if not line:
                stderr = ""
                if process.stderr:
                    stderr = (
                        await process.stderr.read()
                    ).decode("utf-8", errors="replace")
                raise RuntimeError(
                    f"MCP process ended while waiting for {method}. "
                    f"stderr={stderr[-4000:]}"
                )

            try:
                message = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"MCP server '{method}' returned invalid JSON"
                ) from exc

            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(
                    f"MCP error calling {method}: {message['error']}"
                )
            return message.get("result", {})

    async def _notify(
        self,
        process: asyncio.subprocess.Process,
        method: str,
        params: dict[str, Any],
    ) -> None:
        await self._write(
            process,
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            },
        )

    @staticmethod
    async def _write(
        process: asyncio.subprocess.Process,
        message: dict[str, Any],
    ) -> None:
        if not process.stdin:
            raise RuntimeError("MCP process stdin is unavailable")
        process.stdin.write(
            (json.dumps(message, separators=(",", ":")) + "\n").encode("utf-8")
        )
        await process.stdin.drain()
