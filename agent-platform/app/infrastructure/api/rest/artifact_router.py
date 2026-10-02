from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.business.artifact_service import ArtifactService


def create_artifact_router(service: ArtifactService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.get("/artifacts/{artifact_id}")
    async def get_artifact(artifact_id: UUID) -> dict:
        artifact = await service.get(artifact_id)
        if not artifact:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return _view(artifact, include_content=True)

    @router.get("/executions/{execution_id}/artifacts")
    async def list_execution_artifacts(execution_id: UUID) -> list[dict]:
        artifacts = await service.list_execution(execution_id)
        return [_view(item, include_content=False) for item in artifacts]

    @router.get("/artifacts")
    async def list_scope_artifacts(
        scopeKey: str = Query(min_length=1),
        latestOnly: bool = False,
    ) -> list[dict]:
        artifacts = await service.list_scope(
            scopeKey,
            latest_only=latestOnly,
        )
        return [_view(item, include_content=False) for item in artifacts]

    return router


def _view(artifact, *, include_content: bool) -> dict:
    value = {
        "id": str(artifact.id),
        "executionId": str(artifact.execution_id),
        "stepId": artifact.step_id,
        "scopeKey": artifact.scope_key,
        "type": artifact.artifact_type,
        "schema": artifact.schema_name,
        "version": artifact.version,
        "title": artifact.title,
        "mediaType": artifact.media_type,
        "summary": artifact.summary,
        "checksum": artifact.checksum,
        "sizeBytes": artifact.size_bytes,
        "metadata": artifact.metadata,
        "createdAt": (
            artifact.created_at.isoformat()
            if artifact.created_at
            else None
        ),
    }
    if include_content:
        value["content"] = artifact.content
    return value
