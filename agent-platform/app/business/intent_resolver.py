import json

from app.domain.execution import Command, ExecutionPlan


class IntentResolver:
    """
    M0 intent resolver.

    M0 deliberately has a single execution strategy: DIRECT_LLM.
    The resolver is isolated here so future milestones can decide dynamically
    between direct model calls, tools, agents, RAG or multi-step plans without
    changing the external ExecutionCommand contract.
    """

    def resolve(self, command: Command) -> ExecutionPlan:
        normalized_intent = command.intent.strip()
        system_prompt = (
            "You are the direct execution strategy of a generic AI agent platform. "
            "Fulfil the user's intent using only the information supplied. "
            "Do not invent missing business facts. Return a useful, concise result."
        )
        user_payload = {
            "commandName": command.name,
            "intent": normalized_intent,
            "input": command.input,
            "context": command.context,
            "instructions": command.instructions,
        }
        return ExecutionPlan(
            system_prompt=system_prompt,
            user_prompt=json.dumps(user_payload, ensure_ascii=False, indent=2),
        )
