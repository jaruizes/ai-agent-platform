CREATE TABLE IF NOT EXISTS execution_artifacts (
    id UUID PRIMARY KEY,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    step_id TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    version INTEGER NOT NULL,
    title TEXT NOT NULL,
    media_type TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    content JSONB NOT NULL,
    checksum TEXT NOT NULL,
    size_bytes BIGINT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_execution_artifact_type CHECK (
        artifact_type IN (
            'HUMAN_DOCUMENT',
            'MACHINE_DATA',
            'AGENT_HANDOFF',
            'EVIDENCE_SET',
            'FINAL_DELIVERABLE'
        )
    ),
    CONSTRAINT uq_execution_artifact_scope_type_version
        UNIQUE(scope_key, artifact_type, version)
);

CREATE INDEX IF NOT EXISTS idx_execution_artifacts_execution
    ON execution_artifacts(execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_execution_artifacts_scope
    ON execution_artifacts(scope_key, version DESC);

CREATE INDEX IF NOT EXISTS idx_execution_artifacts_type
    ON execution_artifacts(artifact_type, created_at);
