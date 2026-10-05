CREATE TABLE process_definitions (
    id UUID PRIMARY KEY,
    definition_key VARCHAR(200) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    activated_at TIMESTAMPTZ NULL,
    CONSTRAINT uk_process_definition_key_version UNIQUE(definition_key, version)
);

CREATE INDEX idx_process_definitions_key_status
    ON process_definitions(definition_key, status, version DESC);

CREATE TABLE process_step_definitions (
    id UUID PRIMARY KEY,
    process_definition_id UUID NOT NULL
        REFERENCES process_definitions(id) ON DELETE CASCADE,
    step_key VARCHAR(200) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    step_type VARCHAR(50) NOT NULL,
    depends_on JSONB NOT NULL DEFAULT '[]'::jsonb,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uk_process_step_definition_key
        UNIQUE(process_definition_id, step_key)
);

CREATE INDEX idx_process_step_definitions_definition
    ON process_step_definitions(process_definition_id);

CREATE TABLE process_instances (
    id UUID PRIMARY KEY,
    process_definition_id UUID NOT NULL
        REFERENCES process_definitions(id) ON DELETE RESTRICT,
    definition_key VARCHAR(200) NOT NULL,
    definition_version INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    correlation_id VARCHAR(200) NOT NULL,
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    process_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_process_instances_definition
    ON process_instances(process_definition_id, created_at DESC);
CREATE INDEX idx_process_instances_correlation
    ON process_instances(correlation_id);
CREATE INDEX idx_process_instances_status
    ON process_instances(status, created_at);

CREATE TABLE process_step_instances (
    id UUID PRIMARY KEY,
    process_instance_id UUID NOT NULL
        REFERENCES process_instances(id) ON DELETE CASCADE,
    step_definition_id UUID NOT NULL
        REFERENCES process_step_definitions(id) ON DELETE RESTRICT,
    step_key VARCHAR(200) NOT NULL,
    step_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL,
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB NOT NULL DEFAULT '{}'::jsonb,
    delegated_execution_id UUID NULL,
    started_at TIMESTAMPTZ NULL,
    completed_at TIMESTAMPTZ NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uk_process_step_instance_key
        UNIQUE(process_instance_id, step_key)
);

CREATE INDEX idx_process_step_instances_instance
    ON process_step_instances(process_instance_id);
CREATE INDEX idx_process_step_instances_execution
    ON process_step_instances(delegated_execution_id)
    WHERE delegated_execution_id IS NOT NULL;
