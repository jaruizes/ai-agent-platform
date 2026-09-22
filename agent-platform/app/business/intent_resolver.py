import json
from typing import Any

from app.business.knowledge_service import KnowledgeService
from app.business.ports import CatalogRepositoryPort, ModelGatewayPort
from app.business.prompt_service import PromptService
from app.business.tool_service import ToolService
from app.domain.catalog import Agent
from app.domain.execution import Command, ExecutionPlan
from app.domain.knowledge import KnowledgeBase
from app.domain.tool import Tool


class IntentResolver:
    def __init__(
        self,
        catalog: CatalogRepositoryPort,
        prompt_service: PromptService,
        tool_service: ToolService,
        knowledge_service: KnowledgeService,
        model_gateway: ModelGatewayPort,
        *,
        router_model_profile: str,
        execution_model_profile: str,
    ):
        self._catalog = catalog
        self._prompt_service = prompt_service
        self._tool_service = tool_service
        self._knowledge_service = knowledge_service
        self._model_gateway = model_gateway
        self._router_model_profile = router_model_profile
        self._execution_model_profile = execution_model_profile

    async def resolve(self, command: Command) -> ExecutionPlan:
        agents = await self._catalog.list_agents(enabled_only=True)
        tools = await self._tool_service.list_tools(enabled_only=True)
        knowledge_bases = await self._knowledge_service.list_knowledge_bases(enabled_only=True)
        agent_knowledge = {
            str(agent.id): await self._knowledge_service.list_agent_knowledge_bases(agent.id)
            for agent in agents
        }

        decision = await self._route(
            command, agents, tools, knowledge_bases, agent_knowledge
        )

        strategy = decision.get("strategy", "DIRECT_LLM")
        agent = self._find_agent(decision.get("agent"), agents)
        tool = self._find_tool(decision.get("tool"), tools)
        tool_arguments = decision.get("toolArguments") or {}
        selected_kbs = self._valid_knowledge_names(
            decision.get("knowledgeBases") or [],
            knowledge_bases,
        )
        usage_mode = str(decision.get("knowledgeUsageMode") or "REFERENCE").upper()
        if usage_mode not in {"REFERENCE", "GUARDRAIL"}:
            usage_mode = "REFERENCE"

        if strategy in {"AGENT_RAG_LLM", "AGENT_TOOL_RAG_LLM"} and agent and not selected_kbs:
            assigned = agent_knowledge.get(str(agent.id), [])
            selected_kbs = [item["knowledgeBase"].name for item in assigned]
            if any(item["usageMode"] == "GUARDRAIL" for item in assigned):
                usage_mode = "GUARDRAIL"

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

        if strategy == "RAG_LLM" and selected_kbs:
            prompt = await self._prompt_service.get_by_name("knowledge-executor")
            return ExecutionPlan(
                strategy="RAG_LLM",
                system_prompt=prompt.content,
                user_prompt=self._user_payload(command),
                knowledge_base_names=selected_kbs,
                knowledge_usage_mode=usage_mode,
                model_profile=self._execution_model_profile,
            )

        if strategy == "AGENT_RAG_LLM" and agent and selected_kbs:
            return await self._agent_knowledge_plan(
                command, agent, selected_kbs, usage_mode, "AGENT_RAG_LLM"
            )

        if strategy == "AGENT_TOOL_RAG_LLM" and agent and tool and selected_kbs:
            return await self._agent_knowledge_plan(
                command,
                agent,
                selected_kbs,
                usage_mode,
                "AGENT_TOOL_RAG_LLM",
                tool_name=tool.name,
                tool_arguments=tool_arguments,
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

    async def _agent_knowledge_plan(
        self,
        command: Command,
        agent: Agent,
        knowledge_base_names: list[str],
        usage_mode: str,
        strategy: str,
        *,
        tool_name: str | None = None,
        tool_arguments: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
        prompt = await self._prompt_service.get_by_name("agent-knowledge-executor")
        return ExecutionPlan(
            strategy=strategy,
            agent_name=agent.name,
            tool_name=tool_name,
            tool_arguments=tool_arguments or {},
            system_prompt=prompt.content.format(
                agent_name=agent.name,
                agent_description=agent.description,
                agent_instructions=agent.instructions,
                skills=self._skills_text(agent) or "No skills assigned.",
            ),
            user_prompt=self._user_payload(command),
            knowledge_base_names=knowledge_base_names,
            knowledge_usage_mode=usage_mode,
            model_profile=self._execution_model_profile,
        )

    async def _route(
        self,
        command: Command,
        agents: list[Agent],
        tools: list[Tool],
        knowledge_bases: list[KnowledgeBase],
        agent_knowledge: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        routing_prompt = await self._prompt_service.get_by_name("intent-router-knowledge-v1")
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
    def _valid_knowledge_names(
        names: list[str],
        knowledge_bases: list[KnowledgeBase],
    ) -> list[str]:
        available = {kb.name for kb in knowledge_bases}
        return [name for name in names if name in available]

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
                "knowledgeBases": [],
                "knowledgeUsageMode": "REFERENCE",
            }
