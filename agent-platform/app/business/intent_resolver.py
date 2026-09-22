import json
from typing import Any

from app.business.ports import CatalogRepositoryPort, ModelGatewayPort
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.domain.catalog import Agent
from app.domain.execution import Command, ExecutionPlan
from app.domain.tool import Tool


class IntentResolver:
    def __init__(
        self,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        tool_service: ToolService,
        model_gateway: ModelGatewayPort,
        *,
        router_model_profile: str,
        execution_model_profile: str,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._model_gateway = model_gateway
        self._router_model_profile = router_model_profile
        self._execution_model_profile = execution_model_profile

    async def resolve(self, command: Command) -> ExecutionPlan:
        agents = await self._catalog.list_agents(enabled_only=True)
        tools = await self._tool_service.list_tools(enabled_only=True)
        decision = await self._route(command, agents, tools)

        strategy = decision.get("strategy", "DIRECT_LLM")
        agent = self._find_agent(decision.get("agent"), agents)
        tool = self._find_tool(decision.get("tool"), tools)
        tool_arguments = decision.get("toolArguments") or {}

        if strategy == "DIRECT_LLM":
            prompt = await self._prompt_service.get_by_name("direct-executor")
            return ExecutionPlan(
                strategy="DIRECT_LLM",
                system_prompt=prompt.content,
                user_prompt=self._user_payload(command),
                model_profile=self._execution_model_profile,
            )

        if strategy == "AGENT" and agent:
            return await self._agent_plan(command, agent)

        if strategy == "TOOL" and tool:
            return ExecutionPlan(
                strategy="TOOL",
                system_prompt="",
                user_prompt=self._user_payload(command),
                tool_name=tool.name,
                tool_arguments=tool_arguments,
                model_profile=self._execution_model_profile,
            )

        if strategy == "TOOL_LLM" and tool:
            prompt = await self._prompt_service.get_by_name("tool-result-executor")
            return ExecutionPlan(
                strategy="TOOL_LLM",
                system_prompt=prompt.content,
                user_prompt=self._user_payload(command),
                tool_name=tool.name,
                tool_arguments=tool_arguments,
                model_profile=self._execution_model_profile,
            )

        if strategy == "AGENT_TOOL_LLM" and agent and tool:
            prompt = await self._prompt_service.get_by_name("agent-tool-executor")
            return ExecutionPlan(
                strategy="AGENT_TOOL_LLM",
                agent_name=agent.name,
                tool_name=tool.name,
                tool_arguments=tool_arguments,
                system_prompt=prompt.content.format(
                    agent_name=agent.name,
                    agent_description=agent.description,
                    agent_instructions=agent.instructions,
                    skills=self._skills_text(agent) or "No skills assigned.",
                ),
                user_prompt=self._user_payload(command),
                model_profile=self._execution_model_profile,
            )

        prompt = await self._prompt_service.get_by_name("direct-executor")
        return ExecutionPlan(
            strategy="DIRECT_LLM",
            system_prompt=prompt.content,
            user_prompt=self._user_payload(command),
            model_profile=self._execution_model_profile,
        )

    async def _agent_plan(self, command: Command, agent: Agent) -> ExecutionPlan:
        prompt = await self._prompt_service.get_by_name("agent-executor")
        return ExecutionPlan(
            strategy="AGENT",
            agent_name=agent.name,
            system_prompt=prompt.content.format(
                agent_name=agent.name,
                agent_description=agent.description,
                agent_instructions=agent.instructions,
                skills=self._skills_text(agent) or "No skills assigned.",
            ),
            user_prompt=self._user_payload(command),
            model_profile=self._execution_model_profile,
        )

    async def _route(self, command: Command, agents: list[Agent], tools: list[Tool]) -> dict[str, Any]:
        routing_prompt = await self._prompt_service.get_by_name("intent-router-tools")
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
                    "availableAgents": [
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
                },
                ensure_ascii=False,
            ),
            model_profile=self._router_model_profile,
            temperature=0.0,
        )
        return self._parse_json(raw)

    @staticmethod
    def _find_agent(name: str | None, agents: list[Agent]) -> Agent | None:
        return next((agent for agent in agents if agent.name == name), None)

    @staticmethod
    def _find_tool(name: str | None, tools: list[Tool]) -> Tool | None:
        return next((tool for tool in tools if tool.name == name), None)

    @staticmethod
    def _skills_text(agent: Agent) -> str:
        return "\n\n".join(
            f"### Skill: {skill.name}\n{skill.description}\n\n{skill.instructions}"
            for skill in agent.skills
            if skill.enabled
        )

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
            return {
                "strategy": "DIRECT_LLM",
                "agent": None,
                "tool": None,
                "toolArguments": {},
            }
