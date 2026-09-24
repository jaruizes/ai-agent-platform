CREATE TABLE process_service_definitions (
    id UUID PRIMARY KEY,
    service_key VARCHAR(200) NOT NULL,
    name VARCHAR(300) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL,
    implementation_key VARCHAR(200) NOT NULL,
    input_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    activated_at TIMESTAMPTZ NULL,
    CONSTRAINT uk_process_service_key_version UNIQUE(service_key, version)
);

CREATE INDEX idx_process_services_key_status
    ON process_service_definitions(service_key, status, version DESC);

CREATE TABLE process_human_tasks (
    id UUID PRIMARY KEY,
    process_instance_id UUID NOT NULL
        REFERENCES process_instances(id) ON DELETE CASCADE,
    step_key VARCHAR(200) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(30) NOT NULL,
    decision VARCHAR(100) NULL,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NULL,
    CONSTRAINT uk_process_human_task_step UNIQUE(process_instance_id, step_key)
);

CREATE INDEX idx_process_human_tasks_status
    ON process_human_tasks(status, created_at);

CREATE TABLE process_event_waits (
    id UUID PRIMARY KEY,
    process_instance_id UUID NOT NULL
        REFERENCES process_instances(id) ON DELETE CASCADE,
    step_key VARCHAR(200) NOT NULL,
    event_type VARCHAR(300) NOT NULL,
    correlation_id VARCHAR(300) NOT NULL,
    status VARCHAR(30) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL,
    CONSTRAINT uk_process_event_wait_step UNIQUE(process_instance_id, step_key)
);

CREATE INDEX idx_process_event_wait_match
    ON process_event_waits(event_type, correlation_id, status);

ALTER TABLE process_step_instances
    ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN available_at TIMESTAMPTZ NULL,
    ADD COLUMN deadline_at TIMESTAMPTZ NULL;
