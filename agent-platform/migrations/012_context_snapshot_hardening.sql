-- M7 hardening for environments that may have applied an earlier draft
-- of 011_context_engine.sql before ContextSnapshot attempt tracking existed.

ALTER TABLE context_snapshots
    ADD COLUMN IF NOT EXISTS attempt INTEGER NOT NULL DEFAULT 1;

CREATE UNIQUE INDEX IF NOT EXISTS uq_context_snapshot_attempt
    ON context_snapshots(execution_id, step_id, attempt);

CREATE INDEX IF NOT EXISTS idx_context_snapshot_step_attempt
    ON context_snapshots(execution_id, step_id, attempt DESC);
