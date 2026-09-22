from uuid import UUID, uuid4

from app.business.ports import PromptRepositoryPort
from app.domain.prompt import Prompt


class PromptService:
    def __init__(self, repository: PromptRepositoryPort):
        self._repository = repository

    async def list_prompts(self) -> list[Prompt]:
        return await self._repository.list_prompts()

    async def get_by_name(self, name: str) -> Prompt:
        prompt = await self._repository.get_prompt_by_name(name)
        if not prompt or not prompt.enabled:
            raise LookupError(f"Prompt '{name}' not found or disabled")
        return prompt

    async def create_prompt(
        self,
        *,
        name: str,
        description: str,
        content: str,
        version: int = 1,
        enabled: bool = True,
        source: str = "USER",
        only_if_missing: bool = False,
    ) -> Prompt:
        existing = await self._repository.get_prompt_by_name(name)
        if existing:
            if only_if_missing:
                return existing
            raise ValueError(f"Prompt '{name}' already exists")
        return await self._repository.create_prompt(
            Prompt(
                id=uuid4(),
                name=name,
                description=description,
                content=content,
                version=version,
                enabled=enabled,
                source=source,
            )
        )

    async def update_prompt(
        self,
        prompt_id: UUID,
        *,
        name: str,
        description: str,
        content: str,
        version: int,
        enabled: bool,
    ) -> Prompt | None:
        existing = await self._repository.get_prompt(prompt_id)
        if not existing:
            return None
        return await self._repository.update_prompt(
            Prompt(
                id=prompt_id,
                name=name,
                description=description,
                content=content,
                version=version,
                enabled=enabled,
                source=existing.source,
            )
        )

    async def delete_prompt(self, prompt_id: UUID) -> bool:
        return await self._repository.delete_prompt(prompt_id)
