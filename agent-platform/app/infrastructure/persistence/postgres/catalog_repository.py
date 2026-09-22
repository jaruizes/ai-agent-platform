from uuid import UUID

from app.domain.catalog import Agent, Skill
from app.infrastructure.persistence.postgres.database import Database


class PostgresCatalogRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_skills(self, enabled_only: bool = False) -> list[Skill]:
        pool = self._db.require_pool()
        sql = "SELECT * FROM skills"
        if enabled_only:
            sql += " WHERE enabled = true"
        sql += " ORDER BY name"
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [self._skill(row) for row in rows]

    async def get_skill(self, skill_id: UUID) -> Skill | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM skills WHERE id=$1", skill_id)
            return self._skill(row) if row else None

    async def get_skill_by_name(self, name: str) -> Skill | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM skills WHERE name=$1", name)
            return self._skill(row) if row else None

    async def create_skill(self, skill: Skill) -> Skill:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO skills(id,name,description,instructions,enabled,source) VALUES($1,$2,$3,$4,$5,$6)",
                skill.id, skill.name, skill.description, skill.instructions, skill.enabled, skill.source,
            )
        return skill

    async def update_skill(self, skill: Skill) -> Skill:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                "UPDATE skills SET name=$2,description=$3,instructions=$4,enabled=$5,updated_at=now() WHERE id=$1",
                skill.id, skill.name, skill.description, skill.instructions, skill.enabled,
            )
        return skill

    async def delete_skill(self, skill_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM skills WHERE id=$1", skill_id) == "DELETE 1"

    async def list_agents(self, enabled_only: bool = False) -> list[Agent]:
        pool = self._db.require_pool()
        sql = "SELECT * FROM agents"
        if enabled_only:
            sql += " WHERE enabled = true"
        sql += " ORDER BY name"
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [await self._agent(conn, row) for row in rows]

    async def get_agent(self, agent_id: UUID) -> Agent | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM agents WHERE id=$1", agent_id)
            return await self._agent(conn, row) if row else None

    async def get_agent_by_name(self, name: str) -> Agent | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM agents WHERE name=$1", name)
            return await self._agent(conn, row) if row else None

    async def create_agent(self, agent: Agent, skill_names: list[str]) -> Agent:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "INSERT INTO agents(id,name,description,instructions,enabled,source) VALUES($1,$2,$3,$4,$5,$6)",
                    agent.id, agent.name, agent.description, agent.instructions, agent.enabled, agent.source,
                )
                await self._replace_agent_skills(conn, agent.id, skill_names)
                row = await conn.fetchrow("SELECT * FROM agents WHERE id=$1", agent.id)
                return await self._agent(conn, row)

    async def update_agent(self, agent: Agent, skill_names: list[str]) -> Agent:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    "UPDATE agents SET name=$2,description=$3,instructions=$4,enabled=$5,updated_at=now() WHERE id=$1",
                    agent.id, agent.name, agent.description, agent.instructions, agent.enabled,
                )
                await self._replace_agent_skills(conn, agent.id, skill_names)
                row = await conn.fetchrow("SELECT * FROM agents WHERE id=$1", agent.id)
                return await self._agent(conn, row)

    async def delete_agent(self, agent_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM agents WHERE id=$1", agent_id) == "DELETE 1"

    async def _replace_agent_skills(self, conn, agent_id: UUID, skill_names: list[str]) -> None:
        await conn.execute("DELETE FROM agent_skills WHERE agent_id=$1", agent_id)
        if not skill_names:
            return
        rows = await conn.fetch("SELECT id,name FROM skills WHERE name = ANY($1::text[])", skill_names)
        found = {row["name"] for row in rows}
        missing = set(skill_names) - found
        if missing:
            raise ValueError(f"Unknown skills: {', '.join(sorted(missing))}")
        await conn.executemany(
            "INSERT INTO agent_skills(agent_id,skill_id) VALUES($1,$2)",
            [(agent_id, row["id"]) for row in rows],
        )

    async def _agent(self, conn, row) -> Agent:
        skill_rows = await conn.fetch(
            "SELECT s.* FROM skills s JOIN agent_skills x ON x.skill_id=s.id WHERE x.agent_id=$1 ORDER BY s.name",
            row["id"],
        )
        return Agent(
            id=row["id"], name=row["name"], description=row["description"],
            instructions=row["instructions"], enabled=row["enabled"], source=row["source"],
            skills=[self._skill(skill_row) for skill_row in skill_rows],
        )

    @staticmethod
    def _skill(row) -> Skill:
        return Skill(
            id=row["id"], name=row["name"], description=row["description"],
            instructions=row["instructions"], enabled=row["enabled"], source=row["source"],
        )
