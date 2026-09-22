from __future__ import annotations

import json
from typing import Any

from app.business.knowledge_service import KnowledgeService
from app.business.plan_validator import PlanValidator
from app.business.ports import CatalogRepositoryPort, ModelGatewayPort
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.domain.execution import Command
from app.domain.orchestration import LogicalPlan, PlanStep, PlanValidation


class PlannerService:
    def __init__(
        self,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        tool_service: ToolService,
        knowledge_service: KnowledgeService,
        model_gateway: ModelGatewayPort,
        validator: PlanValidator,
        *,
        planner_model_profile: str,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._knowledge_service = knowledge_service
        self._model_gateway = model_gateway
        self._validator = validator
        self._planner_model_profile = planner_model_profile

    async def plan(
        self,
        command: Command,
    ) -> tuple[LogicalPlan, PlanValidation, dict[str, Any]]:
        agents = await self._catalog.list_agents(enabled_only=True)
        tools = await self._tool_service.list_tools(enabled_only=True)
        knowledge_bases = await self._knowledge_service.list_knowledge_bases(
            enabled_only=True
        )
        agent_knowledge = {
            str(agent.id): await self._knowledge_service.list_agent_knowledge_bases(
                agent.id
            )
            for agent in agents
        }

        prompt = await self._prompt_service.get_by_name("planner-v1")
        detail = await self._model_gateway.complete_detailed(
            system_prompt=prompt.content,
            user_prompt=json.dumps(
                {
                    "command": {
                        "name": command.name,
                        "intent": command.intent,
                        "input": command.input,
                        "context": command.context,
                        "instructions": command.instructions,
                    },
                    "availableAgents": [
                        {
                            "name": agent.name,
                            "description": agent.description,
                            "skills": [
                                {
                                    "name": skill.name,
                                    "description": skill.description,
                                }
                                for skill in agent.skills
                                if skill.enabled
                            ],
                            "knowledgeBases": [
                                {
                                    "name": item["knowledgeBase"].name,
                                    "description": item["knowledgeBase"].description,
                                    "usageMode": item["usageMode"],
                                }
                                for item in agent_knowledge.get(str(agent.id), [])
                            ],
                        }
                        for agent in agents
                    ],
                    "availableTools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "instructions": tool.instructions,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in tools
                    ],
                    "availableKnowledgeBases": [
                        {
                            "name": kb.name,
                            "description": kb.description,
                            "scope": kb.scope,
                            "metadata": kb.metadata,
                        }
                        for kb in knowledge_bases
                    ],
                },
                ensure_ascii=False,
            ),
            model_profile=self._planner_model_profile,
            temperature=0.0,
        )
        plan = self._parse_plan(detail["content"])
        validation = self._validator.validate(
            plan,
            agent_names={agent.name for agent in agents},
            tool_names={tool.name for tool in tools},
            knowledge_base_names={kb.name for kb in knowledge_bases},
        )
        return plan, validation, detail

    @classmethod
    def _parse_plan(cls, raw: str) -> LogicalPlan:
        payload = cls._parse_json(raw)
        steps = []
        for item in payload.get("steps") or []:
            steps.append(
                PlanStep(
                    id=str(item.get("id") or "").strip(),
                    type=str(item.get("type") or "MODEL").upper(),
                    description=str(item.get("description") or "").strip()
                    or "Execute planned step",
                    depends_on=[
                        str(value) for value in (item.get("dependsOn") or [])
                    ],
                    agent_name=item.get("agent"),
                    tool_name=item.get("tool"),
                    tool_arguments=item.get("toolArguments") or {},
                    knowledge_base_names=[
                        str(value) for value in (item.get("knowledgeBases") or [])
                    ],
                    knowledge_usage_mode=str(
                        item.get("knowledgeUsageMode") or "REFERENCE"
                    ).upper(),
                    instructions=[
                        str(value) for value in (item.get("instructions") or [])
                    ],
                )
            )

        return LogicalPlan(
            objective=str(payload.get("objective") or "").strip()
            or "Fulfil the requested intent",
            steps=steps,
            final_step_id=str(payload.get("finalStepId") or "").strip(),
        )

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        fence = chr(96) * 3
        if text.startswith(fence):
            text = text.split("\n", 1)[1]
            text = text.rsplit(fence, 1)[0].strip()
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Planner returned invalid JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError("Planner must return a JSON object")
        return value
