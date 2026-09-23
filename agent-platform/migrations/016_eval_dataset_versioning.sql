ALTER TABLE eval_datasets
    DROP CONSTRAINT IF EXISTS eval_datasets_name_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'eval_datasets_name_version_key'
    ) THEN
        ALTER TABLE eval_datasets
            ADD CONSTRAINT eval_datasets_name_version_key UNIQUE(name, version);
    END IF;
END $$;
