ALTER TABLE memory_entries
    ADD COLUMN IF NOT EXISTS embedding vector(768) NULL;

ALTER TABLE memory_entries
    ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;

CREATE INDEX IF NOT EXISTS idx_memory_search
    ON memory_entries USING GIN(search_vector);

CREATE INDEX IF NOT EXISTS idx_memory_embedding
    ON memory_entries USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE TABLE IF NOT EXISTS context_snapshots (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    model_profile TEXT NOT NULL,
    budget JSONB NOT NULL DEFAULT '{}'::jsonb,
    components JSONB NOT NULL DEFAULT '[]'::jsonb,
    provenance JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_token_estimate INTEGER NOT NULL DEFAULT 0,
    selected_token_estimate INTEGER NOT NULL DEFAULT 0,
    dropped_token_estimate INTEGER NOT NULL DEFAULT 0,
    compressed BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_execution_created
    ON context_snapshots(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_context_snapshots_execution_step
    ON context_snapshots(execution_id, step_id, created_at DESC);
