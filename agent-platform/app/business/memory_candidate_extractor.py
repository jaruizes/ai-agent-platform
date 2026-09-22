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
    """LLM-assisted extractor. It only proposes candidates; policy remains authoritative."""

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
        system_prompt = (
            "You extract candidate memories from a completed execution. "
            "Return ONLY a JSON array. Extract only durable facts, preferences, "
            "decisions or constraints that are useful in later turns of the same session. "
            "Do not extract secrets, credentials, tokens, transient execution details, "
            "or information not explicitly supported by the input/result. "
            "Each item must contain: type, key, content, confidence, importance. "
            f"Return at most {self._max_candidates} items."
        )
        user_prompt = json.dumps(
            {
                "intent": command.intent,
                "input": command.input,
                "context": command.context,
                "instructions": command.instructions,
                "result": result,
            },
            ensure_ascii=False,
            default=str,
        )
        detail = await self._model_gateway.complete_detailed(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_profile=self._model_profile,
            temperature=0.0,
        )
        payload = str(detail.get("content") or "").strip()
        match = _JSON_BLOCK.search(payload)
        if match:
            payload = match.group(1).strip()
        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("Memory extractor response must be a JSON array")

        candidates: list[MemoryCandidate] = []
        for item in data[: self._max_candidates]:
            if not isinstance(item, dict):
                continue
            candidates.append(
                MemoryCandidate(
                    scope_type="SESSION",
                    scope_id=str(session_id),
                    memory_type=str(item.get("type") or "LEARNED_CONTEXT"),
                    memory_key=(
                        str(item["key"]).strip()
                        if item.get("key") is not None
                        else None
                    ),
                    content=str(item.get("content") or "").strip(),
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
