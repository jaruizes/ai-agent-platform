CREATE TABLE process_execution_command_outbox (
    id UUID PRIMARY KEY,
    process_instance_id UUID NOT NULL
        REFERENCES process_instances(id) ON DELETE CASCADE,
    step_key VARCHAR(200) NOT NULL,
    execution_id UUID NOT NULL,
    message_id VARCHAR(200) NOT NULL,
    payload JSONB NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ NULL,
    CONSTRAINT uk_process_outbox_message UNIQUE(message_id)
);

CREATE INDEX idx_process_execution_command_outbox_pending
    ON process_execution_command_outbox(created_at)
    WHERE published_at IS NULL;
