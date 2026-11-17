from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentVersionResponse(BaseModel):
    id: str
    document_id: str
    repository_id: str
    version_number: int
    content: str
    change_summary: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: str
    repository_id: str
    doc_type: str
    title: str
    description: str
    status: str
    confidence: str
    version_number: int
    content_length: int = 0
    last_generated_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None

    class Config:
        from_attributes = True


class DocumentDetailResponse(DocumentResponse):
    content: str
    source_evidence: Dict[str, Any] = Field(default_factory=dict)
    versions: List[DocumentVersionResponse] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    repository_id: str
    total: int
    items: List[DocumentResponse]


class GenerateDocumentationRequest(BaseModel):
    doc_types: Optional[List[str]] = Field(
        default=None,
        description="List of document types to generate. If omitted, generates all standard sections.",
    )
    force_refresh: bool = Field(
        default=False,
        description="Force full regeneration ignoring previous cached sections.",
    )


class GenerateDocumentationResponse(BaseModel):
    repository_id: str
    status: str
    generated_count: int
    documents: List[DocumentResponse]


class UpdateDocumentRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Updated Markdown content")
    change_summary: Optional[str] = Field(
        default="Manual edit in Documentation Workspace",
        description="Reason or summary of edit",
    )


class DocumentDiffResponse(BaseModel):
    doc_type: str
    base_version: int
    target_version: int
    diff_patch: str
    base_content: str
    target_content: str


class DocumentApprovalResponse(BaseModel):
    document_id: str
    doc_type: str
    status: str
    approved_at: datetime
    approved_by: str
