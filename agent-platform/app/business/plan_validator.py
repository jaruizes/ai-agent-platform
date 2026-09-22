from __future__ import annotations

from collections import defaultdict, deque
import re

from app.domain.orchestration import LogicalPlan, PlanValidation


_STEP_REFERENCE = re.compile(r"^\$\{steps\.([^.}]+)(?:\.|})")


class PlanValidator:
    def __init__(self, *, max_steps: int = 12):
        self._max_steps = max_steps

    def validate(
        self,
        plan: LogicalPlan,
        *,
        agent_names: set[str],
        tool_names: set[str],
        knowledge_base_names: set[str],
    ) -> PlanValidation:
        errors: list[str] = []
        warnings: list[str] = []

        if not plan.steps:
            errors.append("Plan must contain at least one step")
            return PlanValidation(False, errors, warnings)

        if len(plan.steps) > self._max_steps:
            errors.append(
                f"Plan has {len(plan.steps)} steps; maximum is {self._max_steps}"
            )

        ids = [step.id for step in plan.steps]
        if len(ids) != len(set(ids)):
            errors.append("Step ids must be unique")
        id_set = set(ids)

        if plan.final_step_id not in id_set:
            errors.append(f"finalStepId '{plan.final_step_id}' does not exist")

        allowed_types = {"AGENT", "TOOL", "KNOWLEDGE", "MODEL", "VALIDATE"}

        for step in plan.steps:
            if step.type not in allowed_types:
                errors.append(
                    f"Step '{step.id}' has unsupported type '{step.type}'"
                )
            if not step.id or any(ch.isspace() for ch in step.id):
                errors.append(f"Invalid step id '{step.id}'")
            if step.id in step.depends_on:
                errors.append(f"Step '{step.id}' cannot depend on itself")
            for dependency in step.depends_on:
                if dependency not in id_set:
                    errors.append(
                        f"Step '{step.id}' depends on unknown step '{dependency}'"
                    )

            if step.type == "AGENT":
                if not step.agent_name:
                    errors.append(f"AGENT step '{step.id}' requires agent")
                elif step.agent_name not in agent_names:
                    errors.append(
                        f"AGENT step '{step.id}' references unknown/disabled agent "
                        f"'{step.agent_name}'"
                    )
            elif step.agent_name:
                warnings.append(
                    f"Step '{step.id}' declares agent '{step.agent_name}' but type is {step.type}"
                )

            if step.type == "TOOL":
                if not step.tool_name:
                    errors.append(f"TOOL step '{step.id}' requires tool")
                elif step.tool_name not in tool_names:
                    errors.append(
                        f"TOOL step '{step.id}' references unknown/disabled tool "
                        f"'{step.tool_name}'"
                    )
                for referenced_step in self._step_references(step.tool_arguments):
                    if referenced_step not in id_set:
                        errors.append(
                            f"TOOL step '{step.id}' argument references unknown step "
                            f"'{referenced_step}'"
                        )
                    elif referenced_step not in step.depends_on:
                        errors.append(
                            f"TOOL step '{step.id}' references output from "
                            f"'{referenced_step}' but does not depend on it"
                        )
            elif step.tool_name:
                warnings.append(
                    f"Step '{step.id}' declares tool '{step.tool_name}' but type is {step.type}"
                )

            if step.type in {"KNOWLEDGE", "VALIDATE"} and not step.knowledge_base_names:
                errors.append(
                    f"{step.type} step '{step.id}' requires at least one Knowledge Base"
                )

            for kb_name in step.knowledge_base_names:
                if kb_name not in knowledge_base_names:
                    errors.append(
                        f"Step '{step.id}' references unknown/disabled Knowledge Base "
                        f"'{kb_name}'"
                    )

            if step.knowledge_usage_mode not in {"REFERENCE", "GUARDRAIL"}:
                errors.append(
                    f"Step '{step.id}' has invalid knowledgeUsageMode "
                    f"'{step.knowledge_usage_mode}'"
                )

            if step.timeout_seconds <= 0 or step.timeout_seconds > 3600:
                errors.append(
                    f"Step '{step.id}' timeoutSeconds must be in (0, 3600]"
                )

            retry = step.retry_policy or {}
            max_attempts = int(retry.get("maxAttempts", 3))
            initial_backoff = float(retry.get("initialBackoffSeconds", 1.0))
            max_backoff = float(retry.get("maxBackoffSeconds", 30.0))
            multiplier = float(retry.get("multiplier", 2.0))
            if max_attempts < 1 or max_attempts > 10:
                errors.append(
                    f"Step '{step.id}' maxAttempts must be between 1 and 10"
                )
            if initial_backoff < 0 or max_backoff < 0:
                errors.append(
                    f"Step '{step.id}' backoff values must be non-negative"
                )
            if max_backoff < initial_backoff:
                errors.append(
                    f"Step '{step.id}' maxBackoffSeconds must be >= initialBackoffSeconds"
                )
            if multiplier < 1.0 or multiplier > 10.0:
                errors.append(
                    f"Step '{step.id}' retry multiplier must be between 1 and 10"
                )
            if step.requires_approval and not step.approval_reason:
                warnings.append(
                    f"Step '{step.id}' requires approval without an approvalReason"
                )
            if step.type == "VALIDATE" and step.knowledge_usage_mode != "GUARDRAIL":
                warnings.append(
                    f"VALIDATE step '{step.id}' normally should use GUARDRAIL knowledge"
                )

        if not errors and self._has_cycle(plan):
            errors.append("Plan dependency graph contains a cycle")

        if not errors and plan.final_step_id:
            final_dependents = [
                step.id
                for step in plan.steps
                if plan.final_step_id in step.depends_on
            ]
            if final_dependents:
                errors.append(
                    f"finalStepId '{plan.final_step_id}' has dependent steps: "
                    + ", ".join(sorted(final_dependents))
                )

        if not errors and plan.final_step_id:
            contributing = self._ancestors(plan, plan.final_step_id)
            unused = id_set - contributing - {plan.final_step_id}
            if unused:
                warnings.append(
                    "Steps not contributing to finalStepId: " + ", ".join(sorted(unused))
                )

        return PlanValidation(not errors, errors, warnings)

    @classmethod
    def _step_references(cls, value) -> set[str]:
        references: set[str] = set()
        if isinstance(value, dict):
            for item in value.values():
                references.update(cls._step_references(item))
        elif isinstance(value, list):
            for item in value:
                references.update(cls._step_references(item))
        elif isinstance(value, str):
            match = _STEP_REFERENCE.match(value)
            if match:
                references.add(match.group(1))
        return references

    @staticmethod
    def _has_cycle(plan: LogicalPlan) -> bool:
        indegree = {step.id: 0 for step in plan.steps}
        children: dict[str, list[str]] = defaultdict(list)
        for step in plan.steps:
            for dependency in step.depends_on:
                indegree[step.id] += 1
                children[dependency].append(step.id)

        queue = deque(step_id for step_id, count in indegree.items() if count == 0)
        visited = 0
        while queue:
            current = queue.popleft()
            visited += 1
            for child in children[current]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        return visited != len(plan.steps)

    @staticmethod
    def _ancestors(plan: LogicalPlan, target: str) -> set[str]:
        by_id = {step.id: step for step in plan.steps}
        result: set[str] = set()
        stack = list(by_id[target].depends_on)
        while stack:
            current = stack.pop()
            if current in result:
                continue
            result.add(current)
            stack.extend(by_id[current].depends_on)
        return result
