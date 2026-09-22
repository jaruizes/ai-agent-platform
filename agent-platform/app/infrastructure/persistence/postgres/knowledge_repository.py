from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    RetrievalHit,
)
from app.infrastructure.persistence.postgres.database import Database


class PostgresKnowledgeRepository:
    def __init__(self, database: Database):
        self._db = database

    async def list_knowledge_bases(self, enabled_only: bool = False) -> list[KnowledgeBase]:
        sql = "SELECT * FROM knowledge_bases"
        if enabled_only:
            sql += " WHERE enabled=true"
        sql += " ORDER BY name"
        async with self._db.require_pool().acquire() as conn:
            return [self._kb(row) for row in await conn.fetch(sql)]

    async def get_knowledge_base(self, kb_id: UUID) -> KnowledgeBase | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge_bases WHERE id=$1", kb_id)
            return self._kb(row) if row else None

    async def get_knowledge_base_by_name(self, name: str) -> KnowledgeBase | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge_bases WHERE name=$1", name)
            return self._kb(row) if row else None

    async def create_knowledge_base(self, kb: KnowledgeBase) -> KnowledgeBase:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_bases(
                    id,name,description,scope,retention_policy,expires_at,enabled,metadata
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                """,
                kb.id, kb.name, kb.description, kb.scope, kb.retention_policy,
                kb.expires_at, kb.enabled, json.dumps(kb.metadata),
            )
        return kb

    async def update_knowledge_base(self, kb: KnowledgeBase) -> KnowledgeBase:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_bases SET
                    name=$2,description=$3,scope=$4,retention_policy=$5,
                    expires_at=$6,enabled=$7,metadata=$8::jsonb,updated_at=now()
                WHERE id=$1
                """,
                kb.id, kb.name, kb.description, kb.scope, kb.retention_policy,
                kb.expires_at, kb.enabled, json.dumps(kb.metadata),
            )
        return kb

    async def delete_knowledge_base(self, kb_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute("DELETE FROM knowledge_bases WHERE id=$1", kb_id) == "DELETE 1"

    async def list_expired_knowledge_bases(self) -> list[KnowledgeBase]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM knowledge_bases
                WHERE retention_policy='TTL' AND expires_at IS NOT NULL AND expires_at <= now()
                """
            )
            return [self._kb(row) for row in rows]

    async def list_documents(self, kb_id: UUID) -> list[KnowledgeDocument]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM knowledge_documents WHERE knowledge_base_id=$1 ORDER BY created_at",
                kb_id,
            )
            return [self._document(row) for row in rows]

    async def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM knowledge_documents WHERE id=$1", document_id)
            return self._document(row) if row else None

    async def get_document_by_source(
        self,
        kb_id: UUID,
        source_type: str,
        source_id: str,
    ) -> KnowledgeDocument | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM knowledge_documents
                WHERE knowledge_base_id=$1 AND source_type=$2 AND source_id=$3
                """,
                kb_id, source_type, source_id,
            )
            return self._document(row) if row else None

    async def create_document(self, document: KnowledgeDocument) -> KnowledgeDocument:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO knowledge_documents(
                    id,knowledge_base_id,name,source_type,source_id,source_uri,mime_type,
                    status,version,checksum,storage_path,metadata,error
                ) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13::jsonb)
                """,
                document.id, document.knowledge_base_id, document.name, document.source_type,
                document.source_id, document.source_uri, document.mime_type, document.status,
                document.version, document.checksum, document.storage_path,
                json.dumps(document.metadata), json.dumps(document.error) if document.error else None,
            )
        return document

    async def update_document_content(
        self,
        document_id: UUID,
        *,
        name: str,
        mime_type: str | None,
        checksum: str | None,
        storage_path: str | None,
        metadata: dict[str, Any],
    ) -> KnowledgeDocument | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE knowledge_documents SET
                    name=$2,mime_type=$3,checksum=$4,storage_path=$5,metadata=$6::jsonb,
                    status='PENDING',version=version+1,error=NULL,updated_at=now()
                WHERE id=$1 RETURNING *
                """,
                document_id, name, mime_type, checksum, storage_path, json.dumps(metadata),
            )
            return self._document(row) if row else None

    async def mark_document_pending(self, document_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            result = await conn.execute(
                "UPDATE knowledge_documents SET status='PENDING',error=NULL,updated_at=now() WHERE id=$1",
                document_id,
            )
            return result == "UPDATE 1"

    async def claim_next_document(self) -> KnowledgeDocument | None:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    SELECT d.* FROM knowledge_documents d
                    JOIN knowledge_bases kb ON kb.id=d.knowledge_base_id
                    WHERE d.status='PENDING' AND kb.enabled=true
                    ORDER BY d.updated_at
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
                if not row:
                    return None
                await conn.execute(
                    "UPDATE knowledge_documents SET status='INDEXING',updated_at=now() WHERE id=$1",
                    row["id"],
                )
                data = dict(row)
                data["status"] = "INDEXING"
                return self._document(data)

    async def complete_document(
        self,
        document_id: UUID,
        chunks: list[KnowledgeChunk],
        *,
        parsed_metadata: dict[str, Any],
    ) -> None:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM knowledge_chunks WHERE document_id=$1", document_id)
                if chunks:
                    await conn.executemany(
                        """
                        INSERT INTO knowledge_chunks(
                            id,knowledge_base_id,document_id,ordinal,content,token_estimate,metadata,embedding
                        ) VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::vector)
                        """,
                        [
                            (
                                chunk.id,
                                chunk.knowledge_base_id,
                                chunk.document_id,
                                chunk.ordinal,
                                chunk.content,
                                chunk.token_estimate,
                                json.dumps(chunk.metadata),
                                self._vector_literal(chunk.embedding),
                            )
                            for chunk in chunks
                        ],
                    )
                await conn.execute(
                    """
                    UPDATE knowledge_documents SET
                        status='READY',
                        metadata=metadata || $2::jsonb,
                        error=NULL,
                        indexed_at=now(),
                        updated_at=now()
                    WHERE id=$1
                    """,
                    document_id, json.dumps(parsed_metadata),
                )

    async def fail_document(self, document_id: UUID, error: dict[str, Any]) -> None:
        async with self._db.require_pool().acquire() as conn:
            await conn.execute(
                """
                UPDATE knowledge_documents SET status='FAILED',error=$2::jsonb,updated_at=now()
                WHERE id=$1
                """,
                document_id, json.dumps(error),
            )

    async def delete_document(self, document_id: UUID) -> bool:
        async with self._db.require_pool().acquire() as conn:
            return await conn.execute(
                "DELETE FROM knowledge_documents WHERE id=$1", document_id
            ) == "DELETE 1"

    async def retrieve(
        self,
        knowledge_base_ids: list[UUID],
        *,
        query: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[RetrievalHit]:
        if not knowledge_base_ids:
            return []
        vector = self._vector_literal(query_embedding)
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    c.id AS chunk_id,
                    c.document_id,
                    c.knowledge_base_id,
                    d.name AS document_name,
                    c.content,
                    c.metadata,
                    (
                        0.80 * GREATEST(0.0, 1.0 - (c.embedding <=> $2::vector)) +
                        0.20 * ts_rank_cd(c.search_vector, plainto_tsquery('simple', $3))
                    ) AS score
                FROM knowledge_chunks c
                JOIN knowledge_documents d ON d.id=c.document_id
                JOIN knowledge_bases kb ON kb.id=c.knowledge_base_id
                WHERE c.knowledge_base_id = ANY($1::uuid[])
                  AND d.status='READY'
                  AND kb.enabled=true
                ORDER BY score DESC
                LIMIT $4
                """,
                knowledge_base_ids, vector, query, limit,
            )
            return [
                RetrievalHit(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    knowledge_base_id=row["knowledge_base_id"],
                    document_name=row["document_name"],
                    content=row["content"],
                    score=float(row["score"]),
                    metadata=self._json(row["metadata"]) or {},
                )
                for row in rows
            ]

    async def replace_agent_knowledge_bases(
        self,
        agent_id: UUID,
        assignments: list[tuple[UUID, str]],
    ) -> None:
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM agent_knowledge_bases WHERE agent_id=$1", agent_id)
                if assignments:
                    await conn.executemany(
                        """
                        INSERT INTO agent_knowledge_bases(agent_id,knowledge_base_id,usage_mode)
                        VALUES($1,$2,$3)
                        """,
                        [(agent_id, kb_id, mode) for kb_id, mode in assignments],
                    )

    async def list_agent_knowledge_bases(self, agent_id: UUID) -> list[dict[str, Any]]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT kb.*, akb.usage_mode
                FROM agent_knowledge_bases akb
                JOIN knowledge_bases kb ON kb.id=akb.knowledge_base_id
                WHERE akb.agent_id=$1 AND kb.enabled=true
                ORDER BY kb.name
                """,
                agent_id,
            )
            return [
                {
                    "knowledgeBase": self._kb(row),
                    "usageMode": row["usage_mode"],
                }
                for row in rows
            ]

    @staticmethod
    def _vector_literal(values: list[float]) -> str:
        return "[" + ",".join(f"{value:.9f}" for value in values) + "]"

    @staticmethod
    def _json(value):
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return value

    @classmethod
    def _kb(cls, row) -> KnowledgeBase:
        return KnowledgeBase(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            scope=row["scope"],
            retention_policy=row["retention_policy"],
            expires_at=row["expires_at"],
            enabled=row["enabled"],
            metadata=cls._json(row["metadata"]) or {},
        )

    @classmethod
    def _document(cls, row) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=row["id"],
            knowledge_base_id=row["knowledge_base_id"],
            name=row["name"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            source_uri=row["source_uri"],
            mime_type=row["mime_type"],
            status=row["status"],
            version=row["version"],
            checksum=row["checksum"],
            storage_path=row["storage_path"],
            metadata=cls._json(row["metadata"]) or {},
            error=cls._json(row["error"]),
        )
