ALTER TABLE process_human_tasks
    ADD COLUMN iteration INTEGER NOT NULL DEFAULT 1;

ALTER TABLE process_human_tasks
    DROP CONSTRAINT IF EXISTS uk_process_human_task_step;

ALTER TABLE process_human_tasks
    ADD CONSTRAINT uk_process_human_task_iteration
    UNIQUE(process_instance_id, step_key, iteration);

CREATE INDEX idx_process_human_tasks_instance_step
    ON process_human_tasks(process_instance_id, step_key, iteration DESC);
