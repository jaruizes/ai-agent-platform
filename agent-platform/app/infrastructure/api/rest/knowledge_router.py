from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status

from app.business.knowledge_service import KnowledgeService
from app.domain.knowledge import KnowledgeBase, KnowledgeDocument
from app.infrastructure.api.rest.knowledge_schemas import (
    AgentKnowledgeAssignmentsRequest,
    GoogleDocumentRequest,
    KnowledgeBaseRequest,
    KnowledgeBaseResponse,
    KnowledgeDocumentResponse,
    RetrievalHitResponse,
    RetrievalRequest,
)


def _kb_response(kb: KnowledgeBase) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        scope=kb.scope,
        retentionPolicy=kb.retention_policy,
        expiresAt=kb.expires_at,
        enabled=kb.enabled,
        metadata=kb.metadata,
    )


def _document_response(document: KnowledgeDocument) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=document.id,
        knowledgeBaseId=document.knowledge_base_id,
        name=document.name,
        sourceType=document.source_type,
        sourceId=document.source_id,
        sourceUri=document.source_uri,
        mimeType=document.mime_type,
        status=document.status,
        version=document.version,
        checksum=document.checksum,
        metadata=document.metadata,
        error=document.error,
    )


def create_knowledge_router(service: KnowledgeService) -> APIRouter:
    router = APIRouter(prefix="/v1")

    @router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
    async def list_knowledge_bases() -> list[KnowledgeBaseResponse]:
        return [_kb_response(kb) for kb in await service.list_knowledge_bases()]

    @router.post(
        "/knowledge-bases",
        response_model=KnowledgeBaseResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_knowledge_base(request: KnowledgeBaseRequest) -> KnowledgeBaseResponse:
        try:
            kb = await service.create_knowledge_base(
                name=request.name,
                description=request.description,
                scope=request.scope,
                retention_policy=request.retentionPolicy,
                ttl_seconds=request.ttlSeconds,
                enabled=request.enabled,
                metadata=request.metadata,
            )
            return _kb_response(kb)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.put("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
    async def update_knowledge_base(
        kb_id: UUID,
        request: KnowledgeBaseRequest,
    ) -> KnowledgeBaseResponse:
        try:
            kb = await service.update_knowledge_base(
                kb_id,
                name=request.name,
                description=request.description,
                scope=request.scope,
                retention_policy=request.retentionPolicy,
                ttl_seconds=request.ttlSeconds,
                enabled=request.enabled,
                metadata=request.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        return _kb_response(kb)

    @router.delete("/knowledge-bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_knowledge_base(kb_id: UUID, response: Response) -> Response:
        if not await service.delete_knowledge_base(kb_id):
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        return response

    @router.get(
        "/knowledge-bases/{kb_id}/documents",
        response_model=list[KnowledgeDocumentResponse],
    )
    async def list_documents(kb_id: UUID) -> list[KnowledgeDocumentResponse]:
        if not await service.get_knowledge_base(kb_id):
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        return [_document_response(item) for item in await service.list_documents(kb_id)]

    @router.post(
        "/knowledge-bases/{kb_id}/documents/upload",
        response_model=KnowledgeDocumentResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def upload_document(
        kb_id: UUID,
        file: UploadFile = File(...),
        metadata: str | None = Form(default=None),
    ) -> KnowledgeDocumentResponse:
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
            document = await service.create_uploaded_document(
                kb_id,
                name=file.filename or "document",
                stream=file.file,
                mime_type=file.content_type,
                metadata=parsed_metadata,
            )
            return _document_response(document)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post(
        "/knowledge-bases/{kb_id}/documents/google",
        response_model=KnowledgeDocumentResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def add_google_document(
        kb_id: UUID,
        request: GoogleDocumentRequest,
    ) -> KnowledgeDocumentResponse:
        try:
            document = await service.create_google_document(
                kb_id,
                source_type=request.sourceType,
                source_id=request.sourceId,
                name=request.name,
                source_uri=request.sourceUri,
                metadata=request.metadata,
            )
            return _document_response(document)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put(
        "/knowledge-documents/{document_id}/content",
        response_model=KnowledgeDocumentResponse,
    )
    async def replace_uploaded_document(
        document_id: UUID,
        file: UploadFile = File(...),
        metadata: str | None = Form(default=None),
    ) -> KnowledgeDocumentResponse:
        try:
            parsed_metadata = json.loads(metadata) if metadata else {}
            document = await service.update_uploaded_document(
                document_id,
                name=file.filename or "document",
                stream=file.file,
                mime_type=file.content_type,
                metadata=parsed_metadata,
            )
        except (ValueError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if not document:
            raise HTTPException(status_code=404, detail="Knowledge document not found")
        return _document_response(document)

    @router.get("/knowledge-documents/{document_id}", response_model=KnowledgeDocumentResponse)
    async def get_document(document_id: UUID) -> KnowledgeDocumentResponse:
        document = await service._repository.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Knowledge document not found")
        return _document_response(document)

    @router.post("/knowledge-documents/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
    async def reindex_document(document_id: UUID) -> dict:
        if not await service.reindex_document(document_id):
            raise HTTPException(status_code=404, detail="Knowledge document not found")
        return {"documentId": str(document_id), "status": "PENDING"}

    @router.delete("/knowledge-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_document(document_id: UUID, response: Response) -> Response:
        if not await service.delete_document(document_id):
            raise HTTPException(status_code=404, detail="Knowledge document not found")
        return response

    @router.post("/knowledge/retrieve", response_model=list[RetrievalHitResponse])
    async def retrieve(request: RetrievalRequest) -> list[RetrievalHitResponse]:
        hits = await service.retrieve(
            query=request.query,
            knowledge_base_names=request.knowledgeBases,
            top_k=request.topK,
        )
        return [
            RetrievalHitResponse(
                chunkId=hit.chunk_id,
                documentId=hit.document_id,
                knowledgeBaseId=hit.knowledge_base_id,
                documentName=hit.document_name,
                content=hit.content,
                score=hit.score,
                metadata=hit.metadata,
            )
            for hit in hits
        ]

    @router.put("/agents/{agent_id}/knowledge-bases")
    async def assign_agent_knowledge(
        agent_id: UUID,
        request: AgentKnowledgeAssignmentsRequest,
    ) -> dict:
        try:
            await service.replace_agent_knowledge_bases(
                agent_id,
                [item.model_dump() for item in request.knowledgeBases],
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "agentId": str(agent_id),
            "knowledgeBases": [
                item.model_dump() for item in request.knowledgeBases
            ],
        }

    @router.get("/agents/{agent_id}/knowledge-bases")
    async def list_agent_knowledge(agent_id: UUID) -> list[dict]:
        assignments = await service.list_agent_knowledge_bases(agent_id)
        return [
            {
                "id": str(item["knowledgeBase"].id),
                "name": item["knowledgeBase"].name,
                "description": item["knowledgeBase"].description,
                "usageMode": item["usageMode"],
            }
            for item in assignments
        ]

    return router
