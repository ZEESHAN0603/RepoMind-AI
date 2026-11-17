# RepoMind — AI-Powered Repository Intelligence Platform

> "Understand any codebase. Trace every connection. Explain every flow."

RepoMind is a developer-focused SaaS platform for exploring, visualizing, and understanding complex software repositories.

## Architecture & Development Phases

This codebase is structured cleanly by feature and service abstraction across backend and frontend:

- **Phase 1 (Completed)**: Complete frontend application powered by React 19, Tailwind v4, `@xyflow/react`, and typed services.
- **Phase 2 (Completed)**: Backend foundation with FastAPI, Supabase-managed PostgreSQL, JWT authentication, and Argon2 password hashing.
- **Phase 3 (Completed)**: Repository ingestion engine (ZIP upload, GitHub sync, manifest parsing, language percentage calculation).
- **Phase 4 (Completed)**: Multi-language code intelligence (AST & Tree-sitter parsers, symbols, imports, API endpoints).
- **Phase 5 (Completed)**: AI & Grounded RAG integration (InstaBox Ollama `qwen3.5:4b` / `nomic-embed-text` with Gemini free-tier fallback).
- **Phase 6 (Completed)**: Architecture Intelligence (Multi-language module resolver, layer classifier, 6-view graph builder, `@xyflow/react` integration).
- **Phase 7 (Completed)**: Execution Flow Tracing (AST call extraction, multi-tier call resolution, entry-point detection, interactive call graphs, AI flow explanation).
- **Phase 8–10 (Upcoming)**: Dedicated dependency analysis, update intelligence, and automatic documentation generation.

## Tech Stack

- **Core**: React 19, TypeScript, Vite
- **Styling & UI**: Tailwind CSS v4, shadcn/ui, Lucide React
- **Routing**: React Router
- **State & Data**: Zustand, TanStack Query
- **Code & Visualization**: `@xyflow/react`, `@monaco-editor/react`, `react-markdown`, `mermaid`, `cytoscape`
- **Backend & Intelligence**: FastAPI, SQLAlchemy 2.0 Async, Supabase PostgreSQL, Tree-sitter, AST Diffing, Ollama (InstaBox/Local), Gemini free tier fallback

## Features
- **Phase 1–4**: Ingestion, AST Parsing, Symbol Extraction, File Tree.
- **Phase 5**: Vector Embeddings (nomic-embed-text), RAG Search, Chat Assistant.
- **Phase 6**: Multi-View Interactive Architecture Intelligence.
- **Phase 7**: Execution Flow Tracing & Static Call Resolution.
- **Phase 8**: Multi-Module Dependency Analysis & Circular Cycle Detection.
- **Phase 9**: Repository Update Intelligence (AST Diffing, Line-Shift Invariance, Blast Radius Analysis, Grounded AI Summaries).

## Local Development (Windows PowerShell)

```powershell
# Install dependencies
npm install

# Start the development server on port 3000
npm run dev

# Run TypeScript type checking
npm run lint

# Build for production
npm run build
```
