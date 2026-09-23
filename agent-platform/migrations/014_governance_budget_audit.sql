CREATE TABLE IF NOT EXISTS governance_budget_decisions (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NULL,
    budget_id UUID NULL REFERENCES governance_budgets(id) ON DELETE SET NULL,
    budget_name TEXT NULL,
    action TEXT NOT NULL,
    allowed BOOLEAN NOT NULL,
    requested_model_profile TEXT NOT NULL,
    effective_model_profile TEXT NOT NULL,
    reason TEXT NULL,
    current_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    projected_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_budget_decisions_execution
    ON governance_budget_decisions(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_governance_budget_decisions_action
    ON governance_budget_decisions(action, created_at DESC);
