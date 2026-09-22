import json
from typing import Any

from app.business.ports import CatalogRepositoryPort, ModelGatewayPort
from app.business.prompt_service import PromptService
from app.domain.catalog import Agent
from app.domain.execution import Command, ExecutionPlan


class IntentResolver:
    def __init__(
        self,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        model_gateway: ModelGatewayPort,
        *,
        router_model_profile: str,
        execution_model_profile: str,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._model_gateway = model_gateway
        self._router_model_profile = router_model_profile
        self._execution_model_profile = execution_model_profile

    async def resolve(self, command: Command) -> ExecutionPlan:
        agents = await self._catalog.list_agents(enabled_only=True)
        selected = await self._select_agent(command, agents)

        if selected is None:
            prompt = await self._prompt_service.get_by_name("direct-executor")
            return ExecutionPlan(
                strategy="DIRECT_LLM",
                system_prompt=prompt.content,
                user_prompt=self._user_payload(command),
                model_profile=self._execution_model_profile,
            )

        prompt = await self._prompt_service.get_by_name("agent-executor")
        skills_text = "\n\n".join(
            f"### Skill: {skill.name}\n{skill.description}\n\n{skill.instructions}"
            for skill in selected.skills
            if skill.enabled
        )
        system_prompt = prompt.content.format(
            agent_name=selected.name,
            agent_description=selected.description,
            agent_instructions=selected.instructions,
            skills=skills_text or "No skills assigned.",
        )
        return ExecutionPlan(
            strategy="AGENT",
            agent_name=selected.name,
            system_prompt=system_prompt,
            user_prompt=self._user_payload(command),
            model_profile=self._execution_model_profile,
        )

    async def _select_agent(self, command: Command, agents: list[Agent]) -> Agent | None:
        if not agents:
            return None

        available = [
            {
                "name": agent.name,
                "description": agent.description,
                "skills": [
                    {"name": skill.name, "description": skill.description}
                    for skill in agent.skills
                    if skill.enabled
                ],
            }
            for agent in agents
        ]

        routing_prompt = await self._prompt_service.get_by_name("intent-router")
        raw = await self._model_gateway.complete(
            system_prompt=routing_prompt.content,
            user_prompt=json.dumps(
                {
                    "command": {
                        "name": command.name,
                        "intent": command.intent,
                        "input": command.input,
                        "context": command.context,
                        "instructions": command.instructions,
                    },
                    "availableAgents": available,
                },
                ensure_ascii=False,
            ),
            model_profile=self._router_model_profile,
            temperature=0.0,
        )
        decision = self._parse_json(raw)
        if decision.get("strategy") != "AGENT":
            return None

        selected_name = decision.get("agent")
        return next((agent for agent in agents if agent.name == selected_name), None)

    @staticmethod
    def _user_payload(command: Command) -> str:
        return json.dumps(
            {
                "commandName": command.name,
                "intent": command.intent.strip(),
                "input": command.input,
                "context": command.context,
                "instructions": command.instructions,
            },
            ensure_ascii=False,
            indent=2,
        )

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"strategy": "DIRECT_LLM", "agent": None}
