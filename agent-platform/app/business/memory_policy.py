from __future__ import annotations

import re

from app.domain.memory import (
    MEMORY_SCOPE_TYPES,
    MEMORY_TYPES,
    MemoryCandidate,
    MemoryPolicyDecision,
)


class MemoryPolicyEngine:
    """Deterministic policy gate for persistent memory writes."""

    _SECRET_PATTERNS = (
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
        re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I),
        re.compile(r"\b(?:password|passwd|pwd)\s*[:=]\s*\S+", re.I),
        re.compile(r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*\S+", re.I),
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    )

    def __init__(
        self,
        *,
        min_inferred_confidence: float,
        max_content_chars: int,
        allow_inferred_persistence: bool,
    ):
        self._min_inferred_confidence = min_inferred_confidence
        self._max_content_chars = max_content_chars
        self._allow_inferred_persistence = allow_inferred_persistence

    def evaluate(self, candidate: MemoryCandidate) -> MemoryPolicyDecision:
        scope = candidate.scope_type.upper().strip()
        memory_type = candidate.memory_type.upper().strip()
        reasons: list[str] = []

        if scope not in MEMORY_SCOPE_TYPES:
            reasons.append(f"Unsupported memory scope '{scope}'")
        if memory_type not in MEMORY_TYPES:
            reasons.append(f"Unsupported memory type '{memory_type}'")
        if not candidate.scope_id.strip():
            reasons.append("scopeId is required")
        if not candidate.content.strip():
            reasons.append("Memory content is empty")
        if len(candidate.content) > self._max_content_chars:
            reasons.append(
                f"Memory content exceeds {self._max_content_chars} characters"
            )
        if not 0.0 <= candidate.confidence <= 1.0:
            reasons.append("confidence must be between 0 and 1")
        if not 0.0 <= candidate.importance <= 1.0:
            reasons.append("importance must be between 0 and 1")

        if not candidate.explicit:
            if not self._allow_inferred_persistence:
                reasons.append("Inferred memory persistence is disabled")
            elif candidate.confidence < self._min_inferred_confidence:
                reasons.append(
                    "Inferred memory confidence "
                    f"{candidate.confidence:.2f} is below policy threshold "
                    f"{self._min_inferred_confidence:.2f}"
                )

        for pattern in self._SECRET_PATTERNS:
            if pattern.search(candidate.content):
                reasons.append("Secret-like content is not allowed in persistent memory")
                break

        allowed = not reasons
        return MemoryPolicyDecision(
            allowed=allowed,
            action="PERSIST" if allowed else "REJECT",
            reasons=reasons,
            normalized_scope_type=scope,
            normalized_memory_type=memory_type,
        )

    def describe(self) -> dict:
        return {
            "allowedScopes": sorted(MEMORY_SCOPE_TYPES),
            "allowedTypes": sorted(MEMORY_TYPES),
            "allowInferredPersistence": self._allow_inferred_persistence,
            "minInferredConfidence": self._min_inferred_confidence,
            "maxContentChars": self._max_content_chars,
            "secretLikeContent": "REJECT",
            "conflictStrategy": "SUPERSEDE_ACTIVE_MEMORY_WITH_SAME_SCOPE_AND_KEY",
        }
