DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM process_step_definitions WHERE step_type = 'TOOL'
    ) OR EXISTS (
        SELECT 1 FROM process_step_instances WHERE step_type = 'TOOL'
    ) THEN
        RAISE EXCEPTION
            'Legacy Process Platform TOOL steps exist. TOOL was removed from the Process Platform domain; migrate each step explicitly to SERVICE or AGENTIC_EXECUTION before applying this migration.';
    END IF;
END $$;

ALTER TABLE process_step_definitions
    ADD CONSTRAINT ck_process_step_definitions_type
    CHECK (step_type IN (
        'SERVICE',
        'AGENTIC_EXECUTION',
        'DECISION',
        'HUMAN',
        'WAIT_EVENT',
        'SUBPROCESS'
    ));

ALTER TABLE process_step_instances
    ADD CONSTRAINT ck_process_step_instances_type
    CHECK (step_type IN (
        'SERVICE',
        'AGENTIC_EXECUTION',
        'DECISION',
        'HUMAN',
        'WAIT_EVENT',
        'SUBPROCESS'
    ));
