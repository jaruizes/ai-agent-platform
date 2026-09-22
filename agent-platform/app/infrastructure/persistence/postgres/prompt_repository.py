from uuid import UUID

from app.domain.prompt import Prompt
from app.infrastructure.persistence.postgres.database import Database


class PostgresPromptRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_prompts(self) -> list[Prompt]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch("SELECT * FROM prompts ORDER BY name")
            return [self._prompt(row) for row in rows]

    async def get_prompt(self, prompt_id: UUID) -> Prompt | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM prompts WHERE id=$1", prompt_id)
            return self._prompt(row) if row else None

    async def get_prompt_by_name(self, name: str) -> Prompt | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM prompts WHERE name=$1", name)
            return self._prompt(row) if row else None

    async def create_prompt(self, prompt: Prompt) -> Prompt:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO prompts(id,name,description,content,version,enabled,source)
                VALUES($1,$2,$3,$4,$5,$6,$7)
                """,
                prompt.id, prompt.name, prompt.description, prompt.content,
                prompt.version, prompt.enabled, prompt.source,
            )
        return prompt

    async def update_prompt(self, prompt: Prompt) -> Prompt:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE prompts
                SET name=$2, description=$3, content=$4, version=$5,
                    enabled=$6, updated_at=now()
                WHERE id=$1
                """,
                prompt.id, prompt.name, prompt.description, prompt.content,
                prompt.version, prompt.enabled,
            )
        return prompt

    async def delete_prompt(self, prompt_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM prompts WHERE id=$1", prompt_id) == "DELETE 1"

    @staticmethod
    def _prompt(row) -> Prompt:
        return Prompt(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            content=row["content"],
            version=row["version"],
            enabled=row["enabled"],
            source=row["source"],
        )
