from pathlib import Path

import asyncpg


class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self._dsn, min_size=1, max_size=10)
        migration_dir = Path("/app/migrations")
        async with self.pool.acquire() as connection:
            for migration in sorted(migration_dir.glob("*.sql")):
                await connection.execute(migration.read_text(encoding="utf-8"))

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def require_pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Database is not connected")
        return self.pool
