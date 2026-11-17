from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


FileChangeType = Literal["added", "modified", "deleted", "renamed"]
FileCategoryType = Literal["source", "config", "manifest", "documentation", "other"]
ImpactLevelType = Literal[
    "directly_changed",
    "directly_affected",
    "indirectly_affected",
    "potentially_affected",
    "unknown",
]


class RepositoryVersionResponse(BaseModel):
    id: str
    repository_id: str
    version_tag: str
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    author_name: Optional[str] = None
    author_email: Optional[str] = None
    commit_timestamp: Optional[datetime] = None
    source_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileChangeResponse(BaseModel):
    id: str
    update_run_id: str
    path: str
    old_path: Optional[str] = None
    change_type: FileChangeType
    file_category: FileCategoryType
    additions: int = 0
    deletions: int = 0
    old_size_bytes: int = 0
    new_size_bytes: int = 0
    old_content_hash: Optional[str] = None
    new_content_hash: Optional[str] = None
    diff_patch: Optional[str] = None
    summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SymbolChangeResponse(BaseModel):
    id: str
    update_run_id: str
    file_change_id: Optional[str] = None
    symbol_name: str
    symbol_type: str
    scope: Optional[str] = None
    change_type: FileChangeType
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ImpactRecordResponse(BaseModel):
    id: str
    update_run_id: str
    affected_type: str
    affected_identifier: str
    affected_path: str
    impact_level: ImpactLevelType
    evidence_reason: str
    source_change_symbol_id: Optional[str] = None
    depth: int = 1

    model_config = ConfigDict(from_attributes=True)


class UpdateRunStats(BaseModel):
    files_changed: int = 0
    additions: int = 0
    deletions: int = 0
    symbols_changed: int = 0
    endpoints_affected: int = 0


class ImpactMetrics(BaseModel):
    directly_changed: int = 0
    directly_affected: int = 0
    indirectly_affected: int = 0
    potentially_affected: int = 0
    unknown: int = 0


class UpdateRunResponse(BaseModel):
    id: str
    repository_id: str
    base_version_id: Optional[str] = None
    target_version_id: str
    base_commit_sha: Optional[str] = None
    target_commit_sha: Optional[str] = None
    status: str
    total_files_changed: int
    total_symbols_changed: int
    total_additions: int
    total_deletions: int
    ai_summary_status: str
    analyzed_at: Optional[datetime] = None
    created_at: datetime
    base_version: Optional[RepositoryVersionResponse] = None
    target_version: Optional[RepositoryVersionResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UpdateRunDetailResponse(UpdateRunResponse):
    stats: UpdateRunStats
    impact_metrics: ImpactMetrics
    impact_summary: Dict[str, Any] = Field(default_factory=dict)
    ai_summary_markdown: Optional[str] = None
    file_changes: List[FileChangeResponse] = Field(default_factory=list)
    symbol_changes: List[SymbolChangeResponse] = Field(default_factory=list)
    impact_records: List[ImpactRecordResponse] = Field(default_factory=list)


class UpdateRunCreateRequest(BaseModel):
    base_version_id: Optional[str] = None
    target_version_id: Optional[str] = None
    base_commit_sha: Optional[str] = None
    target_commit_sha: Optional[str] = None
    include_ai_summary: bool = True


class AdHocCompareRequest(BaseModel):
    base_commit_sha: Optional[str] = None
    target_commit_sha: str
    include_ai_summary: bool = False


class AIExplainRequest(BaseModel):
    focus: Optional[str] = None  # "general", "breaking_changes", "security", "api_impact"


class AIExplainResponse(BaseModel):
    update_run_id: str
    ai_summary_markdown: str
    provider_used: str
    model_used: str
    generated_at: datetime


class UpdateHistoryResponse(BaseModel):
    repository_id: str
    current_commit_sha: Optional[str] = None
    latest_remote_sha: Optional[str] = None
    has_pending_updates: bool = False
    total_runs: int = 0
    update_runs: List[UpdateRunResponse] = Field(default_factory=list)
    versions: List[RepositoryVersionResponse] = Field(default_factory=list)


class ImpactGraphNode(BaseModel):
    id: str
    label: str
    node_type: str  # "file", "symbol", "endpoint", "module"
    impact_level: ImpactLevelType
    path: str


class ImpactGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str  # "calls", "imports", "routes_to", "modifies"
    impact_level: ImpactLevelType


class ImpactGraphResponse(BaseModel):
    update_run_id: str
    nodes: List[ImpactGraphNode]
    edges: List[ImpactGraphEdge]
