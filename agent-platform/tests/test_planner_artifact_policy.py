from app.business.planner_service import PlannerService
from app.domain.execution import Command
from app.domain.orchestration import LogicalPlan, PlanStep, PlanValidation
from app.domain.tool import Tool
from uuid import uuid4


def command(agent_names):
    return Command(
        name="proposal",
        intent="Produce proposal",
        metadata={
            "artifactPolicy": {
                "enabled": True,
                "agentNames": agent_names,
            }
        },
    )


def test_artifact_policy_requires_configured_producer_agent():
    plan = LogicalPlan(
        objective="Produce proposal",
        steps=[
            PlanStep(
                id="analyse",
                type="AGENT",
                description="Analyse",
                agent_name="technology-specialist",
            )
        ],
        final_step_id="analyse",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command(["business-analyst"]),
        [],
    )

    assert result.valid is False
    assert any("authoritative producer AGENT" in item for item in result.errors)


def test_artifact_policy_accepts_configured_producer_on_final_path():
    plan = LogicalPlan(
        objective="Produce proposal",
        steps=[
            PlanStep(
                id="specialist",
                type="AGENT",
                description="Specialist input",
                agent_name="technology-specialist",
            ),
            PlanStep(
                id="synthesis",
                type="AGENT",
                description="Authoritative synthesis",
                agent_name="business-analyst",
                depends_on=["specialist"],
            ),
            PlanStep(
                id="materialize",
                type="TOOL",
                description="Write artifact",
                tool_name="google-docs-create-from-artifact",
                depends_on=["synthesis"],
            ),
        ],
        final_step_id="materialize",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command(["business-analyst"]),
        [],
    )

    assert result.valid is True
    assert result.errors == []


def test_artifact_policy_rejects_disconnected_producer_branch():
    plan = LogicalPlan(
        objective="Produce proposal",
        steps=[
            PlanStep(
                id="configured-producer",
                type="AGENT",
                description="Configured producer",
                agent_name="business-analyst",
            ),
            PlanStep(
                id="other-agent",
                type="AGENT",
                description="Other result",
                agent_name="technology-specialist",
            ),
        ],
        final_step_id="other-agent",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command(["business-analyst"]),
        [],
    )

    assert result.valid is False
    assert any("final result path" in item for item in result.errors)


def test_artifact_policy_without_agent_names_remains_generic():
    plan = LogicalPlan(
        objective="Produce proposal",
        steps=[
            PlanStep(
                id="analyse",
                type="AGENT",
                description="Analyse",
                agent_name="business-analyst",
            )
        ],
        final_step_id="analyse",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command([]),
        [],
    )

    assert result.valid is True


def command_with_write_policy(agent_names, allow_write_tools):
    return Command(
        name="proposal",
        intent="Produce proposal",
        metadata={
            "artifactPolicy": {
                "enabled": True,
                "agentNames": agent_names,
                "allowWriteTools": allow_write_tools,
            }
        },
    )


def test_artifact_policy_rejects_multiple_authoritative_producer_calls():
    plan = LogicalPlan(
        objective="Design solution",
        steps=[
            PlanStep(
                id="design-architecture",
                type="AGENT",
                description="Design architecture",
                agent_name="solution-architect",
            ),
            PlanStep(
                id="design-migration",
                type="AGENT",
                description="Design migration",
                agent_name="solution-architect",
                depends_on=["design-architecture"],
            ),
            PlanStep(
                id="consolidate",
                type="AGENT",
                description="Consolidate",
                agent_name="solution-architect",
                depends_on=["design-migration"],
            ),
        ],
        final_step_id="consolidate",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command(["solution-architect"]),
        [],
    )

    assert result.valid is False
    assert any("exactly one authoritative producer" in item for item in result.errors)


def test_artifact_policy_rejects_write_tool_when_disabled():
    write_tool = Tool(
        id=uuid4(),
        name="google-docs-create-from-artifact",
        description="write",
        instructions="",
        implementation_type="MCP",
        side_effect="WRITE",
        approval_policy="REQUIRED",
    )
    plan = LogicalPlan(
        objective="Design solution",
        steps=[
            PlanStep(
                id="synthesis",
                type="AGENT",
                description="Synthesis",
                agent_name="solution-architect",
            ),
            PlanStep(
                id="materialize",
                type="TOOL",
                description="Materialize",
                tool_name="google-docs-create-from-artifact",
                depends_on=["synthesis"],
            ),
        ],
        final_step_id="materialize",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command_with_write_policy(["solution-architect"], False),
        [write_tool],
    )

    assert result.valid is False
    assert any("forbids WRITE tool steps" in item for item in result.errors)


def test_artifact_policy_allows_write_tool_for_final_deliverable():
    write_tool = Tool(
        id=uuid4(),
        name="google-docs-create-from-artifact",
        description="write",
        instructions="",
        implementation_type="MCP",
        side_effect="WRITE",
        approval_policy="REQUIRED",
    )
    plan = LogicalPlan(
        objective="Create final response",
        steps=[
            PlanStep(
                id="write-response",
                type="AGENT",
                description="Author response",
                agent_name="rfp-response-writer",
            ),
            PlanStep(
                id="materialize",
                type="TOOL",
                description="Materialize",
                tool_name="google-docs-create-from-artifact",
                depends_on=["write-response"],
            ),
        ],
        final_step_id="materialize",
    )

    result = PlannerService._apply_artifact_policy_validation(
        PlanValidation(valid=True),
        plan,
        command_with_write_policy(["rfp-response-writer"], True),
        [write_tool],
    )

    assert result.valid is True
