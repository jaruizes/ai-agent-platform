from __future__ import annotations

import json
import re
from typing import Any

from app.business.knowledge_service import KnowledgeService
from app.business.ports import CatalogRepositoryPort, ExecutionRepositoryPort, ModelGatewayPort
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.domain.execution import Command
from app.domain.orchestration import PlanStep


_PLACEHOLDER = re.compile(r"^\$\{([^}]+)\}$")


class StepExecutor:
    def __init__(
        self,
        *,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        tool_service: ToolService,
        knowledge_service: KnowledgeService,
        model_gateway: ModelGatewayPort,
        execution_repository: ExecutionRepositoryPort,
        execution_model_profile: str,
        knowledge_top_k: int,
        max_context_chars: int,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._knowledge_service = knowledge_service
        self._model_gateway = model_gateway
        self._repository = execution_repository
        self._execution_model_profile = execution_model_profile
        self._knowledge_top_k = knowledge_top_k
        self._max_context_chars = max_context_chars

    async def execute(
        self,
        *,
        execution: dict[str, Any],
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        await self._repository.mark_step_started(
            execution,
            step_id=step.id,
            detail={
                "type": step.type,
                "description": step.description,
                "agent": step.agent_name,
                "tool": step.tool_name,
            },
        )
        try:
            if step.type == "TOOL":
                result = await self._tool_step(command, step, previous_results)
            elif step.type == "KNOWLEDGE":
                result = await self._knowledge_step(command, step, previous_results)
            elif step.type == "AGENT":
                result = await self._agent_step(command, step, previous_results)
            elif step.type == "VALIDATE":
                result = await self._validation_step(command, step, previous_results)
            else:
                result = await self._model_step(command, step, previous_results)

            await self._repository.mark_step_completed(
                execution,
                step_id=step.id,
                output=result,
                usage=result.get("usage") or {},
            )
            return result
        except Exception as exc:
            error = {
                "type": type(exc).__name__,
                "message": str(exc)[:4000],
            }
            await self._repository.mark_step_failed(
                execution,
                step_id=step.id,
                error=error,
            )
            raise

    async def _tool_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        arguments = self._resolve_value(
            step.tool_arguments,
            command=command,
            previous_results=previous_results,
        )
        output = await self._tool_service.execute(step.tool_name, arguments)
        return {
            "summary": f"Tool '{step.tool_name}' completed.",
            "output": output,
            "usage": {},
            "agent": None,
            "tool": step.tool_name,
        }

    async def _knowledge_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        query = self._reasoning_input(command, step, previous_results)
        hits = await self._knowledge_service.retrieve(
            query=query,
            knowledge_base_names=step.knowledge_base_names,
            top_k=self._knowledge_top_k,
        )
        return {
            "summary": f"Retrieved {len(hits)} knowledge chunks.",
            "output": {
                "knowledgeBases": step.knowledge_base_names,
                "usageMode": step.knowledge_usage_mode,
                "hits": [
                    {
                        "chunkId": str(hit.chunk_id),
                        "documentId": str(hit.document_id),
                        "documentName": hit.document_name,
                        "score": hit.score,
                        "metadata": hit.metadata,
                        "content": hit.content,
                    }
                    for hit in hits
                ],
            },
            "usage": {},
            "agent": None,
            "tool": None,
        }

    async def _agent_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        agent = await self._catalog.get_agent_by_name(step.agent_name)
        if not agent or not agent.enabled:
            raise LookupError(f"Agent '{step.agent_name}' not found or disabled")

        knowledge_context = ""
        if step.knowledge_base_names:
            hits = await self._knowledge_service.retrieve(
                query=self._reasoning_input(command, step, previous_results),
                knowledge_base_names=step.knowledge_base_names,
                top_k=self._knowledge_top_k,
            )
            knowledge_context = (
                "\n\nManaged knowledge:\n"
                + self._knowledge_service.format_context(hits)
            )

        prompt = await self._prompt_service.get_by_name(
            "agent-knowledge-executor"
            if step.knowledge_base_names
            else "agent-executor"
        )
        system_prompt = prompt.content.format(
            agent_name=agent.name,
            agent_description=agent.description,
            agent_instructions=agent.instructions,
            skills=self._skills_text(agent),
        )
        detail = await self._model_gateway.complete_detailed(
            system_prompt=system_prompt,
            user_prompt=(
                self._reasoning_input(command, step, previous_results)
                + knowledge_context
            ),
            model_profile=self._execution_model_profile,
            temperature=0.2,
        )
        return {
            "summary": detail["content"],
            "output": {"content": detail["content"]},
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "agent": agent.name,
            "tool": None,
        }

    async def _model_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = await self._prompt_service.get_by_name("direct-executor")
        detail = await self._model_gateway.complete_detailed(
            system_prompt=prompt.content,
            user_prompt=self._reasoning_input(command, step, previous_results),
            model_profile=self._execution_model_profile,
            temperature=0.2,
        )
        return {
            "summary": detail["content"],
            "output": {"content": detail["content"]},
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "agent": None,
            "tool": None,
        }

    async def _validation_step(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        hits = await self._knowledge_service.retrieve(
            query=self._reasoning_input(command, step, previous_results),
            knowledge_base_names=step.knowledge_base_names,
            top_k=self._knowledge_top_k,
        )
        prompt = await self._prompt_service.get_by_name("validation-executor")
        detail = await self._model_gateway.complete_detailed(
            system_prompt=prompt.content,
            user_prompt=(
                self._reasoning_input(command, step, previous_results)
                + "\n\nKnowledge usage mode: "
                + step.knowledge_usage_mode
                + "\n\nManaged knowledge:\n"
                + self._knowledge_service.format_context(hits)
            ),
            model_profile=self._execution_model_profile,
            temperature=0.0,
        )
        return {
            "summary": detail["content"],
            "output": {
                "content": detail["content"],
                "knowledgeBases": step.knowledge_base_names,
                "knowledgeHits": [
                    {
                        "chunkId": str(hit.chunk_id),
                        "documentId": str(hit.document_id),
                        "documentName": hit.document_name,
                        "score": hit.score,
                    }
                    for hit in hits
                ],
            },
            "usage": detail.get("usage") or {},
            "model": detail.get("model"),
            "modelProfile": detail.get("modelProfile"),
            "agent": None,
            "tool": None,
        }

    def _reasoning_input(
        self,
        command: Command,
        step: PlanStep,
        previous_results: dict[str, Any],
    ) -> str:
        dependencies = {
            dependency: previous_results.get(dependency)
            for dependency in step.depends_on
        }
        payload = {
            "task": step.description,
            "intent": command.intent,
            "input": command.input,
            "context": command.context,
            "instructions": [*command.instructions, *step.instructions],
            "dependencyResults": dependencies,
        }
        serialized = json.dumps(payload, ensure_ascii=False, indent=2)
        if len(serialized) > self._max_context_chars:
            raise ValueError(
                "Planned step context is too large to inject safely into the model: "
                f"{len(serialized)} characters > {self._max_context_chars}"
            )
        return serialized

    def _resolve_value(
        self,
        value: Any,
        *,
        command: Command,
        previous_results: dict[str, Any],
    ) -> Any:
        if isinstance(value, dict):
            return {
                key: self._resolve_value(
                    item,
                    command=command,
                    previous_results=previous_results,
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve_value(
                    item,
                    command=command,
                    previous_results=previous_results,
                )
                for item in value
            ]
        if not isinstance(value, str):
            return value

        match = _PLACEHOLDER.match(value)
        if not match:
            return value

        path = match.group(1).split(".")
        root: Any = {
            "command": {
                "input": command.input,
                "context": command.context,
                "intent": command.intent,
            },
            "steps": previous_results,
        }
        for part in path:
            if isinstance(root, list):
                root = root[int(part)]
            elif isinstance(root, dict) and part in root:
                root = root[part]
            else:
                raise ValueError(f"Cannot resolve plan placeholder '{value}'")
        return root

    @staticmethod
    def _skills_text(agent) -> str:
        value = "\n\n".join(
            f"### Skill: {skill.name}\n{skill.description}\n\n{skill.instructions}"
            for skill in agent.skills
            if skill.enabled
        )
        return value or "No skills assigned."
