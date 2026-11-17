from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CodeCitationResponse(BaseModel):
    filePath: str = Field(..., description="Repository relative file path")
    startLine: int = Field(..., description="Start line of cited code snippet")
    endLine: int = Field(..., description="End line of cited code snippet")
    snippet: Optional[str] = Field(None, description="Excerpt of cited source code")


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    confidence: str = Field("verified", description="verified | inferred | unknown")
    provider: str
    model: str
    citations: List[CodeCitationResponse] = Field(default_factory=list)
    tokenCount: Optional[int] = None


class ConversationResponse(BaseModel):
    id: str
    repositoryId: str
    title: str
    updatedAt: str
    messages: List[ChatMessageResponse] = Field(default_factory=list)


class SendMessageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000, description="User question about the codebase")


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=200, description="Optional custom conversation title")


class ChatSuggestionsResponse(BaseModel):
    repository_id: str
    suggestions: List[str]
