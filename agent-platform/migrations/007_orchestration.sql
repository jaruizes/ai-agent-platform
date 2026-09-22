CREATE TABLE IF NOT EXISTS execution_plans (
    execution_id UUID PRIMARY KEY REFERENCES executions(id) ON DELETE CASCADE,
    objective TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PLANNED',
    planner_model TEXT NULL,
    planner_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    logical_plan JSONB NOT NULL,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS execution_plan_steps (
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NOT NULL,
    step_type TEXT NOT NULL,
    description TEXT NOT NULL,
    agent_name TEXT NULL,
    tool_name TEXT NULL,
    knowledge_bases JSONB NOT NULL DEFAULT '[]'::jsonb,
    depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'PENDING',
    usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NULL,
    error JSONB NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    PRIMARY KEY (execution_id, step_id)
);

CREATE INDEX IF NOT EXISTS idx_execution_plan_steps_status
    ON execution_plan_steps(execution_id, status);

CREATE INDEX IF NOT EXISTS idx_execution_plan_steps_agent
    ON execution_plan_steps(execution_id, agent_name)
    WHERE agent_name IS NOT NULL;
