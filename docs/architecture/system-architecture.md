# RepoMind — System Architecture

## 1. High-Level Topology

RepoMind is a cloud-native repository intelligence platform that combines AST static code analysis, semantic RAG retrieval, and interactive graph exploration.

```mermaid
flowchart LR
    subgraph Client ["Client (Vercel)"]
        UI["React 19 + Vite 8\n(@xyflow/react + Tailwind v4)"]
    end

    subgraph BackendGateway ["API Backend (Render)"]
        FastAPIApp["FastAPI 0.115\n(AsyncIO Gateway)"]
        IngestionService["Ingestion & Security\n(Zip slip protection, Git indexer)"]
        ParserRegistry["AST & Tree-Sitter Parsers\n(Python, TS, JS, Go, Rust)"]
        ArchEngine["Architecture Intelligence\n(Module resolver, Layer classifier, Layout)"]
        RAGService["RAG & Embeddings\n(Chunking, Cosine Similarity)"]
    end

    subgraph PrimaryAI ["Primary Inference (InstaBox)"]
        OllamaServer["Ollama Server\n(qwen3.5:4b + nomic-embed-text)"]
    end

    subgraph FallbackAI ["Fallback Inference (Google Cloud)"]
        GeminiAPI["Gemini API Free Tier\n(gemini-2.5-flash / gemini-1.5-flash)"]
    end

    subgraph Storage ["Persistent Data Layer"]
        PostgresDB["Supabase PostgreSQL\n(SQLAlchemy 2.0 Async)"]
        LocalWS["Workspace Disk\n(storage/workspaces/)"]
    end

    UI <-->|REST & JSON API| FastAPIApp
    FastAPIApp --> IngestionService
    FastAPIApp --> ParserRegistry
    FastAPIApp --> ArchEngine
    FastAPIApp --> RAGService
    RAGService -->|Primary| OllamaServer
    RAGService -.->|Fallback| GeminiAPI
    FastAPIApp <--> PostgresDB
    IngestionService <--> LocalWS
    ParserRegistry <--> LocalWS
```

## 2. Layer Responsibilities

1. **Frontend Presentation Layer (`src/`)**:
   - Single-page React 19 application bundled with Vite.
   - Interactive graphs powered by `@xyflow/react` v12.
   - TanStack React Query for data fetching and optimistic UI caching.
   - Zustand stores for user session, active repositories, and theme preferences.

2. **Backend Application Layer (`backend/app/`)**:
   - FastAPI application structured with layered domain services.
   - Dependency injection for database sessions and authentication (`get_current_user`, `get_db`).
   - Standardized exception handlers and correlation ID middleware.

3. **Intelligence & Analysis Layer**:
   - Python AST standard library parser for Python.
   - Tree-sitter multi-language parser for JavaScript, TypeScript, Java, Go, Rust, C/C++, C#, and PHP.
   - Module resolution engine for cross-file path resolution.
   - Architecture classifier and DAG layout engine.

4. **Persistence Layer**:
   - Async SQLAlchemy with PostgreSQL (production on Render) and SQLite (local dev/test).
   - Dedicated tables for files, symbols, imports, endpoints, chunks, chat messages, and architecture snapshots.
