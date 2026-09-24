ALTER TABLE process_service_definitions
    ADD COLUMN configuration JSONB NOT NULL DEFAULT '{}'::jsonb;
