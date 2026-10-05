from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.domain.artifact import Artifact
from app.infrastructure.persistence.postgres.database import Database


class PostgresArtifactRepository:
    def __init__(self, database: Database):
        self._db = database

    async def next_version(self, scope_key: str) -> int:
        async with self._db.require_pool().acquire() as conn:
            value = await conn.fetchval(
                """
                SELECT COALESCE(MAX(version), 0) + 1
                FROM execution_artifacts
                WHERE scope_key=$1
                """,
                scope_key,
            )
            return int(value or 1)

    async def create_many(self, artifacts: list[Artifact]) -> list[Artifact]:
        if not artifacts:
            return []
        async with self._db.require_pool().acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO execution_artifacts(
                        id,execution_id,step_id,scope_key,artifact_type,
                        schema_name,version,title,media_type,summary,content,
                        checksum,size_bytes,metadata
                    ) VALUES(
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13,$14::jsonb
                    )
                    """,
                    [
                        (
                            item.id,
                            item.execution_id,
                            item.step_id,
                            item.scope_key,
                            item.artifact_type,
                            item.schema_name,
                            item.version,
                            item.title,
                            item.media_type,
                            item.summary,
                            json.dumps(item.content, ensure_ascii=False, default=str),
                            item.checksum,
                            item.size_bytes,
                            json.dumps(item.metadata, ensure_ascii=False, default=str),
                        )
                        for item in artifacts
                    ],
                )
        return artifacts

    async def get(self, artifact_id: UUID) -> Artifact | None:
        async with self._db.require_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM execution_artifacts WHERE id=$1",
                artifact_id,
            )
            return self._map(row) if row else None

    async def list_by_execution(self, execution_id: UUID) -> list[Artifact]:
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM execution_artifacts
                WHERE execution_id=$1
                ORDER BY version,created_at,artifact_type
                """,
                execution_id,
            )
            return [self._map(row) for row in rows]

    async def list_by_ids(self, artifact_ids: list[UUID]) -> list[Artifact]:
        if not artifact_ids:
            return []
        async with self._db.require_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM execution_artifacts
                WHERE id = ANY($1::uuid[])
                ORDER BY CASE artifact_type
                    WHEN 'AGENT_HANDOFF' THEN 1
                    WHEN 'MACHINE_DATA' THEN 2
                    WHEN 'EVIDENCE_SET' THEN 3
                    ELSE 9
                END, created_at
                """,
                artifact_ids,
            )
            return [self._map(row) for row in rows]

    async def list_scope(
        self,
        scope_key: str,
        *,
        latest_only: bool = False,
    ) -> list[Artifact]:
        async with self._db.require_pool().acquire() as conn:
            if latest_only:
                rows = await conn.fetch(
                    """
                    SELECT * FROM execution_artifacts
                    WHERE scope_key=$1
                      AND version=(SELECT MAX(version) FROM execution_artifacts WHERE scope_key=$1)
                    ORDER BY artifact_type
                    """,
                    scope_key,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM execution_artifacts
                    WHERE scope_key=$1
                    ORDER BY version DESC,artifact_type
                    """,
                    scope_key,
                )
            return [self._map(row) for row in rows]

    @staticmethod
    def _map(row: Any) -> Artifact:
        def decode(value: Any) -> Any:
            return json.loads(value) if isinstance(value, str) else value

        return Artifact(
            id=row["id"],
            execution_id=row["execution_id"],
            step_id=row["step_id"],
            scope_key=row["scope_key"],
            artifact_type=row["artifact_type"],
            schema_name=row["schema_name"],
            version=int(row["version"]),
            title=row["title"],
            media_type=row["media_type"],
            summary=row["summary"],
            content=decode(row["content"]),
            checksum=row["checksum"],
            size_bytes=int(row["size_bytes"]),
            metadata=decode(row["metadata"]) or {},
            created_at=row["created_at"],
        )
