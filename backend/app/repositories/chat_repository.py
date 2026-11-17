from typing import List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage


class ChatRepository:
    """Data access repository for chat conversations and message history."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_conversation(self, conversation: ChatConversation) -> ChatConversation:
        self.session.add(conversation)
        await self.session.flush()
        return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[ChatConversation]:
        query = (
            select(ChatConversation)
            .options(selectinload(ChatConversation.messages))
            .where(ChatConversation.id == conversation_id)
        )
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def list_conversations(
        self,
        repository_id: str,
        user_id: str,
    ) -> List[ChatConversation]:
        query = (
            select(ChatConversation)
            .options(selectinload(ChatConversation.messages))
            .where(
                ChatConversation.repository_id == repository_id,
                ChatConversation.user_id == user_id,
            )
            .order_by(ChatConversation.updated_at.desc())
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def delete_conversation(self, conversation_id: str) -> None:
        await self.session.execute(
            delete(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        await self.session.flush()

    async def add_message(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        await self.session.flush()
        return message

    async def list_messages(self, conversation_id: str) -> List[ChatMessage]:
        query = (
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.created_at.asc())
        )
        res = await self.session.execute(query)
        return list(res.scalars().all())
