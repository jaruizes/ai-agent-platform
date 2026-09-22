CREATE TABLE IF NOT EXISTS executions (
    id UUID PRIMARY KEY,
    request_message_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    source JSONB NOT NULL,
    command_name TEXT NULL,
    intent TEXT NOT NULL,
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    instructions JSONB NOT NULL DEFAULT '[]'::jsonb,
    normalized_intent TEXT NULL,
    status TEXT NOT NULL,
    result JSONB NULL,
    error JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_executions_status_created
    ON executions(status, created_at);

CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    payload JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished
    ON outbox_events(created_at)
    WHERE published_at IS NULL;
