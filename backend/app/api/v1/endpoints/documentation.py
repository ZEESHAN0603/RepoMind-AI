import difflib
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.exceptions import BadRequestException, ForbiddenException, NotFoundException
from app.db.session import get_db
from app.models.user import User
from app.repositories.documentation_repository import DocumentationRepository
from app.repositories.repository_repository import RepositoryRepository
from app.schemas.documentation import (
    DocumentApprovalResponse,
    DocumentDetailResponse,
    DocumentDiffResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentVersionResponse,
    GenerateDocumentationRequest,
    GenerateDocumentationResponse,
    UpdateDocumentRequest,
)
from app.services.documentation_export_service import DocumentationExportService
from app.services.documentation_generation_service import DocumentationGenerationService

router = APIRouter()
doc_gen_service = DocumentationGenerationService()


async def _verify_repo_ownership(
    repository_id: str,
    user_id: str,
    db: AsyncSession,
):
    repo_repo = RepositoryRepository(db)
    repo = await repo_repo.get_by_id(repository_id)
    if not repo:
        raise NotFoundException("Repository not found")
    if repo.owner_id != user_id:
        raise ForbiddenException("You do not have access to this repository")
    return repo


@router.post(
    "/{repository_id}/documentation/generate",
    response_model=GenerateDocumentationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate automatic repository documentation",
    description="Analyzes repository intelligence across Phases 3–9 and generates structured technical documentation.",
)
async def generate_documentation(
    repository_id: str,
    payload: GenerateDocumentationRequest = GenerateDocumentationRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateDocumentationResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    generated = await doc_gen_service.generate_all_documents(
        session=db,
        repository_id=repository_id,
        user_id=current_user.id,
        doc_types=payload.doc_types,
        force_refresh=payload.force_refresh,
    )
    return GenerateDocumentationResponse(
        repository_id=repository_id,
        status="completed",
        generated_count=len(generated),
        documents=[DocumentResponse.model_validate(d) for d in generated],
    )


@router.get(
    "/{repository_id}/documentation",
    response_model=DocumentListResponse,
    summary="List generated repository documents",
    description="Returns metadata and status for all documentation sections associated with a repository.",
)
async def list_documents(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    docs = await doc_repo.list_documents_by_repo(repository_id)

    items = []
    for d in docs:
        items.append(
            DocumentResponse(
                id=d.id,
                repository_id=d.repository_id,
                doc_type=d.doc_type,
                title=d.title,
                description=d.description,
                status=d.status,
                confidence=d.confidence,
                version_number=d.version_number,
                content_length=len(d.content),
                last_generated_at=d.last_generated_at,
                approved_at=d.approved_at,
                approved_by=d.approved_by,
            )
        )

    return DocumentListResponse(
        repository_id=repository_id,
        total=len(items),
        items=items,
    )


@router.get(
    "/{repository_id}/documentation/export-package",
    summary="Export complete documentation package as ZIP archive",
    description="Streams a compressed ZIP package containing all Markdown documentation and an index file.",
)
async def export_documentation_package(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    docs = await doc_repo.list_documents_by_repo(repository_id)

    if not docs:
        raise NotFoundException("No documentation has been generated for this repository yet.")

    zip_bytes, filename = DocumentationExportService.export_as_zip_package(repo, docs)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{repository_id}/documentation/{doc_type}",
    response_model=DocumentDetailResponse,
    summary="Get single document detail",
    description="Returns full Markdown content, version history, and source evidence citations.",
)
async def get_document(
    repository_id: str,
    doc_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    doc = await doc_repo.get_document_by_type(repository_id, doc_type, include_versions=True)

    if not doc:
        raise NotFoundException(f"Documentation section '{doc_type}' not found for this repository.")

    evidence: dict = {}
    try:
        evidence = json.loads(doc.source_evidence_json or "{}")
    except Exception:
        pass

    versions = [
        DocumentVersionResponse(
            id=v.id,
            document_id=v.document_id,
            repository_id=v.repository_id,
            version_number=v.version_number,
            content=v.content,
            change_summary=v.change_summary,
            created_by=v.created_by,
            created_at=v.created_at,
        )
        for v in (doc.versions or [])
    ]

    return DocumentDetailResponse(
        id=doc.id,
        repository_id=doc.repository_id,
        doc_type=doc.doc_type,
        title=doc.title,
        description=doc.description,
        status=doc.status,
        confidence=doc.confidence,
        version_number=doc.version_number,
        content=doc.content,
        content_length=len(doc.content),
        last_generated_at=doc.last_generated_at,
        approved_at=doc.approved_at,
        approved_by=doc.approved_by,
        source_evidence=evidence,
        versions=versions,
    )


@router.put(
    "/{repository_id}/documentation/{doc_type}",
    response_model=DocumentDetailResponse,
    summary="Update document content",
    description="Saves manual edits to a document, automatically bumping its version number.",
)
async def update_document(
    repository_id: str,
    doc_type: str,
    payload: UpdateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDetailResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    doc = await doc_repo.get_document_by_type(repository_id, doc_type)

    if not doc:
        raise NotFoundException(f"Document '{doc_type}' not found")

    updated_doc = await doc_repo.update_document_content(
        doc_id=doc.id,
        content=payload.content,
        change_summary=payload.change_summary or "Manual user edit",
        user_id=current_user.id,
    )
    await db.commit()

    return await get_document(repository_id, doc_type, current_user, db)


@router.post(
    "/{repository_id}/documentation/{doc_type}/approve",
    response_model=DocumentApprovalResponse,
    summary="Approve document",
    description="Marks a document as approved by the authenticated user.",
)
async def approve_document(
    repository_id: str,
    doc_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentApprovalResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    doc = await doc_repo.get_document_by_type(repository_id, doc_type)

    if not doc:
        raise NotFoundException(f"Document '{doc_type}' not found")

    approved = await doc_repo.approve_document(doc.id, current_user.id)
    await db.commit()

    return DocumentApprovalResponse(
        document_id=approved.id,
        doc_type=approved.doc_type,
        status=approved.status,
        approved_at=approved.approved_at,
        approved_by=approved.approved_by or current_user.id,
    )


@router.get(
    "/{repository_id}/documentation/{doc_type}/diff",
    response_model=DocumentDiffResponse,
    summary="Compare document versions",
    description="Computes a unified diff patch between two version snapshots of a document.",
)
async def compare_document_versions(
    repository_id: str,
    doc_type: str,
    v1: int = Query(..., ge=1, description="Base version number"),
    v2: int = Query(..., ge=1, description="Target version number"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDiffResponse:
    await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    doc = await doc_repo.get_document_by_type(repository_id, doc_type)

    if not doc:
        raise NotFoundException(f"Document '{doc_type}' not found")

    ver1 = await doc_repo.get_version(doc.id, v1)
    ver2 = await doc_repo.get_version(doc.id, v2)

    if not ver1 or not ver2:
        raise NotFoundException("One or both requested versions do not exist")

    c1_lines = ver1.content.splitlines(keepends=True)
    c2_lines = ver2.content.splitlines(keepends=True)
    diff = list(difflib.unified_diff(
        c1_lines,
        c2_lines,
        fromfile=f"v{v1}",
        tofile=f"v{v2}",
    ))
    diff_patch = "".join(diff)

    return DocumentDiffResponse(
        doc_type=doc_type,
        base_version=v1,
        target_version=v2,
        diff_patch=diff_patch,
        base_content=ver1.content,
        target_content=ver2.content,
    )


@router.get(
    "/{repository_id}/documentation/{doc_type}/export",
    summary="Export single document",
    description="Streams an individual document formatted as Markdown (.md) or standalone HTML (.html).",
)
async def export_document(
    repository_id: str,
    doc_type: str,
    format: str = Query("markdown", pattern="^(markdown|html)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    repo = await _verify_repo_ownership(repository_id, current_user.id, db)
    doc_repo = DocumentationRepository(db)
    doc = await doc_repo.get_document_by_type(repository_id, doc_type)

    if not doc:
        raise NotFoundException(f"Document '{doc_type}' not found")

    if format == "html":
        content_bytes, filename = DocumentationExportService.export_as_html(doc, repo)
        media_type = "text/html; charset=utf-8"
    else:
        content_bytes, filename = DocumentationExportService.export_as_markdown(doc)
        media_type = "text/markdown; charset=utf-8"

    return Response(
        content=content_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
