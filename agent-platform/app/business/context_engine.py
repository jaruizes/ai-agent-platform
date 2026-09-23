from __future__ import annotations

import json
from dataclasses import replace
from typing import Any
from uuid import UUID

from app.business.memory_service import MemoryService
from app.domain.context import ContextComponent, ContextSnapshot, EffectiveContext
from app.domain.execution import Command
from app.domain.orchestration import PlanStep


class ContextEngine:
    """Builds a bounded, explainable model context from platform-owned sources."""

    def __init__(
        self,
        memory_service: MemoryService,
        *,
        model_window_tokens: int,
        reserved_output_tokens: int,
        safety_margin_tokens: int,
        max_session_entries: int,
        memory_top_k: int,
        memory_min_score: float = 0.12,
        min_compression_tokens: int = 128,
    ):
        self._memory_service = memory_service
        self._model_window_tokens = model_window_tokens
        self._reserved_output_tokens = reserved_output_tokens
        self._safety_margin_tokens = safety_margin_tokens
        self._max_session_entries = max_session_entries
        self._memory_top_k = memory_top_k
        self._memory_min_score = memory_min_score
        self._min_compression_tokens = min_compression_tokens

    async def build(
        self,
        *,
        execution: dict[str, Any],
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
        system_prompt: str,
        model_profile: str,
        attempt: int = 1,
        additional_memory_scopes: list[tuple[str, str]] | None = None,
        knowledge_context: str = "",
        knowledge_provenance: list[dict[str, Any]] | None = None,
    ) -> EffectiveContext:
        components: list[ContextComponent] = []
        provenance: list[dict[str, Any]] = list(knowledge_provenance or [])

        system_tokens = self._estimate_tokens(system_prompt)
        components.append(
            ContextComponent(
                type="SYSTEM_PROMPT",
                content=system_prompt,
                priority=100,
                mandatory=True,
                token_estimate=system_tokens,
                metadata={"channel": "system"},
            )
        )

        current_payload = {
            "task": step.description,
            "intent": command.intent,
            "input": command.input,
            "context": command.context,
            "instructions": [*command.instructions, *step.instructions],
        }
        current_text = json.dumps(
            current_payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        components.append(
            ContextComponent(
                type="CURRENT_TASK",
                content=current_text,
                priority=100,
                mandatory=True,
                token_estimate=self._estimate_tokens(current_text),
                source_ref=str(execution["id"]),
                metadata={"channel": "user"},
            )
        )

        dependencies = {
            dependency: previous_results.get(dependency)
            for dependency in step.depends_on
            if dependency in previous_results
        }
        if dependencies:
            dependency_text = json.dumps(
                dependencies,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            components.append(
                ContextComponent(
                    type="DEPENDENCY_RESULTS",
                    content=dependency_text,
                    priority=95,
                    mandatory=True,
                    token_estimate=self._estimate_tokens(dependency_text),
                    metadata={
                        "channel": "user",
                        "stepIds": list(dependencies.keys()),
                    },
                )
            )

        session_id = execution.get("session_id")
        scopes: list[tuple[str, str]] = list(additional_memory_scopes or [])
        retrieval_query = self._retrieval_query(command, step, dependencies)
        if session_id:
            session = await self._memory_service.get_session(session_id)
            if session:
                scopes.append(("SESSION", str(session.id)))
                if session.owner_key:
                    scopes.append((session.scope, session.owner_key))

                session_entries = await self._memory_service.session_context(
                    session.id,
                    limit=self._max_session_entries * 3,
                )
                previous_entries = [
                    entry
                    for entry in session_entries
                    if entry.execution_id != execution["id"]
                ][-self._max_session_entries :]
                for entry in previous_entries:
                    compact = self._compact_session_entry(entry)
                    components.append(
                        ContextComponent(
                            type="SESSION_CONTEXT",
                            content=compact,
                            priority=self._session_priority(entry.entry_type),
                            mandatory=False,
                            source_ref=str(entry.id),
                            token_estimate=self._estimate_tokens(compact),
                            metadata={
                                "channel": "user",
                                "executionId": str(entry.execution_id),
                                "entryType": entry.entry_type,
                                "createdAt": (
                                    entry.created_at.isoformat()
                                    if entry.created_at
                                    else None
                                ),
                            },
                        )
                    )
                    provenance.append(
                        {
                            "type": "WORKING_CONTEXT",
                            "id": str(entry.id),
                            "executionId": str(entry.execution_id),
                            "entryType": entry.entry_type,
                        }
                    )

        scopes = list(dict.fromkeys(scopes))

        memories = await self._memory_service.retrieve_relevant(
            query=retrieval_query,
            scopes=scopes,
            limit=min(50, max(self._memory_top_k * 3, self._memory_top_k)),
        )
        memories = [
            memory
            for memory in memories
            if float(memory.metadata.get("relevanceScore") or 0.0)
            >= self._memory_min_score
        ][: self._memory_top_k]
        for memory in memories:
            memory_text = (
                f"[{memory.memory_type}] "
                + (f"{memory.memory_key}: " if memory.memory_key else "")
                + memory.content
            )
            components.append(
                ContextComponent(
                    type="MEMORY",
                    content=memory_text,
                    priority=78,
                    mandatory=False,
                    source_ref=str(memory.id),
                    token_estimate=self._estimate_tokens(memory_text),
                    metadata={
                        "channel": "user",
                        "scopeType": memory.scope_type,
                        "scopeId": memory.scope_id,
                        "memoryType": memory.memory_type,
                        "key": memory.memory_key,
                        "confidence": memory.confidence,
                        "importance": memory.importance,
                        "relevanceScore": memory.metadata.get("relevanceScore"),
                        "retrievalScore": memory.metadata.get("retrievalScore"),
                    },
                )
            )
            provenance.append(
                {
                    "type": "MEMORY",
                    "id": str(memory.id),
                    "scopeType": memory.scope_type,
                    "scopeId": memory.scope_id,
                    "memoryType": memory.memory_type,
                }
            )

        if knowledge_context.strip():
            components.append(
                ContextComponent(
                    type="KNOWLEDGE",
                    content=knowledge_context,
                    priority=85,
                    mandatory=False,
                    token_estimate=self._estimate_tokens(knowledge_context),
                    metadata={"channel": "user"},
                )
            )

        budget = {
            "modelWindowTokens": self._model_window_tokens,
            "reservedOutputTokens": self._reserved_output_tokens,
            "safetyMarginTokens": self._safety_margin_tokens,
            "availableInputTokens": max(
                1,
                self._model_window_tokens
                - self._reserved_output_tokens
                - self._safety_margin_tokens,
            ),
            "systemPromptTokens": system_tokens,
        }
        selected, compressed = self._select_components(
            components,
            budget["availableInputTokens"],
        )

        effective_system_prompt = next(
            (
                component.content
                for component in selected
                if component.selected
                and component.metadata.get("channel") == "system"
            ),
            "",
        )
        user_parts = [
            f"## {component.type}\n{component.content}"
            for component in selected
            if component.selected
            and component.metadata.get("channel") != "system"
        ]
        user_prompt = "\n\n".join(user_parts)
        effective_system_tokens = self._estimate_tokens(effective_system_prompt)
        effective_user_tokens = self._estimate_tokens(user_prompt)
        budget = {
            **budget,
            "effectiveSystemPromptTokens": effective_system_tokens,
            "effectiveUserPromptTokens": effective_user_tokens,
        }
        prompt_estimate = effective_system_tokens + effective_user_tokens
        selected_tokens = sum(
            component.token_estimate
            for component in selected
            if component.selected
        )
        original_tokens = sum(
            int(component.metadata.get("originalTokens") or component.token_estimate)
            for component in selected
        )
        dropped_tokens = max(0, original_tokens - selected_tokens)
        selected_refs = {
            component.source_ref
            for component in selected
            if component.selected and component.source_ref
        }
        knowledge_selected = any(
            component.selected and component.type == "KNOWLEDGE"
            for component in selected
        )
        effective_provenance = [
            {
                **item,
                "selected": (
                    knowledge_selected
                    if item.get("type") == "KNOWLEDGE"
                    else (
                        item.get("id") in selected_refs
                        if item.get("id")
                        else True
                    )
                ),
            }
            for item in provenance
        ]

        effective = EffectiveContext(
            system_prompt=effective_system_prompt,
            user_prompt=user_prompt,
            components=selected,
            budget=budget,
            provenance=effective_provenance,
            prompt_token_estimate=prompt_estimate,
            selected_token_estimate=selected_tokens,
            dropped_token_estimate=dropped_tokens,
            compressed=compressed,
        )
        await self._memory_service.save_context_snapshot(
            ContextSnapshot(
                execution_id=UUID(str(execution["id"])),
                step_id=step.id,
                attempt=max(1, attempt),
                model_profile=model_profile,
                budget=effective.budget,
                components=[self._component_dict(item) for item in selected],
                provenance=effective.provenance,
                prompt_token_estimate=effective.prompt_token_estimate,
                selected_token_estimate=effective.selected_token_estimate,
                dropped_token_estimate=effective.dropped_token_estimate,
                compressed=effective.compressed,
            )
        )
        return effective

    def _select_components(
        self,
        components: list[ContextComponent],
        available_tokens: int,
    ) -> tuple[list[ContextComponent], bool]:
        ordered = sorted(
            enumerate(components),
            key=lambda item: (
                not item[1].mandatory,
                -item[1].priority,
                item[0],
            ),
        )
        remaining = available_tokens
        result: dict[int, ContextComponent] = {}
        compressed_any = False

        for index, component in ordered:
            estimate = max(1, component.token_estimate)
            if estimate <= remaining:
                result[index] = component
                remaining -= estimate
                continue

            if component.mandatory:
                if remaining <= 0:
                    raise ValueError(
                        "Mandatory execution context exceeds the configured model budget"
                    )
                compressed = self._truncate(component, remaining)
                result[index] = compressed
                remaining -= compressed.token_estimate
                compressed_any = True
                continue

            if remaining >= self._min_compression_tokens and component.priority >= 70:
                compressed = self._truncate(component, remaining)
                result[index] = compressed
                remaining -= compressed.token_estimate
                compressed_any = True
            else:
                result[index] = replace(
                    component,
                    selected=False,
                    action="DROP_BUDGET",
                )

        return [result[index] for index in range(len(components))], compressed_any

    def _truncate(
        self,
        component: ContextComponent,
        token_budget: int,
    ) -> ContextComponent:
        char_budget = max(1, token_budget * 4)
        suffix = "\n...[compressed by Context Budget Manager]"
        content = component.content
        if len(content) > char_budget:
            usable = max(1, char_budget - len(suffix))
            content = content[:usable] + suffix
        return replace(
            component,
            content=content,
            token_estimate=min(
                token_budget,
                self._estimate_tokens(content),
            ),
            selected=True,
            action="COMPRESS_TRUNCATE",
            metadata={**component.metadata, "originalTokens": component.token_estimate},
        )

    @staticmethod
    def _compact_session_entry(entry) -> str:
        payload = {
            "type": entry.entry_type,
            "key": entry.entry_key,
            "content": entry.content,
        }
        serialized = json.dumps(payload, ensure_ascii=False, default=str)
        if len(serialized) > 12000:
            serialized = serialized[:12000] + "...[session context compacted]"
        return serialized

    @staticmethod
    def _session_priority(entry_type: str) -> int:
        return {
            "SUMMARY": 74,
            "FACT": 72,
            "INSTRUCTION": 70,
            "STEP_RESULT": 62,
            "TOOL_RESULT": 58,
            "KNOWLEDGE": 55,
            "PLAN": 48,
            "COMMAND": 50,
        }.get(entry_type, 45)

    @staticmethod
    def _retrieval_query(
        command: Command,
        step: PlanStep,
        dependencies: dict[str, Any],
    ) -> str:
        payload = {
            "intent": command.intent,
            "task": step.description,
            "input": command.input,
            "dependencySummaries": {
                key: (
                    value.get("summary")
                    if isinstance(value, dict)
                    else str(value)
                )
                for key, value in dependencies.items()
            },
        }
        return json.dumps(payload, ensure_ascii=False, default=str)[:4000]

    @staticmethod
    def _estimate_tokens(value: str) -> int:
        return max(1, len(value) // 4)

    @staticmethod
    def _component_dict(item: ContextComponent) -> dict[str, Any]:
        return {
            "type": item.type,
            "priority": item.priority,
            "mandatory": item.mandatory,
            "sourceRef": item.source_ref,
            "tokenEstimate": item.token_estimate,
            "selected": item.selected,
            "action": item.action,
            "metadata": item.metadata,
        }
