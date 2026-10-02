import json
from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.business.artifact_service import ArtifactService


class FakeArtifactRepository:
    def __init__(self):
        self.items = []
        self.versions = {}

    async def next_version(self, scope_key):
        value = self.versions.get(scope_key, 0) + 1
        self.versions[scope_key] = value
        return value

    async def create_many(self, artifacts):
        self.items.extend(artifacts)
        return artifacts

    async def list_by_ids(self, ids):
        wanted = set(ids)
        return [item for item in self.items if item.id in wanted]

    async def get(self, artifact_id):
        return next((item for item in self.items if item.id == artifact_id), None)

    async def list_by_execution(self, execution_id):
        return [item for item in self.items if item.execution_id == execution_id]

    async def list_scope(self, scope_key, latest_only=False):
        values = [item for item in self.items if item.scope_key == scope_key]
        if not latest_only or not values:
            return values
        latest = max(item.version for item in values)
        return [item for item in values if item.version == latest]


@pytest.mark.asyncio
async def test_capture_creates_human_machine_handoff_and_evidence():
    repo = FakeArtifactRepository()
    service = ArtifactService(repo)
    execution_id = UUID("11111111-1111-1111-1111-111111111111")

    raw = json.dumps(
        {
            "summary": "Qualification ready for review.",
            "humanDocument": {
                "title": "Qualification report",
                "markdown": "# Qualification\n\nCustomer needs migration.",
            },
            "machineData": {
                "customerNeeds": ["migration"],
                "risks": [{"id": "R1", "severity": "HIGH"}],
            },
            "handoff": {
                "objective": "Design the solution",
                "keyFacts": ["AWS required"],
                "hardConstraints": ["6 months"],
                "openQuestions": [],
                "recommendedNextActions": ["Consult security"],
            },
            "evidence": [
                {
                    "claim": "AWS required",
                    "sourceId": "RFP.pdf",
                    "locator": "p.12",
                }
            ],
        }
    )

    captured = await service.capture_model_output(
        execution_id=execution_id,
        step_id="analyse",
        metadata={
            "processInstanceId": "process-1",
            "processStepKey": "understand-and-qualify",
        },
        raw_content=raw,
        policy={
            "enabled": True,
            "schema": "proposal-qualification/v1",
            "humanTitle": "Qualification report",
        },
    )

    assert captured["version"] == 1
    assert captured["scopeKey"] == "process:process-1:step:understand-and-qualify"
    assert {item.artifact_type for item in repo.items} == {
        "HUMAN_DOCUMENT",
        "MACHINE_DATA",
        "AGENT_HANDOFF",
        "EVIDENCE_SET",
    }
    assert all(item.version == 1 for item in repo.items)
    assert all("content" not in ref for ref in captured["artifactRefs"])


@pytest.mark.asyncio
async def test_review_iteration_versions_artifacts_in_same_process_scope():
    repo = FakeArtifactRepository()
    service = ArtifactService(repo)
    metadata = {
        "processInstanceId": "process-1",
        "processStepKey": "understand-and-qualify",
    }
    raw = json.dumps(
        {
            "summary": "Ready.",
            "humanDocument": {"title": "Report", "markdown": "Report"},
            "machineData": {"value": 1},
            "handoff": {"keyFacts": ["one"]},
            "evidence": [],
        }
    )

    first = await service.capture_model_output(
        execution_id=UUID("11111111-1111-1111-1111-111111111111"),
        step_id="analyse",
        metadata=metadata,
        raw_content=raw,
        policy={"enabled": True, "schema": "proposal/v1"},
    )
    second = await service.capture_model_output(
        execution_id=UUID("22222222-2222-2222-2222-222222222222"),
        step_id="analyse",
        metadata=metadata,
        raw_content=raw,
        policy={"enabled": True, "schema": "proposal/v1"},
    )

    assert first["version"] == 1
    assert second["version"] == 2


@pytest.mark.asyncio
async def test_agent_context_excludes_human_document_and_prefers_handoff_machine():
    repo = FakeArtifactRepository()
    service = ArtifactService(repo, context_max_chars=10000)
    execution_id = UUID("11111111-1111-1111-1111-111111111111")

    captured = await service.capture_model_output(
        execution_id=execution_id,
        step_id="analyse",
        metadata={},
        raw_content=json.dumps(
            {
                "summary": "Summary",
                "humanDocument": {
                    "title": "Long report",
                    "markdown": "HUMAN-ONLY-" + ("x" * 5000),
                },
                "machineData": {"requirements": ["REQ-1"]},
                "handoff": {"keyFacts": ["FACT-1"]},
                "evidence": [],
            }
        ),
        policy={"enabled": True, "schema": "proposal/v1"},
    )

    context, provenance = await service.build_agent_context(
        {"artifactRefs": captured["artifactRefs"]}
    )

    assert "FACT-1" in context
    assert "REQ-1" in context
    assert "HUMAN-ONLY" not in context
    assert {item["artifactType"] for item in provenance} == {
        "AGENT_HANDOFF",
        "MACHINE_DATA",
    }


@pytest.mark.asyncio
async def test_unstructured_model_output_falls_back_without_extra_model_call():
    repo = FakeArtifactRepository()
    service = ArtifactService(repo)

    captured = await service.capture_model_output(
        execution_id=UUID("11111111-1111-1111-1111-111111111111"),
        step_id="analyse",
        metadata={},
        raw_content="Plain unstructured report.",
        policy={"enabled": True, "schema": "generic/v1"},
    )

    assert {item.artifact_type for item in repo.items} == {
        "HUMAN_DOCUMENT",
        "AGENT_HANDOFF",
    }
    assert captured["summary"] == "Plain unstructured report."
