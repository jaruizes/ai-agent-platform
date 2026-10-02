from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID, uuid4

from app.domain.artifact import ARTIFACT_TYPES, Artifact


_JSON_FENCE = re.compile(
    r"^\s*```(?:json)?\s*(.*?)\s*```\s*$",
    re.DOTALL | re.IGNORECASE,
)


class ArtifactService:
    def __init__(
        self,
        repository,
        *,
        context_max_chars: int = 24000,
        handoff_max_chars: int = 8000,
    ):
        self._repository = repository
        self._context_max_chars = max(1000, context_max_chars)
        self._handoff_max_chars = max(1000, handoff_max_chars)

    @staticmethod
    def enabled_for_agent(
        policy: dict[str, Any] | None,
        agent_name: str | None,
    ) -> bool:
        if not policy or not bool(policy.get("enabled", False)):
            return False
        names = policy.get("agentNames") or []
        if names and agent_name not in names:
            return False
        return True

    def output_contract(self, policy: dict[str, Any]) -> str:
        schema_name = str(policy.get("schema") or "generic-agent-output/v1")
        human_title = str(policy.get("humanTitle") or "Agent result")
        artifact_type = str(
            policy.get("humanArtifactType") or "HUMAN_DOCUMENT"
        ).upper()
        if artifact_type not in {"HUMAN_DOCUMENT", "FINAL_DELIVERABLE"}:
            artifact_type = "HUMAN_DOCUMENT"

        return f"""
\n\n## REQUIRED ARTIFACT OUTPUT CONTRACT
Return ONLY one valid JSON object. Do not wrap it in Markdown fences.
The platform will persist the fields as separate typed artifacts, so do not
repeat the same long content in several fields.

{{
  "summary": "Concise review summary, preferably <= 500 tokens",
  "humanDocument": {{
    "title": "{human_title}",
    "markdown": "Human-readable report. This is the only place for long narrative."
  }},
  "machineData": {{
    "...": "Compact structured facts and decisions for downstream agents"
  }},
  "handoff": {{
    "objective": "What the next agent should accomplish",
    "keyFacts": ["Only high-value facts"],
    "hardConstraints": ["Constraints that must not be lost"],
    "openQuestions": ["Material unresolved questions"],
    "recommendedNextActions": ["Compact next actions"]
  }},
  "evidence": [
    {{
      "claim": "Important claim or decision",
      "sourceId": "Source/document identifier when available",
      "locator": "Page/sheet/section when available"
    }}
  ]
}}

Machine schema identifier: {schema_name}
Human artifact type: {artifact_type}

Rules:
- Keep machineData structured and compact; do not copy the human report into it.
- Keep handoff deliberately small. It is optimized for another agent's context.
- Evidence contains references, not copied source documents.
- Never place full source documents in any artifact.
- If a field has no useful content, return an empty object/array rather than prose.
"""

    async def capture_model_output(
        self,
        *,
        execution_id: UUID,
        step_id: str,
        metadata: dict[str, Any],
        raw_content: str,
        policy: dict[str, Any],
    ) -> dict[str, Any]:
        payload = self._decode_output(raw_content)
        scope_key = self._scope_key(execution_id, step_id, metadata)
        version = await self._repository.next_version(scope_key)
        schema_name = str(policy.get("schema") or "generic-agent-output/v1")
        title = str(
            (payload.get("humanDocument") or {}).get("title")
            or policy.get("humanTitle")
            or step_id
        )
        summary = self._compact_text(
            str(payload.get("summary") or ""),
            4000,
        )
        if not summary:
            summary = self._compact_text(raw_content, 2000)

        artifacts: list[Artifact] = []
        human = payload.get("humanDocument")
        if isinstance(human, dict) and str(human.get("markdown") or "").strip():
            human_type = str(
                policy.get("humanArtifactType") or "HUMAN_DOCUMENT"
            ).upper()
            if human_type not in {"HUMAN_DOCUMENT", "FINAL_DELIVERABLE"}:
                human_type = "HUMAN_DOCUMENT"
            artifacts.append(
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type=human_type,
                    schema_name=f"{schema_name}/human",
                    version=version,
                    title=title,
                    media_type="text/markdown",
                    summary=summary,
                    content={
                        "title": title,
                        "markdown": str(human.get("markdown") or ""),
                    },
                    metadata=metadata,
                )
            )

        machine = payload.get("machineData")
        if isinstance(machine, dict) and machine:
            artifacts.append(
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type="MACHINE_DATA",
                    schema_name=schema_name,
                    version=version,
                    title=f"{title} · machine data",
                    media_type="application/json",
                    summary=summary,
                    content=machine,
                    metadata=metadata,
                )
            )

        handoff = payload.get("handoff")
        if isinstance(handoff, dict) and handoff:
            handoff = self._truncate_json(handoff, self._handoff_max_chars)
            artifacts.append(
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type="AGENT_HANDOFF",
                    schema_name=f"{schema_name}/handoff",
                    version=version,
                    title=f"{title} · agent handoff",
                    media_type="application/json",
                    summary=summary,
                    content=handoff,
                    metadata=metadata,
                )
            )

        evidence = payload.get("evidence")
        if isinstance(evidence, list) and evidence:
            artifacts.append(
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type="EVIDENCE_SET",
                    schema_name=f"{schema_name}/evidence",
                    version=version,
                    title=f"{title} · evidence",
                    media_type="application/json",
                    summary=summary,
                    content={"items": evidence[:200]},
                    metadata=metadata,
                )
            )

        if not artifacts:
            artifacts = [
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type="HUMAN_DOCUMENT",
                    schema_name=f"{schema_name}/fallback",
                    version=version,
                    title=title,
                    media_type="text/markdown",
                    summary=summary,
                    content={"title": title, "markdown": raw_content},
                    metadata={**metadata, "artifactFallback": True},
                ),
                self._artifact(
                    execution_id=execution_id,
                    step_id=step_id,
                    scope_key=scope_key,
                    artifact_type="AGENT_HANDOFF",
                    schema_name=f"{schema_name}/handoff-fallback",
                    version=version,
                    title=f"{title} · agent handoff",
                    media_type="application/json",
                    summary=summary,
                    content={
                        "objective": "",
                        "keyFacts": [self._compact_text(raw_content, 3500)],
                        "hardConstraints": [],
                        "openQuestions": [],
                        "recommendedNextActions": [],
                    },
                    metadata={**metadata, "artifactFallback": True},
                ),
            ]

        await self._repository.create_many(artifacts)
        refs = [artifact.ref() for artifact in artifacts]
        return {
            "summary": summary,
            "artifactRefs": refs,
            "version": version,
            "scopeKey": scope_key,
        }

    async def build_agent_context(
        self,
        payload: Any,
    ) -> tuple[str, list[dict[str, Any]]]:
        ids = self._collect_artifact_ids(payload)
        if not ids:
            return "", []
        artifacts = await self._repository.list_by_ids(ids)
        selected = [
            item
            for item in artifacts
            if item.artifact_type in {
                "AGENT_HANDOFF",
                "MACHINE_DATA",
                "EVIDENCE_SET",
            }
        ]
        if not selected:
            return "", []

        blocks: list[dict[str, Any]] = []
        total = 0
        provenance: list[dict[str, Any]] = []
        for item in selected:
            entry = {
                "artifactId": str(item.id),
                "type": item.artifact_type,
                "schema": item.schema_name,
                "version": item.version,
                "title": item.title,
                "content": item.content,
            }
            encoded = json.dumps(entry, ensure_ascii=False, default=str)
            if total + len(encoded) > self._context_max_chars:
                remaining = self._context_max_chars - total
                if remaining < 1000:
                    break
                blocks.append(
                    {
                        "artifactId": str(item.id),
                        "type": item.artifact_type,
                        "schema": item.schema_name,
                        "truncated": True,
                        "contentPreview": encoded[:remaining],
                    }
                )
                provenance.append(self._provenance(item, True))
                break
            blocks.append(entry)
            total += len(encoded)
            provenance.append(self._provenance(item, False))

        return (
            "Managed artifact context (machine/handoff only; human documents are intentionally excluded):\n"
            + json.dumps(blocks, ensure_ascii=False, indent=2, default=str),
            provenance,
        )

    async def get(self, artifact_id: UUID) -> Artifact | None:
        return await self._repository.get(artifact_id)

    async def list_execution(self, execution_id: UUID) -> list[Artifact]:
        return await self._repository.list_by_execution(execution_id)

    async def list_scope(
        self,
        scope_key: str,
        *,
        latest_only: bool = False,
    ) -> list[Artifact]:
        return await self._repository.list_scope(
            scope_key,
            latest_only=latest_only,
        )

    @staticmethod
    def _scope_key(
        execution_id: UUID,
        step_id: str,
        metadata: dict[str, Any],
    ) -> str:
        process_instance = metadata.get("processInstanceId")
        process_step = metadata.get("processStepKey")
        if process_instance and process_step:
            return f"process:{process_instance}:step:{process_step}"
        return f"execution:{execution_id}:step:{step_id}"

    @staticmethod
    def _decode_output(raw: str) -> dict[str, Any]:
        candidate = raw.strip()
        match = _JSON_FENCE.match(candidate)
        if match:
            candidate = match.group(1).strip()
        try:
            decoded = json.loads(candidate)
            return decoded if isinstance(decoded, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _compact_text(value: str, max_chars: int) -> str:
        compact = re.sub(r"\s+", " ", value).strip()
        return compact[:max_chars]

    @staticmethod
    def _truncate_json(
        value: dict[str, Any],
        max_chars: int,
    ) -> dict[str, Any]:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        if len(encoded) <= max_chars:
            return value
        return {
            "truncated": True,
            "summary": encoded[:max_chars],
        }

    @staticmethod
    def _collect_artifact_ids(value: Any) -> list[UUID]:
        found: list[UUID] = []

        def visit(item: Any) -> None:
            if isinstance(item, dict):
                raw = item.get("artifactId")
                if raw:
                    try:
                        found.append(UUID(str(raw)))
                    except ValueError:
                        pass
                for nested in item.values():
                    visit(nested)
            elif isinstance(item, list):
                for nested in item:
                    visit(nested)

        visit(value)
        return list(dict.fromkeys(found))

    @staticmethod
    def _provenance(item: Artifact, truncated: bool) -> dict[str, Any]:
        return {
            "type": "ARTIFACT",
            "id": str(item.id),
            "artifactType": item.artifact_type,
            "schema": item.schema_name,
            "version": item.version,
            "scopeKey": item.scope_key,
            "truncated": truncated,
        }

    @staticmethod
    def _artifact(
        *,
        execution_id: UUID,
        step_id: str,
        scope_key: str,
        artifact_type: str,
        schema_name: str,
        version: int,
        title: str,
        media_type: str,
        summary: str,
        content: Any,
        metadata: dict[str, Any],
    ) -> Artifact:
        if artifact_type not in ARTIFACT_TYPES:
            raise ValueError(f"Unsupported artifact type: {artifact_type}")
        encoded = json.dumps(
            content,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return Artifact(
            id=uuid4(),
            execution_id=execution_id,
            step_id=step_id,
            scope_key=scope_key,
            artifact_type=artifact_type,
            schema_name=schema_name,
            version=version,
            title=title,
            media_type=media_type,
            summary=summary,
            content=content,
            checksum=hashlib.sha256(encoded).hexdigest(),
            size_bytes=len(encoded),
            metadata={
                "processInstanceId": metadata.get("processInstanceId"),
                "processStepKey": metadata.get("processStepKey"),
                "processDefinitionKey": metadata.get("processDefinitionKey"),
                "processDefinitionVersion": metadata.get("processDefinitionVersion"),
            },
        )
