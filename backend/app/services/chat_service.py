import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider_manager import ProviderManager
from app.ai.schemas import ChatMessage as AIChatMessage, GenerationResult
from app.core.config import settings
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logging import logger
from app.models.chat_conversation import ChatConversation
from app.models.chat_message import ChatMessage
from app.repositories.chat_repository import ChatRepository
from app.repositories.code_intelligence_repository import CodeIntelligenceRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.rag_service import RAGService, RetrievalResult, RetrievedChunk


class ChatService:
    """
    Orchestrates repository-grounded conversations, citation building,
    evidence confidence classification, and conversational persistence.
    """

    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        provider_manager: Optional[ProviderManager] = None,
    ) -> None:
        self.rag_service = rag_service or RAGService()
        self.provider_manager = provider_manager or ProviderManager()

    async def _verify_repo_access(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> None:
        repo_repo = RepositoryRepository(session)
        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")
        if repo.owner_id != user_id:
            raise ForbiddenException("You do not have permission to access this repository")

    async def list_conversations(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> List[ChatConversation]:
        await self._verify_repo_access(session, repository_id, user_id)
        chat_repo = ChatRepository(session)
        return await chat_repo.list_conversations(repository_id, user_id)

    async def get_conversation(
        self,
        session: AsyncSession,
        repository_id: str,
        conversation_id: str,
        user_id: str,
    ) -> ChatConversation:
        await self._verify_repo_access(session, repository_id, user_id)
        chat_repo = ChatRepository(session)
        conv = await chat_repo.get_conversation(conversation_id)
        if not conv or conv.repository_id != repository_id:
            raise NotFoundException("Conversation not found")
        if conv.user_id != user_id:
            raise ForbiddenException("You do not have access to this conversation")
        return conv

    async def create_conversation(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
        title: Optional[str] = None,
    ) -> ChatConversation:
        await self._verify_repo_access(session, repository_id, user_id)
        chat_repo = ChatRepository(session)
        new_conv = ChatConversation(
            repository_id=repository_id,
            user_id=user_id,
            title=title or "New repository inquiry",
        )
        saved = await chat_repo.create_conversation(new_conv)
        await session.commit()
        return saved

    async def delete_conversation(
        self,
        session: AsyncSession,
        repository_id: str,
        conversation_id: str,
        user_id: str,
    ) -> None:
        await self.get_conversation(session, repository_id, conversation_id, user_id)
        chat_repo = ChatRepository(session)
        await chat_repo.delete_conversation(conversation_id)
        await session.commit()

    def _determine_confidence(self, answer_text: str, has_evidence: bool) -> str:
        """Determines factual classification: verified | inferred | unknown."""
        lower = answer_text.lower()
        if not has_evidence or "unknown" in lower or "does not contain" in lower or "insufficient information" in lower:
            return "unknown"
        if "infer" in lower or "likely" in lower or "suggests" in lower or "probably" in lower:
            return "inferred"
        return "verified"

    async def send_message(
        self,
        session: AsyncSession,
        repository_id: str,
        conversation_id: str,
        user_id: str,
        prompt: str,
    ) -> ChatMessage:
        """
        Processes a user question:
        1. Persists user prompt turn.
        2. Retrieves relevant repository chunks.
        3. Formulates prompt with strict evidence grounding rules.
        4. Queries Ollama (with Gemini fallback if enabled).
        5. Builds verified citations from retrieved chunk metadata.
        6. Persists and returns grounded assistant response.
        """
        await self._verify_repo_access(session, repository_id, user_id)
        chat_repo = ChatRepository(session)

        # Ensure conversation exists and is owned by user
        conv = await chat_repo.get_conversation(conversation_id)
        if not conv:
            conv = ChatConversation(
                id=conversation_id,
                repository_id=repository_id,
                user_id=user_id,
                title=prompt[:40] + ("..." if len(prompt) > 40 else ""),
            )
            conv = await chat_repo.create_conversation(conv)
        elif conv.user_id != user_id:
            raise ForbiddenException("You do not have access to this conversation")

        # 1. Save user prompt message
        user_msg = ChatMessage(
            conversation_id=conv.id,
            role="user",
            content=prompt,
            confidence="verified",
            provider="client",
            model="user",
            citations_json="[]",
        )
        await chat_repo.add_message(user_msg)

        # 2. Retrieve repository-scoped evidence
        retrieval: RetrievalResult = await self.rag_service.retrieve_context(
            session=session,
            repository_id=repository_id,
            user_id=user_id,
            query=prompt,
            top_k=6,
            min_similarity=0.25,
        )

        has_evidence = len(retrieval.chunks) > 0

        # Build citations strictly from retrieved chunks
        citations = [
            {
                "filePath": c.file_path,
                "startLine": c.start_line,
                "endLine": c.end_line,
                "snippet": c.content[:180] + ("..." if len(c.content) > 180 else ""),
            }
            for c in retrieval.chunks
        ]

        # 3. Assemble Grounded Prompt
        system_instruction = (
            "You are RepoMind's expert software architecture and code intelligence assistant.\n"
            "Analyze the user's question using ONLY the provided repository evidence below.\n"
            "Rules:\n"
            "1. Ground all statements in the retrieved source code.\n"
            "2. If the repository does not contain enough evidence to answer accurately, explicitly state that it is UNKNOWN.\n"
            "3. Never invent file paths, method signatures, line numbers, or passwords.\n"
            "4. Clearly distinguish verified code facts from inferences.\n"
            "5. Cite relevant file paths when discussing implementation details."
        )

        llm_messages: List[AIChatMessage] = [
            AIChatMessage(
                role="user",
                content=(
                    f"--- REPOSITORY CONTEXT ---\n"
                    f"{retrieval.assembled_context}\n\n"
                    f"--- USER QUESTION ---\n"
                    f"{prompt}"
                ),
            )
        ]

        # 4. Generate answer via ProviderManager (Ollama primary, Gemini fallback)
        gen_result: GenerationResult = await self.provider_manager.generate_chat(
            messages=llm_messages,
            system_prompt=system_instruction,
            temperature=0.2,
        )

        confidence = self._determine_confidence(gen_result.content, has_evidence)

        # 5. Persist assistant reply
        assistant_msg = ChatMessage(
            conversation_id=conv.id,
            role="assistant",
            content=gen_result.content,
            confidence=confidence,
            provider=gen_result.provider,
            model=gen_result.model,
            citations_json=json.dumps(citations),
            token_count=gen_result.usage.total_tokens,
        )
        saved_msg = await chat_repo.add_message(assistant_msg)

        # Update conversation title if default
        if conv.title == "New repository inquiry":
            conv.title = prompt[:45] + ("..." if len(prompt) > 45 else "")

        conv.updated_at = datetime.now(timezone.utc)
        await session.commit()

        return saved_msg

    async def get_suggested_questions(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> List[str]:
        """Generates dynamic suggested questions grounded in the repository's discovered assets."""
        await self._verify_repo_access(session, repository_id, user_id)
        ci_repo = CodeIntelligenceRepository(session)
        file_repo = FileRepository(session)

        # Fetch endpoints and symbols
        endpoints = await ci_repo.list_endpoints_by_repo(repository_id)
        symbols, _ = await ci_repo.list_symbols_by_repo(repository_id, limit=10)
        languages = await file_repo.list_languages_by_repo(repository_id)

        suggestions = [
            "Explain the overall project architecture and key components.",
            "Where is user authentication and session handling implemented?",
        ]

        if endpoints:
            first_ep = endpoints[0]
            suggestions.append(f"How does the `{first_ep.http_method} {first_ep.path}` endpoint work?")

        if symbols:
            first_sym = symbols[0]
            suggestions.append(f"Explain the implementation and responsibilities of `{first_sym.name}`.")

        primary_lang = languages[0].language if languages else "this project"
        suggestions.append(f"What external libraries and frameworks does {primary_lang} rely on?")
        suggestions.append("Are there any security risks or missing validations in this codebase?")

        return suggestions[:6]
