from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from app.business.ports import ModelGatewayPort
from app.domain.execution import Command
from app.domain.memory import MemoryCandidate


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


class MemoryCandidateExtractor:
    """LLM proposes session-memory candidates; deterministic policy decides persistence."""

    def __init__(
        self,
        model_gateway: ModelGatewayPort,
        *,
        model_profile: str,
        max_candidates: int = 8,
    ):
        self._model_gateway = model_gateway
        self._model_profile = model_profile
        self._max_candidates = max(1, max_candidates)

    async def extract_for_session(
        self,
        *,
        session_id: UUID,
        execution_id: UUID,
        command: Command,
        result: dict[str, Any],
    ) -> list[MemoryCandidate]:
        detail = await self._model_gateway.complete_detailed(
            system_prompt=(
                "Extract candidate memories for later turns of the SAME session. "
                "Return ONLY a JSON array. Each item must contain "
                "type, key, content, confidence and importance. "
                "Allowed types: FACT, PREFERENCE, DECISION, CONSTRAINT, "
                "SUMMARY, LEARNED_CONTEXT. Extract only durable information "
                "supported by the execution. Never extract credentials, secrets, "
                "tokens, transient runtime state, retries, IDs or timestamps. "
                f"Return at most {self._max_candidates} items."
            ),
            user_prompt=json.dumps(
                {
                    "intent": command.intent,
                    "input": command.input,
                    "context": command.context,
                    "instructions": command.instructions,
                    "result": result,
                },
                ensure_ascii=False,
                default=str,
            ),
            model_profile=self._model_profile,
            temperature=0.0,
        )
        payload = str(detail.get("content") or "").strip()
        match = _JSON_BLOCK.search(payload)
        if match:
            payload = match.group(1).strip()
        parsed = json.loads(payload)
        if not isinstance(parsed, list):
            raise ValueError("Memory extractor response must be a JSON array")

        candidates: list[MemoryCandidate] = []
        for item in parsed[: self._max_candidates]:
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or "").strip()
            if not content:
                continue
            candidates.append(
                MemoryCandidate(
                    scope_type="SESSION",
                    scope_id=str(session_id),
                    memory_type=str(item.get("type") or "LEARNED_CONTEXT"),
                    memory_key=(
                        str(item.get("key")).strip()
                        if item.get("key") is not None
                        else None
                    ),
                    content=content,
                    confidence=float(item.get("confidence") or 0.0),
                    importance=float(item.get("importance") or 0.5),
                    explicit=False,
                    source_execution_id=execution_id,
                    metadata={
                        "extractor": "llm",
                        "modelProfile": self._model_profile,
                    },
                )
            )
        return candidates
