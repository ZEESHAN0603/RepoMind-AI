# RepoMind — AI-Powered Repository Intelligence Platform

> "Understand any codebase. Trace every connection. Explain every flow."

RepoMind is a developer-focused SaaS platform for exploring, visualizing, and understanding complex software repositories.

## Architecture & Development Phases

This codebase is structured cleanly by feature and service abstraction:

- **Phase 1 (In Progress)**: Complete frontend application powered by typed service interfaces and mock data implementations (`src/services/api/` + `src/services/mock/`).
- **Phase 2+ (Planned)**: Backend ingestion, static analysis, RAG with Ollama/Gemini fallback, incremental commit intelligence, and documentation generation.

## Tech Stack

- **Core**: React 19, TypeScript, Vite
- **Styling & UI**: Tailwind CSS v4, shadcn/ui, Lucide React
- **Routing**: React Router
- **State & Data**: Zustand, TanStack Query
- **Code & Visualization**: `@xyflow/react`, `@monaco-editor/react`, `react-markdown`, `mermaid`

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
