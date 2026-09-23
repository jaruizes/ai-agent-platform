CREATE TABLE IF NOT EXISTS governance_policies (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    policy_type TEXT NOT NULL,
    effect TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_pattern TEXT NOT NULL DEFAULT '*',
    subject_type TEXT NOT NULL DEFAULT 'GLOBAL',
    subject_pattern TEXT NOT NULL DEFAULT '*',
    conditions JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 100,
    enabled BOOLEAN NOT NULL DEFAULT true,
    source TEXT NOT NULL DEFAULT 'API',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_policies_match
    ON governance_policies(enabled, policy_type, resource_type, priority DESC);

CREATE TABLE IF NOT EXISTS governance_policy_decisions (
    id UUID PRIMARY KEY,
    execution_id UUID NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NULL,
    policy_id UUID NULL REFERENCES governance_policies(id) ON DELETE SET NULL,
    policy_name TEXT NULL,
    policy_type TEXT NOT NULL,
    effect TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_decisions_execution
    ON governance_policy_decisions(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_governance_decisions_effect
    ON governance_policy_decisions(effect, created_at DESC);

CREATE TABLE IF NOT EXISTS governance_budgets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    period TEXT NOT NULL DEFAULT 'EXECUTION',
    max_prompt_tokens BIGINT NULL,
    max_completion_tokens BIGINT NULL,
    max_total_tokens BIGINT NULL,
    max_cost_usd DOUBLE PRECISION NULL,
    action TEXT NOT NULL DEFAULT 'DENY',
    degrade_model_profile TEXT NULL,
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_budgets_scope
    ON governance_budgets(enabled, scope_type, scope_id, period);

CREATE TABLE IF NOT EXISTS governance_usage (
    id UUID PRIMARY KEY,
    execution_id UUID NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    model_profile TEXT NOT NULL,
    prompt_tokens BIGINT NOT NULL DEFAULT 0,
    completion_tokens BIGINT NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    estimated_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_governance_usage_execution
    ON governance_usage(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_governance_usage_scope
    ON governance_usage(scope_type, scope_id, created_at);
