from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatMessageResponse,
    ChatSuggestionsResponse,
    CodeCitationResponse,
    ConversationResponse,
    CreateConversationRequest,
    SendMessageRequest,
)
from app.services.chat_service import ChatService
from app.services.embedding_service import EmbeddingService

router = APIRouter()
chat_service = ChatService()
embedding_service = EmbeddingService()


def _map_message_to_response(msg: ChatMessage) -> ChatMessageResponse:
    citations = [
        CodeCitationResponse(
            filePath=c.get("filePath", ""),
            startLine=c.get("startLine", 1),
            endLine=c.get("endLine", 1),
            snippet=c.get("snippet"),
        )
        for c in msg.citations
    ]
    return ChatMessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        timestamp=msg.created_at.isoformat() if msg.created_at else "",
        confidence=msg.confidence,
        provider=msg.provider,
        model=msg.model,
        citations=citations,
        tokenCount=msg.token_count,
    )


def _map_conversation_to_response(conv: ChatConversation) -> ConversationResponse:
    return ConversationResponse(
        id=conv.id,
        repositoryId=conv.repository_id,
        title=conv.title,
        updatedAt=conv.updated_at.isoformat() if conv.updated_at else "",
        messages=[_map_message_to_response(m) for m in (conv.messages or [])],
    )


@router.get(
    "/{repository_id}/conversations",
    response_model=List[ConversationResponse],
    summary="List repository conversations",
    description="Retrieves all chat conversations owned by the user for the given repository.",
)
async def list_conversations(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ConversationResponse]:
    convs = await chat_service.list_conversations(db, repository_id, current_user.id)
    return [_map_conversation_to_response(c) for c in convs]


@router.post(
    "/{repository_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create chat conversation",
    description="Initializes a new grounded conversation thread for this repository.",
)
async def create_conversation(
    repository_id: str,
    payload: Optional[CreateConversationRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    title = payload.title if payload else None
    conv = await chat_service.create_conversation(db, repository_id, current_user.id, title)
    return _map_conversation_to_response(conv)


@router.get(
    "/{repository_id}/conversations/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation details",
    description="Retrieves a specific conversation with all historical turns and citations.",
)
async def get_conversation(
    repository_id: str,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    conv = await chat_service.get_conversation(db, repository_id, conversation_id, current_user.id)
    return _map_conversation_to_response(conv)


@router.delete(
    "/{repository_id}/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
    description="Deletes a conversation thread and its message history.",
)
async def delete_conversation(
    repository_id: str,
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await chat_service.delete_conversation(db, repository_id, conversation_id, current_user.id)


@router.post(
    "/{repository_id}/conversations/{conversation_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Send message / ask question",
    description="Processes a question through the RAG pipeline, queries Ollama (with Gemini fallback), and returns an evidence-grounded answer with citations.",
)
async def send_message(
    repository_id: str,
    conversation_id: str,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    msg = await chat_service.send_message(
        session=db,
        repository_id=repository_id,
        conversation_id=conversation_id,
        user_id=current_user.id,
        prompt=payload.prompt,
    )
    return _map_message_to_response(msg)


@router.get(
    "/{repository_id}/chat/suggestions",
    response_model=ChatSuggestionsResponse,
    summary="Get suggested questions",
    description="Returns intelligent, codebase-tailored starter questions based on discovered static analysis symbols and endpoints.",
)
async def get_chat_suggestions(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatSuggestionsResponse:
    suggestions = await chat_service.get_suggested_questions(db, repository_id, current_user.id)
    return ChatSuggestionsResponse(repository_id=repository_id, suggestions=suggestions)


@router.post(
    "/{repository_id}/index-embeddings",
    status_code=status.HTTP_200_OK,
    summary="Trigger vector embedding indexing",
    description="Runs code chunking and dense vector embedding generation across all repository files using Ollama.",
)
async def index_embeddings(
    repository_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await embedding_service.index_repository_embeddings(db, repository_id, current_user.id)
