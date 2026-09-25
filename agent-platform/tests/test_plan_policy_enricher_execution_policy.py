from uuid import uuid4

from app.business.plan_policy_enricher import PlanPolicyEnricher
from app.domain.orchestration import LogicalPlan, PlanStep
from app.domain.tool import Tool


def test_execution_policy_overrides_planner_retry_and_timeout():
    plan = LogicalPlan(
        objective="Analyse proposal",
        steps=[
            PlanStep(
                id="analyse",
                type="AGENT",
                description="Analyse",
                agent_name="business-analyst",
                timeout_seconds=120,
                retry_policy={
                    "maxAttempts": 2,
                    "initialBackoffSeconds": 1,
                    "maxBackoffSeconds": 30,
                    "multiplier": 2,
                },
            )
        ],
        final_step_id="analyse",
    )

    enriched = PlanPolicyEnricher().apply(
        plan,
        tools=[],
        execution_policy={
            "maxStepAttempts": 1,
            "stepTimeoutSeconds": 480,
        },
    )

    step = enriched.steps[0]
    assert step.retry_policy["maxAttempts"] == 1
    assert step.timeout_seconds == 480


def test_execution_policy_keeps_tool_governance():
    tool = Tool(
        id=uuid4(),
        name="writer",
        description="write",
        instructions="",
        implementation_type="MCP",
        side_effect="WRITE",
        approval_policy="REQUIRED",
    )
    plan = LogicalPlan(
        objective="Write",
        steps=[
            PlanStep(
                id="write",
                type="TOOL",
                description="Write document",
                tool_name="writer",
                timeout_seconds=60,
                retry_policy={"maxAttempts": 3},
            )
        ],
        final_step_id="write",
    )

    enriched = PlanPolicyEnricher().apply(
        plan,
        tools=[tool],
        execution_policy={
            "maxStepAttempts": 1,
            "stepTimeoutSeconds": 480,
        },
    )

    step = enriched.steps[0]
    assert step.retry_policy["maxAttempts"] == 1
    assert step.timeout_seconds == 480
    assert step.requires_approval is True
    assert step.approval_source == "TOOL_POLICY"
