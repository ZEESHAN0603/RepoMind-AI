# AI & RAG Architecture (Phase 5)

## 1. Provider Priority & Architectural Invariants

RepoMind adheres to a strict dual-provider AI hierarchy:

1. **Primary Generation Provider: Ollama**
   - Development target: `http://localhost:11434`
   - Production target: Remote InstaBox instance running Ollama over protected HTTPS with token authentication:
     `https://11434-agq6j3olyzqnjz6i3vl5zgyvj4.instabox.tech`
   - Chat endpoint: `POST /api/chat`
   - Embed endpoint: `POST /api/embed` (with fallback to `POST /api/embeddings`)
   - Initial generation model candidate: `qwen3.5:4b` (bounded 4096 context window).
   - Mandatory embedding model: `nomic-embed-text` (768 dimensions).
2. **Fallback Generation Provider: Google Gemini API (Free Tier Only)**
   - Model: `gemini-1.5-flash`
   - Used strictly for recoverable Ollama infrastructure failures (server down, timeout, 5xx server error).
   - Never used for embeddings (to prevent vector dimension/space divergence).
   - Bounded by strict privacy sanitization: all API keys, access tokens, database passwords, and credentials are automatically stripped prior to cloud fallback.
   - Non-recoverable failures (e.g. `AUTHENTICATION_ERROR` 401/403 or bad user input) **never** trigger fallback.
   - Cloud fallback can be disabled completely via `GEMINI_ALLOW_CLOUD_FALLBACK=false`.

## 2. Component Topology

```text
[User / Frontend UI]
       │
       ▼ (JWT Authenticated REST)
[FastAPI Backend / Render]
       │
       ├─► [ProviderManager] (Centralized Router & Sanitizer)
       │         │
       │         ├─► [OllamaProvider] (Primary, HTTPX Async Client)
       │         │         │
       │         │         └─► Localhost (:11434) OR Remote InstaBox Endpoint
       │         │             (with Bearer + ?_token private port auth)
       │         │
       │         └─► [GeminiProvider] (Fallback, Free Tier Only)
       │                   │
       │                   └─► Google Generative Language API
       │
       ├─► [ChunkingService] (Phase-4 Symbol-Aware AST Chunker)
       │
       ├─► [EmbeddingService] (Batch Vector Generator & Indexer)
       │
       ├─► [RAGService] (Query Vectorizer, Top-K Retrieval, Injection Defense)
       │
       └─► [ChatService & Repository]
                 │
                 └─► CodeChunk & Chat History in PostgreSQL / SQLite
```

## 3. Provider Error Classification

The provider layer maps HTTP and transport anomalies into domain error categories:

- `AUTHENTICATION_ERROR`: HTTP 401/403 (Invalid/missing InstaBox port token; `is_recoverable=False`, never triggers fallback).
- `CONNECTION_ERROR`: Network failure or sleeping InstaBox machine (`is_recoverable=True`).
- `TIMEOUT_ERROR`: Request connect or read timeout (`is_recoverable=True`).
- `MODEL_NOT_FOUND`: HTTP 404 from Ollama registry (`is_recoverable=False`).
- `INVALID_RESPONSE`: Malformed JSON or non-finite vector (`is_recoverable=False`).
- `RATE_LIMITED`: HTTP 429 quota exhaustion (`is_recoverable=True`).
- `SERVER_ERROR`: HTTP 5xx crash on Ollama host (`is_recoverable=True`).
- `UNKNOWN_PROVIDER_ERROR`: Unexpected runtime exception.

## 4. Health Check Status Hierarchy

Health check operation inspects `/api/tags` and reports one of 8 distinct states:
1. `connected`: Server reachable, authenticated, and both models present.
2. `authentication_failed`: Server returned 401/403.
3. `server_unavailable`: ConnectError / host unreachable.
4. `request_timed_out`: Connection timed out.
5. `generation_model_missing`: `qwen3.5:4b` not found in model tags.
6. `embedding_model_missing`: `nomic-embed-text` not found in model tags.
7. `invalid_response`: Non-200 or unparseable JSON.
8. `unknown_failure`: Unhandled exception.

## 5. Vector Storage & Isolation Architecture

- **Portability**: To maintain 100% operational compatibility across local environments (SQLite / PostgreSQL 18.4 without `pgvector`) and Render production databases, embeddings are serialized as JSON float arrays (`CodeChunk.embedding_json`).
- **Isolation by Tenant**: `ChunkRepository.find_similar_chunks` enforces strict filtering:
  ```sql
  SELECT * FROM code_chunks WHERE repository_id = :repository_id;
  ```
  It is structurally impossible for a query on Repository A to retrieve code chunks from Repository B.
- **Vector Math**: Cosine similarity is computed in memory:
  $$\text{similarity} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
  with an empty/zero vector safeguard and normalized dot products.

## 6. AST & Symbol-Aware Code Chunking

- **AST Boundaries**: `ChunkingService` inspects Phase 4 parsed `CodeSymbol` entities (classes, functions, methods) using exact `start_line` and `end_line` ranges.
- **Adaptive Windowing**:
  - Small to medium functions (≤ 80 lines) remain cohesive single chunks.
  - Large symbols (> 80 lines) are chunked in 60-line windows with a 10-line overlap.
  - Non-symbol files (JSON, YAML, configuration, markdown) use 50-line overlapping windows.
- **Safety Exclusions**: Files matching patterns for `.env*`, `*.pem`, `*.key`, `package-lock.json`, `dist/`, `build/`, `__pycache__/`, or containing high-entropy API keys are excluded from chunking and vector storage.

## 7. RAG Pipeline & Prompt Injection Defense

- **System Prompt**: Defines strict evidence grounding:
  - Answers must rely *only* on the provided context chunks.
  - If the context lacks the required information, the assistant must reply: *"I don't know based on the provided repository code."*
- **XML Context Delimitation**: Context chunks are wrapped in XML tags:
  ```xml
  <context_chunk id="1" file="app/services/auth.py" lines="45-88" symbol="authenticate_user">
  ... code contents ...
  </context_chunk>
  ```
- **Injection Defense**: Code chunks are sanitized, removing markdown code fence escape sequences. The system prompt instructs the LLM that any directives found *within* code blocks or comments must be treated strictly as code data, never as system instructions.

## 8. Chat APIs and Citation Contracts

Endpoints exposed under `/api/v1/repositories/{id}/`:
- `POST /conversations`: Start new conversation thread.
- `GET /conversations`: List user's conversations for the repository.
- `GET /conversations/{c_id}/messages`: Fetch chat history.
- `POST /conversations/{c_id}/messages`: Process user question, run RAG retrieval, generate answer, record message history with citations.
- `GET /chat/suggestions`: Return repository-specific sample questions.
- `POST /index-embeddings`: Index or re-index repository chunks.
