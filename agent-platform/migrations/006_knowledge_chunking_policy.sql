ALTER TABLE knowledge_bases
    ADD COLUMN IF NOT EXISTS chunking_policy JSONB NOT NULL DEFAULT '{
      "strategy":"PARAGRAPH",
      "chunkSize":1600,
      "overlap":200,
      "parentSize":6000,
      "childSize":1600,
      "childOverlap":200
    }'::jsonb;

ALTER TABLE knowledge_chunks
    ALTER COLUMN embedding DROP NOT NULL;
