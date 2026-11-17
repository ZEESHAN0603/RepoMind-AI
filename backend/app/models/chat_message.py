import json
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.chat_conversation import ChatConversation


class ChatMessage(Base, TimestampMixin):
    """Individual chat turn (user prompt or grounded assistant reply) within a conversation."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    conversation_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), default="verified", nullable=False)  # "verified", "inferred", "unknown"
    provider: Mapped[str] = mapped_column(String(50), default="ollama", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="qwen3.5:4b", nullable=False)
    citations_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)  # JSON list of CodeCitation
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="messages")

    @property
    def citations(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.citations_json)
        except Exception:
            return []

    @citations.setter
    def citations(self, citations_list: List[Dict[str, Any]]) -> None:
        self.citations_json = json.dumps(citations_list)

    __table_args__ = (
        Index("ix_chat_messages_conv_created", "conversation_id", "created_at"),
    )
