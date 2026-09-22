CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL DEFAULT 'TENANT',
    retention_policy TEXT NOT NULL DEFAULT 'PERSISTENT',
    expires_at TIMESTAMPTZ NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id UUID PRIMARY KEY,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NULL,
    source_uri TEXT NULL,
    mime_type TEXT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    version INTEGER NOT NULL DEFAULT 1,
    checksum TEXT NULL,
    storage_path TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    error JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    indexed_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_knowledge_documents_kb_status
    ON knowledge_documents(knowledge_base_id, status);

CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_document_source
    ON knowledge_documents(knowledge_base_id, source_type, source_id)
    WHERE source_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id UUID PRIMARY KEY,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_estimate INTEGER NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(document_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_search
    ON knowledge_chunks USING GIN(search_vector);

CREATE INDEX IF NOT EXISTS idx_knowledge_chunks_embedding
    ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS agent_knowledge_bases (
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    usage_mode TEXT NOT NULL DEFAULT 'REFERENCE',
    PRIMARY KEY(agent_id, knowledge_base_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_knowledge_bases_agent
    ON agent_knowledge_bases(agent_id);
