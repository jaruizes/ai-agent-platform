CREATE TABLE IF NOT EXISTS eval_datasets (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL DEFAULT 1,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(name, version)
);

CREATE TABLE IF NOT EXISTS eval_dataset_items (
    id UUID PRIMARY KEY,
    dataset_id UUID NOT NULL REFERENCES eval_datasets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    command JSONB NOT NULL,
    expected_output TEXT NULL,
    assertions JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_eval_dataset_items_dataset ON eval_dataset_items(dataset_id);

CREATE TABLE IF NOT EXISTS eval_definitions (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    dataset_id UUID NOT NULL REFERENCES eval_datasets(id) ON DELETE RESTRICT,
    metrics JSONB NOT NULL DEFAULT '[]'::jsonb,
    thresholds JSONB NOT NULL DEFAULT '{}'::jsonb,
    judge_model_profile TEXT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY,
    definition_id UUID NOT NULL REFERENCES eval_definitions(id) ON DELETE RESTRICT,
    baseline_run_id UUID NULL REFERENCES eval_runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    dataset_version INTEGER NOT NULL,
    configuration_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    aggregate_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    regression JSONB NOT NULL DEFAULT '{}'::jsonb,
    total_cases INTEGER NOT NULL DEFAULT 0,
    passed_cases INTEGER NOT NULL DEFAULT 0,
    failed_cases INTEGER NOT NULL DEFAULT 0,
    total_tokens BIGINT NOT NULL DEFAULT 0,
    total_cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    error JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_definition_created ON eval_runs(definition_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eval_runs_status ON eval_runs(status, created_at);

CREATE TABLE IF NOT EXISTS eval_results (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
    dataset_item_id UUID NOT NULL REFERENCES eval_dataset_items(id) ON DELETE RESTRICT,
    execution_id UUID NULL REFERENCES executions(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    output TEXT NULL,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    passed BOOLEAN NOT NULL DEFAULT FALSE,
    token_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
    latency_ms BIGINT NOT NULL DEFAULT 0,
    error JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_eval_results_run_item ON eval_results(run_id, dataset_item_id);
