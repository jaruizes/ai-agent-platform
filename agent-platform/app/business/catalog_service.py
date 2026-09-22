from uuid import UUID, uuid4

from app.business.ports import CatalogRepositoryPort
from app.domain.catalog import Agent, Skill


class CatalogService:
    def __init__(self, repository: CatalogRepositoryPort):
        self._repository = repository

    async def list_skills(self, enabled_only: bool = False) -> list[Skill]:
        return await self._repository.list_skills(enabled_only)

    async def get_skill(self, skill_id: UUID) -> Skill | None:
        return await self._repository.get_skill(skill_id)

    async def create_skill(self, *, name: str, description: str, instructions: str,
                           enabled: bool = True, source: str = "USER",
                           only_if_missing: bool = False) -> Skill:
        existing = await self._repository.get_skill_by_name(name)
        if existing:
            if only_if_missing:
                return existing
            raise ValueError(f"Skill '{name}' already exists")
        return await self._repository.create_skill(
            Skill(id=uuid4(), name=name, description=description,
                  instructions=instructions, enabled=enabled, source=source)
        )

    async def update_skill(self, skill_id: UUID, *, name: str, description: str,
                           instructions: str, enabled: bool) -> Skill | None:
        existing = await self._repository.get_skill(skill_id)
        if not existing:
            return None
        return await self._repository.update_skill(
            Skill(id=skill_id, name=name, description=description,
                  instructions=instructions, enabled=enabled, source=existing.source)
        )

    async def delete_skill(self, skill_id: UUID) -> bool:
        return await self._repository.delete_skill(skill_id)

    async def list_agents(self, enabled_only: bool = False) -> list[Agent]:
        return await self._repository.list_agents(enabled_only)

    async def get_agent(self, agent_id: UUID) -> Agent | None:
        return await self._repository.get_agent(agent_id)

    async def create_agent(self, *, name: str, description: str, instructions: str,
                           skill_names: list[str], enabled: bool = True,
                           source: str = "USER", only_if_missing: bool = False) -> Agent:
        existing = await self._repository.get_agent_by_name(name)
        if existing:
            if only_if_missing:
                return existing
            raise ValueError(f"Agent '{name}' already exists")
        return await self._repository.create_agent(
            Agent(id=uuid4(), name=name, description=description,
                  instructions=instructions, enabled=enabled, source=source),
            skill_names,
        )

    async def update_agent(self, agent_id: UUID, *, name: str, description: str,
                           instructions: str, skill_names: list[str],
                           enabled: bool) -> Agent | None:
        existing = await self._repository.get_agent(agent_id)
        if not existing:
            return None
        return await self._repository.update_agent(
            Agent(id=agent_id, name=name, description=description,
                  instructions=instructions, enabled=enabled, source=existing.source),
            skill_names,
        )

    async def delete_agent(self, agent_id: UUID) -> bool:
        return await self._repository.delete_agent(agent_id)
