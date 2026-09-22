from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO
from uuid import UUID, uuid4

from app.business.embeddings import EmbeddingProvider
from app.business.ports import KnowledgeRepositoryPort
from app.business.tool_service import ToolService
from app.domain.knowledge import (
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDocument,
    ParsedDocument,
    ParsedSegment,
    RetrievalHit,
)
from app.infrastructure.knowledge.chunking import build_chunker, normalize_chunking_policy
from app.infrastructure.knowledge.parsers import DocumentParser


logger = logging.getLogger(__name__)


class KnowledgeService:
    GOOGLE_TOOLS = {
        "GOOGLE_DOCS": "google-docs-get-text",
        "GOOGLE_SLIDES": "google-slides-get-text",
        "GOOGLE_SHEETS": "google-sheets-get-text",
    }

    def __init__(
        self,
        repository: KnowledgeRepositoryPort,
        embedding_provider: EmbeddingProvider,
        tool_service: ToolService,
        parser: DocumentParser,
        *,
        storage_root: str,
        embedding_batch_size: int,
        worker_poll_seconds: float,
        cleanup_poll_seconds: float,
    ):
        self._repository = repository
        self._embedding_provider = embedding_provider
        self._tool_service = tool_service
        self._parser = parser
        self._storage_root = Path(storage_root)
        self._embedding_batch_size = embedding_batch_size
        self._worker_poll_seconds = worker_poll_seconds
        self._cleanup_poll_seconds = cleanup_poll_seconds
        self._stop = asyncio.Event()
        self._storage_root.mkdir(parents=True, exist_ok=True)

    async def list_knowledge_bases(self, enabled_only: bool = False) -> list[KnowledgeBase]:
        return await self._repository.list_knowledge_bases(enabled_only)

    async def get_knowledge_base(self, kb_id: UUID) -> KnowledgeBase | None:
        return await self._repository.get_knowledge_base(kb_id)

    async def create_knowledge_base(
        self,
        *,
        name: str,
        description: str = "",
        scope: str = "TENANT",
        retention_policy: str = "PERSISTENT",
        ttl_seconds: int | None = None,
        enabled: bool = True,
        chunking_policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeBase:
        if await self._repository.get_knowledge_base_by_name(name):
            raise ValueError(f"Knowledge base '{name}' already exists")
        scope = scope.upper()
        retention_policy = retention_policy.upper()
        if scope not in {"EXECUTION", "SESSION", "USER", "TENANT", "GLOBAL"}:
            raise ValueError(f"Unsupported knowledge scope '{scope}'")
        if retention_policy not in {"PERSISTENT", "TTL"}:
            raise ValueError(f"Unsupported retention policy '{retention_policy}'")
        if retention_policy == "TTL" and (ttl_seconds is None or ttl_seconds <= 0):
            raise ValueError("ttlSeconds must be greater than zero for TTL retention")
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            if retention_policy == "TTL"
            else None
        )
        return await self._repository.create_knowledge_base(
            KnowledgeBase(
                id=uuid4(),
                name=name,
                description=description,
                scope=scope,
                retention_policy=retention_policy,
                expires_at=expires_at,
                enabled=enabled,
                chunking_policy=normalize_chunking_policy(chunking_policy),
                metadata=metadata or {},
            )
        )

    async def update_knowledge_base(
        self,
        kb_id: UUID,
        *,
        name: str,
        description: str,
        scope: str,
        retention_policy: str,
        ttl_seconds: int | None,
        enabled: bool,
        chunking_policy: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeBase | None:
        existing = await self._repository.get_knowledge_base(kb_id)
        if not existing:
            return None
        scope = scope.upper()
        retention_policy = retention_policy.upper()
        if scope not in {"EXECUTION", "SESSION", "USER", "TENANT", "GLOBAL"}:
            raise ValueError(f"Unsupported knowledge scope '{scope}'")
        if retention_policy not in {"PERSISTENT", "TTL"}:
            raise ValueError(f"Unsupported retention policy '{retention_policy}'")
        expires_at = existing.expires_at
        if retention_policy == "TTL":
            if ttl_seconds is not None:
                if ttl_seconds <= 0:
                    raise ValueError("ttlSeconds must be greater than zero")
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            elif expires_at is None:
                raise ValueError("ttlSeconds is required when switching to TTL retention")
        else:
            expires_at = None
        return await self._repository.update_knowledge_base(
            KnowledgeBase(
                id=existing.id,
                name=name,
                description=description,
                scope=scope,
                retention_policy=retention_policy,
                expires_at=expires_at,
                enabled=enabled,
                chunking_policy=normalize_chunking_policy(
                    chunking_policy if chunking_policy is not None else existing.chunking_policy
                ),
                metadata=metadata or {},
            )
        )

    async def delete_knowledge_base(self, kb_id: UUID) -> bool:
        documents = await self._repository.list_documents(kb_id)
        deleted = await self._repository.delete_knowledge_base(kb_id)
        if deleted:
            for document in documents:
                await self._delete_storage(document.storage_path)
            shutil.rmtree(self._storage_root / str(kb_id), ignore_errors=True)
        return deleted

    async def list_documents(self, kb_id: UUID) -> list[KnowledgeDocument]:
        return await self._repository.list_documents(kb_id)

    async def get_document(self, document_id: UUID) -> KnowledgeDocument | None:
        return await self._repository.get_document(document_id)

    async def create_uploaded_document(
        self,
        kb_id: UUID,
        *,
        name: str,
        stream: BinaryIO,
        mime_type: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        if not await self._repository.get_knowledge_base(kb_id):
            raise LookupError("Knowledge base not found")
        suffix = Path(name).suffix.lower()
        if suffix not in self._parser.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension '{suffix}'")
        document_id = uuid4()
        directory = self._storage_root / str(kb_id) / str(document_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / name
        checksum = await asyncio.to_thread(self._write_stream, stream, destination)
        return await self._repository.create_document(
            KnowledgeDocument(
                id=document_id,
                knowledge_base_id=kb_id,
                name=name,
                source_type="UPLOAD",
                source_id=None,
                source_uri=None,
                mime_type=mime_type,
                status="PENDING",
                version=1,
                checksum=checksum,
                storage_path=str(destination),
                metadata=metadata or {},
            )
        )

    async def create_google_document(
        self,
        kb_id: UUID,
        *,
        source_type: str,
        source_id: str,
        name: str | None = None,
        source_uri: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        source_type = source_type.upper()
        if source_type not in self.GOOGLE_TOOLS:
            raise ValueError(
                "sourceType must be one of GOOGLE_DOCS, GOOGLE_SLIDES or GOOGLE_SHEETS"
            )
        if not await self._repository.get_knowledge_base(kb_id):
            raise LookupError("Knowledge base not found")
        existing = await self._repository.get_document_by_source(kb_id, source_type, source_id)
        if existing:
            raise ValueError(
                f"Source '{source_type}:{source_id}' already exists in this knowledge base"
            )
        return await self._repository.create_document(
            KnowledgeDocument(
                id=uuid4(),
                knowledge_base_id=kb_id,
                name=name or source_id,
                source_type=source_type,
                source_id=source_id,
                source_uri=source_uri,
                mime_type=None,
                status="PENDING",
                version=1,
                metadata=metadata or {},
            )
        )

    async def update_uploaded_document(
        self,
        document_id: UUID,
        *,
        name: str,
        stream: BinaryIO,
        mime_type: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument | None:
        existing = await self._repository.get_document(document_id)
        if not existing:
            return None
        if existing.source_type != "UPLOAD":
            raise ValueError("Binary content can only replace UPLOAD documents")
        suffix = Path(name).suffix.lower()
        if suffix not in self._parser.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file extension '{suffix}'")
        directory = self._storage_root / str(existing.knowledge_base_id) / str(document_id)
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / name
        checksum = await asyncio.to_thread(self._write_stream, stream, destination)
        if existing.storage_path and existing.storage_path != str(destination):
            await self._delete_storage(existing.storage_path)
        return await self._repository.update_document_content(
            document_id,
            name=name,
            mime_type=mime_type,
            checksum=checksum,
            storage_path=str(destination),
            metadata=metadata or existing.metadata,
        )

    async def reindex_document(self, document_id: UUID) -> bool:
        return await self._repository.mark_document_pending(document_id)

    async def delete_document(self, document_id: UUID) -> bool:
        existing = await self._repository.get_document(document_id)
        if not existing:
            return False
        deleted = await self._repository.delete_document(document_id)
        if deleted:
            await self._delete_storage(existing.storage_path)
            shutil.rmtree(
                self._storage_root / str(existing.knowledge_base_id) / str(document_id),
                ignore_errors=True,
            )
        return deleted

    async def retrieve(
        self,
        *,
        query: str,
        knowledge_base_names: list[str],
        top_k: int = 8,
    ) -> list[RetrievalHit]:
        if not query.strip():
            return []
        kbs: list[KnowledgeBase] = []
        for name in knowledge_base_names:
            kb = await self._repository.get_knowledge_base_by_name(name)
            if kb and kb.enabled:
                kbs.append(kb)
        if not kbs:
            return []
        retrieval_query = query[:1600]
        embedding_result = await self._embedding_provider.embed([retrieval_query])
        embeddings = embedding_result.vectors
        self._validate_embedding(embeddings[0])
        return await self._repository.retrieve(
            [kb.id for kb in kbs],
            query=retrieval_query,
            query_embedding=embeddings[0],
            limit=max(1, min(top_k, 50)),
        )

    async def replace_agent_knowledge_bases(
        self,
        agent_id: UUID,
        assignments: list[dict[str, str]],
    ) -> None:
        if not await self._repository.agent_exists(agent_id):
            raise LookupError("Agent not found")
        resolved: list[tuple[UUID, str]] = []
        for assignment in assignments:
            name = assignment["name"]
            mode = assignment.get("usageMode", "REFERENCE").upper()
            if mode not in {"REFERENCE", "GUARDRAIL"}:
                raise ValueError(f"Unsupported knowledge usage mode '{mode}'")
            kb = await self._repository.get_knowledge_base_by_name(name)
            if not kb:
                raise ValueError(f"Unknown knowledge base '{name}'")
            resolved.append((kb.id, mode))
        await self._repository.replace_agent_knowledge_bases(agent_id, resolved)

    async def list_agent_knowledge_bases(self, agent_id: UUID) -> list[dict[str, Any]]:
        return await self._repository.list_agent_knowledge_bases(agent_id)

    async def worker_loop(self) -> None:
        while not self._stop.is_set():
            document = await self._repository.claim_next_document()
            if not document:
                await asyncio.sleep(self._worker_poll_seconds)
                continue
            await self._index_document(document)

    async def cleanup_loop(self) -> None:
        while not self._stop.is_set():
            try:
                for kb in await self._repository.list_expired_knowledge_bases():
                    logger.info("Deleting expired knowledge base id=%s name=%s", kb.id, kb.name)
                    await self.delete_knowledge_base(kb.id)
            except Exception:
                logger.exception("Knowledge retention cleanup failed")
            await asyncio.sleep(self._cleanup_poll_seconds)

    async def stop(self) -> None:
        self._stop.set()

    async def _index_document(self, document: KnowledgeDocument) -> None:
        try:
            kb = await self._repository.get_knowledge_base(document.knowledge_base_id)
            if not kb:
                raise LookupError("Knowledge base not found during indexing")

            parsed = await self._extract(document)
            chunks = self._chunk(parsed, document, kb.chunking_policy)
            if not chunks:
                raise ValueError("Document produced no indexable text")

            embeddable_indices = [
                index for index, chunk in enumerate(chunks) if chunk["embed"]
            ]
            embeddings_by_index: dict[int, list[float]] = {}
            for start in range(0, len(embeddable_indices), self._embedding_batch_size):
                batch_indices = embeddable_indices[start:start + self._embedding_batch_size]
                result = await self._embedding_provider.embed(
                    [chunks[index]["content"] for index in batch_indices]
                )
                if len(result.vectors) != len(batch_indices):
                    raise RuntimeError(
                        "Embedding provider returned an unexpected vector count"
                    )
                for index, vector in zip(batch_indices, result.vectors, strict=True):
                    self._validate_embedding(vector)
                    embeddings_by_index[index] = vector

            rows = [
                KnowledgeChunk(
                    id=uuid4(),
                    document_id=document.id,
                    knowledge_base_id=document.knowledge_base_id,
                    ordinal=index,
                    content=item["content"],
                    token_estimate=max(1, len(item["content"]) // 4),
                    metadata=item["metadata"],
                    embedding=embeddings_by_index.get(index),
                )
                for index, item in enumerate(chunks)
            ]
            await self._repository.complete_document(
                document.id,
                rows,
                parsed_metadata={
                    "parsed": parsed.metadata,
                    "chunkCount": len(rows),
                    "embeddedChunkCount": len(embeddable_indices),
                    "embeddingProvider": self._embedding_provider.provider_key,
                    "embeddingModel": self._embedding_provider.model,
                    "chunkingPolicy": normalize_chunking_policy(kb.chunking_policy),
                },
            )
            logger.info(
                "Knowledge document indexed document_id=%s chunks=%s embedded=%s "
                "source_type=%s chunking=%s embedding_provider=%s",
                document.id,
                len(rows),
                len(embeddable_indices),
                document.source_type,
                kb.chunking_policy.get("strategy"),
                self._embedding_provider.provider_key,
            )
        except Exception as exc:
            logger.exception("Knowledge indexing failed document_id=%s", document.id)
            await self._repository.fail_document(
                document.id,
                {
                    "type": type(exc).__name__,
                    "message": str(exc)[:4000],
                },
            )

    async def _extract(self, document: KnowledgeDocument) -> ParsedDocument:
        if document.source_type == "UPLOAD":
            if not document.storage_path:
                raise ValueError("Uploaded document has no storage path")
            return await asyncio.to_thread(
                self._parser.parse,
                document.storage_path,
                name=document.name,
                mime_type=document.mime_type,
            )
        if document.source_type in self.GOOGLE_TOOLS:
            if not document.source_id:
                raise ValueError("Google source has no sourceId")
            tool_name = self.GOOGLE_TOOLS[document.source_type]
            argument_name = {
                "GOOGLE_DOCS": "documentId",
                "GOOGLE_SLIDES": "presentationId",
                "GOOGLE_SHEETS": "spreadsheetId",
            }[document.source_type]
            result = await self._tool_service.execute(
                tool_name,
                {argument_name: document.source_id},
            )
            output = result.get("output")
            if not isinstance(output, dict):
                raise ValueError(f"{tool_name} returned a non-object semantic result")
            text = str(output.get("text", "")).strip()
            if not text:
                raise ValueError(f"{tool_name} returned no text")
            return ParsedDocument(
                title=str(output.get("title") or document.name),
                segments=[ParsedSegment(text, {"sourceType": document.source_type})],
                metadata={
                    "format": document.source_type.lower(),
                    "sourceMetadata": {
                        key: value for key, value in output.items() if key != "text"
                    },
                },
            )
        raise ValueError(f"Unsupported knowledge source type '{document.source_type}'")

    def _chunk(
        self,
        parsed: ParsedDocument,
        document: KnowledgeDocument,
        chunking_policy: dict[str, Any],
    ) -> list[dict[str, Any]]:
        policy = normalize_chunking_policy(chunking_policy)
        chunker = build_chunker(policy)
        chunks: list[dict[str, Any]] = []

        for segment_index, segment in enumerate(parsed.segments):
            text = segment.text.strip()
            if not text:
                continue

            for candidate in chunker.split(text):
                chunks.append(
                    {
                        "content": candidate.content,
                        "embed": candidate.embed,
                        "metadata": {
                            **segment.metadata,
                            **candidate.metadata,
                            "documentName": document.name,
                            "segment": segment_index,
                            "charStart": candidate.start,
                            "charEnd": candidate.end,
                        },
                    }
                )
        return chunks

    @staticmethod
    def format_context(hits: list[RetrievalHit]) -> str:
        if not hits:
            return "No relevant knowledge was retrieved."
        blocks = []
        for index, hit in enumerate(hits, start=1):
            blocks.append(
                f"[Knowledge {index}]\n"
                f"Document: {hit.document_name}\n"
                f"Score: {hit.score:.4f}\n"
                f"Metadata: {json.dumps(hit.metadata, ensure_ascii=False)}\n"
                f"Content:\n{hit.content}"
            )
        return "\n\n".join(blocks)

    def _validate_embedding(self, vector: list[float]) -> None:
        if len(vector) != self._embedding_provider.dimensions:
            raise RuntimeError(
                f"Embedding provider '{self._embedding_provider.provider_key}' returned "
                f"{len(vector)} dimensions; expected {self._embedding_provider.dimensions}"
            )
        if len(vector) != 768:
            raise RuntimeError(
                f"Knowledge storage expects 768 dimensions, got {len(vector)}. "
                "Change KNOWLEDGE_EMBEDDING_DIMENSIONS only together with a pgvector schema migration."
            )

    @staticmethod
    def _write_stream(stream: BinaryIO, destination: Path) -> str:
        digest = hashlib.sha256()
        stream.seek(0)
        with destination.open("wb") as target:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                digest.update(block)
                target.write(block)
        return digest.hexdigest()

    async def _delete_storage(self, storage_path: str | None) -> None:
        if not storage_path:
            return
        path = Path(storage_path)
        if path.exists():
            await asyncio.to_thread(path.unlink)
