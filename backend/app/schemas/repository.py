from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RepositoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    owner: str = Field(..., min_length=1, max_length=100)
    repository_url: str = Field(..., min_length=1, max_length=500)
    source_type: str = Field("github_public", max_length=50)
    default_branch: str = Field("main", max_length=100)
    visibility: str = Field("public", max_length=20)


class RepositoryCreate(RepositoryBase):
    pass


class RepositoryResponse(RepositoryBase):
    id: str
    owner_id: str
    current_commit_sha: Optional[str] = None
    status: str
    last_analyzed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

