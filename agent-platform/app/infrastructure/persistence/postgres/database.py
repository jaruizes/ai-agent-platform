from pathlib import Path

import asyncpg


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        migration = Path("/app/migrations/001_init.sql").read_text(encoding="utf-8")
        async with self.pool.acquire() as connection:
            await connection.execute(migration)

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def require_pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Database is not connected")
        return self.pool
