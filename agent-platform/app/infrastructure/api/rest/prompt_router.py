from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.business.prompt_service import PromptService
from app.domain.prompt import Prompt
from app.infrastructure.api.rest.prompt_schemas import PromptRequest, PromptResponse


def _response(prompt: Prompt) -> PromptResponse:
    return PromptResponse(
        id=prompt.id,
        name=prompt.name,
        description=prompt.description,
        content=prompt.content,
        version=prompt.version,
        enabled=prompt.enabled,
        source=prompt.source,
    )


def create_prompt_router(service: PromptService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.get("/prompts", response_model=list[PromptResponse])
    async def list_prompts() -> list[PromptResponse]:
        return [_response(prompt) for prompt in await service.list_prompts()]

    @router.post("/prompts", response_model=PromptResponse, status_code=status.HTTP_201_CREATED)
    async def create_prompt(request: PromptRequest) -> PromptResponse:
        try:
            return _response(await service.create_prompt(**request.model_dump()))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/prompts/{prompt_id}", response_model=PromptResponse)
    async def update_prompt(prompt_id: UUID, request: PromptRequest) -> PromptResponse:
        try:
            prompt = await service.update_prompt(prompt_id, **request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return _response(prompt)

    @router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_prompt(prompt_id: UUID, response: Response) -> Response:
        if not await service.delete_prompt(prompt_id):
            raise HTTPException(status_code=404, detail="Prompt not found")
        return response

    return router
