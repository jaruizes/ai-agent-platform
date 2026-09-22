CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY,
    name TEXT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    scope TEXT NOT NULL DEFAULT 'TENANT',
    owner_key TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_status_updated
    ON sessions(status, updated_at DESC);

ALTER TABLE executions
    ADD COLUMN IF NOT EXISTS session_id UUID NULL REFERENCES sessions(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS command_metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_executions_session_created
    ON executions(session_id, created_at DESC)
    WHERE session_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS execution_context_entries (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    session_id UUID NULL REFERENCES sessions(id) ON DELETE SET NULL,
    step_id TEXT NULL,
    entry_type TEXT NOT NULL,
    entry_key TEXT NULL,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    priority INTEGER NOT NULL DEFAULT 50,
    token_estimate INTEGER NOT NULL DEFAULT 0,
    source_type TEXT NOT NULL DEFAULT 'PLATFORM',
    source_ref TEXT NULL,
    provenance JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_context_execution_created
    ON execution_context_entries(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_context_session_created
    ON execution_context_entries(session_id, created_at)
    WHERE session_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_context_execution_step
    ON execution_context_entries(execution_id, step_id)
    WHERE step_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS memory_entries (
    id UUID PRIMARY KEY,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    memory_key TEXT NULL,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    importance DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    explicit BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'ACTIVE',
    policy_decision JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_execution_id UUID NULL REFERENCES executions(id) ON DELETE SET NULL,
    source_step_id TEXT NULL,
    supersedes_memory_id UUID NULL REFERENCES memory_entries(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NULL,
    revoked_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_scope_status
    ON memory_entries(scope_type, scope_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_type_status
    ON memory_entries(memory_type, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_memory_expiry
    ON memory_entries(expires_at)
    WHERE status='ACTIVE' AND expires_at IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_memory_active_key
    ON memory_entries(scope_type, scope_id, memory_key)
    WHERE status='ACTIVE' AND memory_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS memory_policy_audit (
    id UUID PRIMARY KEY,
    memory_id UUID NULL REFERENCES memory_entries(id) ON DELETE SET NULL,
    candidate JSONB NOT NULL,
    decision JSONB NOT NULL,
    source_execution_id UUID NULL REFERENCES executions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_policy_audit_created
    ON memory_policy_audit(created_at DESC);
