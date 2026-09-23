from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.domain.evals import EvalDataset, EvalDatasetItem, EvalDefinition
from app.infrastructure.api.rest.eval_schemas import (
    EvalDatasetRequest,
    EvalDefinitionRequest,
    EvalRunRequest,
)


def create_eval_router(service) -> APIRouter:
    router = APIRouter(prefix="/v1/evals", tags=["evals"])

    @router.get("/datasets")
    async def list_datasets():
        return [_json(x) for x in await service.list_datasets()]

    @router.post("/datasets")
    async def save_dataset(request: EvalDatasetRequest):
        try:
            dataset = EvalDataset(
                name=request.name, description=request.description,
                version=request.version, enabled=request.enabled,
                items=[
                    EvalDatasetItem(
                        name=i.name, command=i.command,
                        expected_output=i.expectedOutput,
                        assertions=i.assertions, tags=i.tags,
                    )
                    for i in request.items
                ],
            )
            return _json(await service.save_dataset(dataset))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/datasets/{dataset_id}")
    async def delete_dataset(dataset_id: UUID):
        try:
            deleted = await service.delete_dataset(dataset_id)
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail="Dataset is referenced by an eval definition and cannot be deleted",
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return {"deleted": True}

    @router.get("/definitions")
    async def list_definitions():
        return [_json(x) for x in await service.list_definitions()]

    @router.post("/definitions")
    async def save_definition(request: EvalDefinitionRequest):
        try:
            definition = EvalDefinition(
                name=request.name, description=request.description,
                dataset_id=request.datasetId, metrics=request.metrics,
                thresholds=request.thresholds,
                judge_model_profile=request.judgeModelProfile,
                enabled=request.enabled,
            )
            return _json(await service.save_definition(definition))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.delete("/definitions/{definition_id}")
    async def delete_definition(definition_id: UUID):
        try:
            deleted = await service.delete_definition(definition_id)
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail="Definition has eval runs and cannot be deleted",
            ) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="Definition not found")
        return {"deleted": True}

    @router.get("/runs")
    async def list_runs(definitionId: UUID | None = None):
        return [_json(x) for x in await service.list_runs(definitionId)]

    @router.post("/definitions/{definition_id}/runs", status_code=status.HTTP_202_ACCEPTED)
    async def create_run(definition_id: UUID, request: EvalRunRequest):
        try:
            return _json(await service.create_run(definition_id, request.baselineRunId))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/runs/{run_id}")
    async def get_run(run_id: UUID):
        run = await service.get_run(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Eval run not found")
        return _json(run)

    return router


def _json(value):
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_json(x) for x in value]
    if isinstance(value, dict):
        return {k: _json(v) for k, v in value.items()}
    return value
