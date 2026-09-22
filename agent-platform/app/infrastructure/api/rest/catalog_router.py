from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.business.catalog_service import CatalogService
from app.domain.catalog import Agent, Skill
from app.infrastructure.api.rest.catalog_schemas import (
    AgentRequest,
    AgentResponse,
    SkillRequest,
    SkillResponse,
)


def _skill_response(skill: Skill) -> SkillResponse:
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        instructions=skill.instructions,
        enabled=skill.enabled,
        source=skill.source,
    )


def _agent_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        instructions=agent.instructions,
        enabled=agent.enabled,
        source=agent.source,
        skills=[_skill_response(skill) for skill in agent.skills],
    )


def create_catalog_router(service: CatalogService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.get("/skills", response_model=list[SkillResponse])
    async def list_skills() -> list[SkillResponse]:
        return [_skill_response(skill) for skill in await service.list_skills()]

    @router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
    async def create_skill(request: SkillRequest) -> SkillResponse:
        try:
            return _skill_response(await service.create_skill(**request.model_dump()))
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/skills/{skill_id}", response_model=SkillResponse)
    async def update_skill(skill_id: UUID, request: SkillRequest) -> SkillResponse:
        try:
            skill = await service.update_skill(skill_id, **request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not skill:
            raise HTTPException(status_code=404, detail="Skill not found")
        return _skill_response(skill)

    @router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_skill(skill_id: UUID, response: Response) -> Response:
        try:
            deleted = await service.delete_skill(skill_id)
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail="Skill is assigned to an agent and cannot be deleted",
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Skill not found")
        return response

    @router.get("/agents", response_model=list[AgentResponse])
    async def list_agents() -> list[AgentResponse]:
        return [_agent_response(agent) for agent in await service.list_agents()]

    @router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
    async def create_agent(request: AgentRequest) -> AgentResponse:
        try:
            agent = await service.create_agent(
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                skill_names=request.skills,
                enabled=request.enabled,
            )
            return _agent_response(agent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/agents/{agent_id}", response_model=AgentResponse)
    async def update_agent(agent_id: UUID, request: AgentRequest) -> AgentResponse:
        try:
            agent = await service.update_agent(
                agent_id,
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                skill_names=request.skills,
                enabled=request.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return _agent_response(agent)

    @router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_agent(agent_id: UUID, response: Response) -> Response:
        if not await service.delete_agent(agent_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        return response

    return router
