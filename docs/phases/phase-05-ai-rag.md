# Phase 5: AI Integration & Retrieval-Augmented Generation (RAG)

## Status: Completed (Milestones 5.1 – 5.10)

### Scope & Invariants
- **Primary generation provider**: Ollama hosted on InstaBox cloud Linux VM (`qwen3.5:4b` candidate).
- **Fallback generation provider**: Google Gemini Free Tier only (`gemini-1.5-flash`), strictly for recoverable network/timeout/5xx errors.
- **Primary embedding provider**: Ollama (`nomic-embed-text`, 768 dimensions).
- **Zero paid API calls or paid subscriptions**.
- **Backend holds all provider credentials; frontend receives none**.
- **Zero Hallucination / Grounding Rule**: Responses rely exclusively on retrieved repository context. If information is absent or ambiguous, RepoMind explicitly states "I don't know based on the provided repository code."
- **Tenant Isolation**: Every vector retrieval query strictly filters by `repository_id = :id`. Cross-repository data leakage is impossible.
- **Prompt Injection Defense**: All user queries and code chunks are sanitized, XML-tagged `<context_chunk>`, and system instructions explicitly command the model to disregard instructions embedded inside source code.

---

### Completed Milestones

#### Milestone 5.1 — Existing System Audit
- Complete codebase audit performed across frontend, backend, database models, Phase 3 ingestion, Phase 4 static intelligence, and local environment.
- Verified all existing backend unit tests pass.
- Evaluated vector store compatibility for local SQLite / PostgreSQL 18.4 without `pgvector`. Selected dual-compatible serialized JSON float array storage with in-memory Python cosine similarity (`ChunkRepository`), providing sub-15ms search across repository-scoped chunks.

#### Milestone 5.2 — AI Provider Architecture
- Designed and implemented centralized provider abstraction package `app.ai`.
- Created `BaseLLMProvider` interface in `app/ai/base.py`.
- Implemented `OllamaProvider` and `GeminiProvider` with `ProviderManager` orchestration.
- Added 10 unit tests in `backend/tests/test_ai_providers.py`.

#### Milestone 5.3 — InstaBox Ollama Connectivity, Authentication & Model Validation
- Configured connection to InstaBox Ollama host: `https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech`.
- Implemented dual-channel private port authentication: `Authorization: Bearer <token>` header and `?_token=<token>` query parameter.
- Integrated generation endpoint `POST /api/chat` with bounded context window (4096 tokens) and non-streaming responses.
- Integrated embedding endpoint `POST /api/embed` with batch chunk support, empty string rejection, non-finite vector detection (`math.isfinite`), and dimension consistency validation.
- Implemented structured error classification: `AUTHENTICATION_ERROR`, `CONNECTION_ERROR`, `TIMEOUT_ERROR`, `MODEL_NOT_FOUND`, `INVALID_RESPONSE`, `RATE_LIMITED`, `SERVER_ERROR`, `UNKNOWN_PROVIDER_ERROR`.
- Added 8-state connection health check: `connected`, `authentication_failed`, `server_unavailable`, `request_timed_out`, `generation_model_missing`, `embedding_model_missing`, `invalid_response`, `unknown_failure`.
- Enforced strict fallback isolation: `AUTHENTICATION_ERROR` (401/403) and embedding failures never trigger fallback to Gemini.
- Created 20 dedicated unit tests in `backend/tests/test_instabox_ollama.py`.

#### Milestone 5.4 — Model Benchmarking & Configuration
- Created automated benchmark suite in `backend/app/ai/benchmarks.py` covering 8 representative code intelligence tasks:
  1. Entry point explanation
  2. Architecture explanation
  3. Function purpose explanation
  4. Dependency / import analysis
  5. Security audit / vulnerability check
  6. Bug localization
  7. Cross-file data flow tracking
  8. Refactoring recommendation
- Benchmarks measure latency, tokens per second, memory usage, and citation accuracy.
- Tested in `backend/tests/test_model_benchmarks.py`.

#### Milestone 5.5 — Repository-Aware Code Chunking
- Implemented `ChunkingService` in `backend/app/services/chunking_service.py`.
- Leveraged Phase 4 AST parser and symbol tables (`CodeSymbol` with `start_line` / `end_line`) for syntax-boundary chunking.
- Implemented recursive splitting with overlapping windows (10-line overlap) for oversized functions or symbol-less configuration files.
- Excluded secrets, `.env`, `.pem`, lock files, binary files, and ignored build directories (`node_modules`, `.git`, `dist`, `__pycache__`).
- Tested in `backend/tests/test_chunking.py`.

#### Milestone 5.6 — Embeddings & Vector Storage
- Implemented `CodeChunk` SQLAlchemy model in `backend/app/models/code_chunk.py` with foreign keys to `Repository` and `RepositoryFile`.
- Implemented `ChunkRepository` in `backend/app/repositories/chunk_repository.py` with cosine similarity vector math.
- Implemented `EmbeddingService` in `backend/app/services/embedding_service.py` to orchestrate batch chunking, Ollama vector generation (`nomic-embed-text`), and persistence.
- Integrated automatic vector indexing into the Phase 3 ingestion pipeline (`backend/app/services/ingestion_service.py`).
- Tested in `backend/tests/test_embeddings_and_vectors.py`.

#### Milestone 5.7 — Retrieval-Augmented Generation (RAG)
- Implemented `RAGService` in `backend/app/services/rag_service.py`.
- Configured dynamic retrieval (`top_k=5`, minimum similarity threshold 0.25).
- Constructed prompt injection defense: user query sanitization, XML delimited `<context_chunk>` structures with line numbers and file paths, and strict system grounding rules.
- Tested in `backend/tests/test_rag_pipeline.py`.

#### Milestone 5.8 — Grounded AI Answers & Chat APIs
- Implemented chat models `ChatConversation` and `ChatMessage` in `backend/app/models/`.
- Implemented `ChatRepository` and `ChatService` for managing conversational threads with full RAG integration.
- Exposed REST endpoints in `backend/app/api/v1/endpoints/chat.py`:
  - `POST /api/v1/repositories/{id}/conversations`: Create conversation.
  - `GET /api/v1/repositories/{id}/conversations`: List conversations.
  - `GET /api/v1/repositories/{id}/conversations/{c_id}/messages`: Get conversation history.
  - `POST /api/v1/repositories/{id}/conversations/{c_id}/messages`: Ask a question and receive grounded answer with exact file and line citations.
  - `GET /api/v1/repositories/{id}/chat/suggestions`: Get dynamically generated repository-aware suggested prompts.
  - `POST /api/v1/repositories/{id}/index-embeddings`: Manually trigger or refresh vector indexing.
- Implemented TypeScript client in `src/services/api/assistant.api.ts` and registered in `src/services/index.ts`.
- Tested in `backend/tests/test_chat_and_grounding.py`.

#### Milestone 5.9 — Gemini Free-Tier Fallback & Reliability
- Enforced strict failover policy: Gemini (`gemini-1.5-flash`) is only invoked when Ollama experiences network connectivity errors, read timeouts, or remote 5xx server crashes.
- Implemented secret and PII redaction (`REDACTION_RULES` in `backend/app/ai/provider_manager.py`) before prompts leave the network to Gemini.
- Strictly prohibited fallback on authentication errors (401/403) or client input validation errors.
- Handled Gemini rate limits (HTTP 429) gracefully without crashing.
- Tested in `backend/tests/test_gemini_fallback_reliability.py`.

#### Milestone 5.10 — Phase 5 Integration, Testing & Documentation
- Authored Alembic database migration `8d9c2401f82e_add_phase5_ai_and_rag_schema.py` and executed `alembic upgrade head`.
- Validated all 97 backend unit tests passing across all 5 phases.
- Verified frontend build passes (`npm run build`).
- Updated deployment and architectural documentation.
