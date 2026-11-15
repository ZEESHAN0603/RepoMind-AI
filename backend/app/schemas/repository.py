from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepositoryBase(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    owner: Optional[str] = Field(None, min_length=1, max_length=100)
    repository_url: str = Field(..., min_length=1, max_length=500)
    source_type: str = Field("github_public", max_length=50)
    default_branch: str = Field("main", max_length=100)
    visibility: str = Field("public", max_length=20)
    description: Optional[str] = Field(None, max_length=500)


class RepositoryCreate(BaseModel):
    repository_url: str = Field(..., min_length=1, max_length=500)
    name: Optional[str] = Field(None, max_length=150)
    owner: Optional[str] = Field(None, max_length=100)
    branch: Optional[str] = Field(None, max_length=100)
    default_branch: Optional[str] = Field("main", max_length=100)
    source_type: Optional[str] = Field("github_public", max_length=50)
    visibility: Optional[str] = Field("public", max_length=20)
    is_private: Optional[bool] = Field(False)
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("source_type", mode="before")
    @classmethod
    def normalize_source_type(cls, v: Optional[str]) -> str:
        if not v:
            return "github_public"
        v_lower = v.lower()
        if v_lower in ("github", "github_public"):
            return "github_public"
        if v_lower in ("github_private", "private"):
            return "github_private"
        if v_lower in ("zip", "zip_upload"):
            return "zip_upload"
        return v_lower


class RepositoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    default_branch: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    is_archived: Optional[bool] = None


class RepositoryBranchResponse(BaseModel):
    id: str
    name: str
    commit_sha: Optional[str] = None
    is_default: bool = False

    model_config = ConfigDict(from_attributes=True)


class RepositoryLanguageResponse(BaseModel):
    id: str
    language: str
    byte_count: int
    file_count: int
    percentage: float
    color: str

    model_config = ConfigDict(from_attributes=True)


class RepositoryManifestResponse(BaseModel):
    id: str
    file_path: str
    ecosystem: str
    manifest_type: str
    detected_frameworks: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class IngestionJobResponse(BaseModel):
    id: str
    repository_id: str
    status: str
    progress_percent: int
    current_stage: str
    error_message: Optional[str] = None
    retry_count: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    owner: str
    repository_url: str
    source_type: str
    default_branch: str
    current_commit_sha: Optional[str] = None
    visibility: str
    status: str
    description: Optional[str] = None
    size_bytes: int = 0
    file_count: int = 0
    folder_count: int = 0
    is_archived: bool = False
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RepositoryFileNode(BaseModel):
    id: str
    name: str
    path: str
    type: str  # "file" or "folder"
    language: Optional[str] = None
    size_bytes: int = 0
    is_binary: bool = False
    children: Optional[List["RepositoryFileNode"]] = None

    model_config = ConfigDict(from_attributes=True)


class RepositoryOverviewResponse(BaseModel):
    repository: RepositoryResponse
    available_branches: List[RepositoryBranchResponse] = []
    languages: List[RepositoryLanguageResponse] = []
    manifests: List[RepositoryManifestResponse] = []
    latest_job: Optional[IngestionJobResponse] = None
    file_count: int = 0
    folder_count: int = 0
    size_bytes: int = 0


class GitHubStatusResponse(BaseModel):
    is_connected: bool
    github_username: Optional[str] = None
    scope: Optional[str] = None
    connected_at: Optional[datetime] = None


class GitHubConnectUrlResponse(BaseModel):
    authorization_url: str
