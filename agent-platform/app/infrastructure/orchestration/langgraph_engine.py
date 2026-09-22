from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.business.ports import ExecutionRepositoryPort
from app.business.step_executor import StepExecutor
from app.domain.execution import Command
from app.domain.orchestration import LogicalPlan, PlanStep


def _merge_results(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class OrchestrationState(TypedDict):
    results: Annotated[dict[str, Any], _merge_results]


class LangGraphOrchestrationEngine:
    def __init__(
        self,
        *,
        step_executor: StepExecutor,
        execution_repository: ExecutionRepositoryPort,
    ):
        self._step_executor = step_executor
        self._repository = execution_repository

    async def execute(
        self,
        *,
        execution: dict[str, Any],
        command: Command,
        plan: LogicalPlan,
    ) -> dict[str, Any]:
        await self._repository.mark_plan_running(execution)
        graph = StateGraph(OrchestrationState)

        for step in plan.steps:
            graph.add_node(
                step.id,
                self._node(
                    execution=execution,
                    command=command,
                    step=step,
                ),
            )

        for step in plan.steps:
            if step.depends_on:
                graph.add_edge(step.depends_on, step.id)
            else:
                graph.add_edge(START, step.id)

        graph.add_edge(plan.final_step_id, END)
        compiled = graph.compile()

        try:
            state = await compiled.ainvoke({"results": {}})
            final = state.get("results", {}).get(plan.final_step_id)
            if not final:
                raise RuntimeError(
                    f"Final plan step '{plan.final_step_id}' did not produce a result"
                )
            await self._repository.mark_plan_completed(execution)
        except Exception:
            await self._repository.mark_plan_failed(execution)
            raise
        return {
            "final": final,
            "stepResults": state.get("results", {}),
        }

    def _node(
        self,
        *,
        execution: dict[str, Any],
        command: Command,
        step: PlanStep,
    ):
        async def execute_step(state: OrchestrationState) -> dict[str, Any]:
            result = await self._step_executor.execute(
                execution=execution,
                command=command,
                step=step,
                previous_results=state.get("results", {}),
            )
            return {"results": {step.id: result}}

        return execute_step
