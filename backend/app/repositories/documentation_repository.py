from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.base import utc_now
from app.models.repository_document import RepositoryDocument, RepositoryDocumentVersion


class DocumentationRepository:
    """Data access repository for repository documentation and version history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_document_by_type(
        self,
        repository_id: str,
        doc_type: str,
        include_versions: bool = False,
    ) -> Optional[RepositoryDocument]:
        query = select(RepositoryDocument).where(
            RepositoryDocument.repository_id == repository_id,
            RepositoryDocument.doc_type == doc_type,
        )
        if include_versions:
            query = query.options(selectinload(RepositoryDocument.versions))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_document_by_id(
        self,
        document_id: str,
        include_versions: bool = False,
    ) -> Optional[RepositoryDocument]:
        query = select(RepositoryDocument).where(RepositoryDocument.id == document_id)
        if include_versions:
            query = query.options(selectinload(RepositoryDocument.versions))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_documents_by_repo(
        self,
        repository_id: str,
    ) -> List[RepositoryDocument]:
        query = (
            select(RepositoryDocument)
            .where(RepositoryDocument.repository_id == repository_id)
            .order_by(RepositoryDocument.doc_type)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def save_or_update_document(
        self,
        repository_id: str,
        doc_type: str,
        title: str,
        description: str,
        content: str,
        status: str = "draft",
        confidence: str = "verified",
        source_evidence: Optional[Dict[str, Any]] = None,
        change_summary: Optional[str] = "Initial generation",
        user_id: Optional[str] = None,
    ) -> RepositoryDocument:
        """
        Creates or updates a document and creates a version snapshot.
        """
        now = utc_now()
        evidence_json = json.dumps(source_evidence or {})
        existing = await self.get_document_by_type(repository_id, doc_type)

        if existing:
            new_version_num = existing.version_number + 1
            existing.title = title
            existing.description = description
            existing.content = content
            existing.status = status
            existing.confidence = confidence
            existing.source_evidence_json = evidence_json
            existing.version_number = new_version_num
            existing.last_generated_at = now

            version = RepositoryDocumentVersion(
                document_id=existing.id,
                repository_id=repository_id,
                version_number=new_version_num,
                content=content,
                change_summary=change_summary,
                created_by=user_id,
                created_at=now,
            )
            self.session.add(version)
            await self.session.flush()
            return existing

        # Create fresh document
        new_doc = RepositoryDocument(
            repository_id=repository_id,
            doc_type=doc_type,
            title=title,
            description=description,
            content=content,
            status=status,
            confidence=confidence,
            source_evidence_json=evidence_json,
            version_number=1,
            last_generated_at=now,
        )
        self.session.add(new_doc)
        await self.session.flush()

        # Create version 1 record
        version_1 = RepositoryDocumentVersion(
            document_id=new_doc.id,
            repository_id=repository_id,
            version_number=1,
            content=content,
            change_summary=change_summary or "Initial version",
            created_by=user_id,
            created_at=now,
        )
        self.session.add(version_1)
        await self.session.flush()
        return new_doc

    async def update_document_content(
        self,
        doc_id: str,
        content: str,
        change_summary: str,
        user_id: Optional[str] = None,
    ) -> RepositoryDocument:
        doc = await self.get_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        now = utc_now()
        new_version_num = doc.version_number + 1
        doc.content = content
        doc.version_number = new_version_num
        doc.updated_at = now

        version = RepositoryDocumentVersion(
            document_id=doc.id,
            repository_id=doc.repository_id,
            version_number=new_version_num,
            content=content,
            change_summary=change_summary,
            created_by=user_id,
            created_at=now,
        )
        self.session.add(version)
        await self.session.flush()
        return doc

    async def approve_document(
        self,
        doc_id: str,
        user_id: str,
    ) -> RepositoryDocument:
        doc = await self.get_document_by_id(doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")

        doc.status = "approved"
        doc.approved_at = utc_now()
        doc.approved_by = user_id
        await self.session.flush()
        return doc

    async def list_versions(
        self,
        doc_id: str,
    ) -> List[RepositoryDocumentVersion]:
        query = (
            select(RepositoryDocumentVersion)
            .where(RepositoryDocumentVersion.document_id == doc_id)
            .order_by(desc(RepositoryDocumentVersion.version_number))
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_version(
        self,
        doc_id: str,
        version_number: int,
    ) -> Optional[RepositoryDocumentVersion]:
        query = select(RepositoryDocumentVersion).where(
            RepositoryDocumentVersion.document_id == doc_id,
            RepositoryDocumentVersion.version_number == version_number,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def mark_documents_as_stale(
        self,
        repository_id: str,
        doc_types: Optional[List[str]] = None,
    ) -> List[RepositoryDocument]:
        """
        Transitions approved documents to 'stale' status when a repository update occurs,
        identifying outdated documentation without destructively overwriting approved content.
        """
        query = select(RepositoryDocument).where(
            RepositoryDocument.repository_id == repository_id,
            RepositoryDocument.status == "approved",
        )
        if doc_types:
            query = query.where(RepositoryDocument.doc_type.in_(doc_types))

        result = await self.session.execute(query)
        stale_docs = list(result.scalars().all())
        for doc in stale_docs:
            doc.status = "stale"
            doc.updated_at = utc_now()
        await self.session.flush()
        return stale_docs
