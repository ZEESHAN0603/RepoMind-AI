# Phase 7: Execution Flow Tracing

## 1. Overview & Objective

Phase 7 introduces **Execution Flow Tracing** to RepoMind, providing deep, call-level visibility into how source code executes. While Phase 6 mapped file- and module-level architectural relationships, Phase 7 analyzes function definitions, method invocations, and execution paths—tracing operations from frontend user interactions and backend API endpoints through services, repositories, and database operations.

The Execution Flow Tracing engine delivers:
- **Fine-Grained AST Call Extraction**: Identifies caller and callee symbols across Python and Tree-sitter supported languages (TypeScript, JavaScript, Java, Go, Rust, C#).
- **Multi-Tier Static Call Resolution**: Classifies calls across 4 distinct resolution tiers (`verified` local/method, `verified` cross-file import, `external` third-party library, and `unresolved` / dynamic dispatch).
- **Automated Entry-Point Detection**: Discovers verified application startup files, API route handlers, CLI commands, background jobs, and frontend UI event handlers.
- **Bounded Traversal Call Graphs**: Generates directed call graphs with caller/callee navigation, depth limits (`max_depth = 5`), node caps (`max_nodes = 50`), and cycle detection to safeguard memory on constrained deployments (Render).
- **Interactive Execution Flow Workspace**: React Flow (`@xyflow/react`) visualization with dual graph and step-by-step views, caller/callee collapse/expand, and jump-to-source in Project Explorer.
- **AI-Grounded Flow Explanations**: Context-grounded execution summaries powered by primary Ollama (`qwen3.5:4b`) on InstaBox with Gemini Free Tier fallback, providing step explanations and explicit uncertainty disclosures with zero paid API overhead.

---

## 2. Core Components Implemented

### 2.1 Static Call Extraction Engine (`app.analysis.python_parser` & `treesitter_parser`)
- Extends code parsing with `ParsedCall` metadata capturing:
  - Caller function/method symbol name and scope.
  - Callee identifier or attribute expression.
  - Target object expressions (e.g., `self.validate()`, `apiClient.post()`).
  - Argument counts and keyword argument names.
  - Start line, end line, and exact call expression text evidence.
- Full AST traversal handling chained calls, nested calls, higher-order functions, and module-level statements.

### 2.2 Multi-Tier Call Resolver (`app.analysis.call_resolver.CallResolver`)
Resolves raw call expressions against extracted codebase symbols using a deterministic 4-tier strategy:
1. **Local Scope & Class Hierarchy**: Resolves `self.method()`, `cls.method()`, and sibling functions defined within the same file or enclosing class.
2. **Cross-File Imports (`ModuleResolver`)**: Traces `from app.services.auth import AuthService` and matches instantiation/method calls to symbols in target files.
3. **External Dependencies**: Detects third-party package calls (e.g., `logging.info`, `requests.get`, `react.useState`) and flags them with `external` status without polluting local symbol graphs.
4. **Dynamic Dispatch & Heuristics**: Preserves unresolvable calls (callbacks, runtime reflection) as `unresolved` or `inferred`, never fabricating false execution edges.

### 2.3 Automated Entry-Point Detector (`app.analysis.entry_point_detector.EntryPointDetector`)
Discovers execution roots across frameworks:
- **Backend API Routes**: FastAPI (`@app.get`, `@router.post`), Flask (`@app.route`), Express routes (`router.get`, `app.post`).
- **Application Startup**: `main.py`, `app.py`, `server.ts`, `index.js`, and `if __name__ == '__main__':` blocks.
- **Command-Line Entry Points**: Click commands, Typer CLI functions, `argparse` scripts.
- **Background Jobs**: Celery tasks, scheduled cron handlers, worker loops.
- **Frontend UI Triggers**: React event handlers, `handleSubmit`, `onClick`, and API client calls (`apiClient.post`, `fetch`).

### 2.4 Database Models & Alembic Migration
- `code_calls` (`app.models.code_call.CodeCall`): Stores caller symbol ID, callee symbol ID, target name, call type, resolution status, line evidence, and confidence.
- `execution_entry_points` (`app.models.execution_entry_point.ExecutionEntryPoint`): Stores entry point name, type, handler symbol, file path, line number, HTTP method, and route path.
- `execution_snapshots` (`app.models.execution_snapshot.ExecutionSnapshot`): Stores precomputed execution workspaces and trace trees in SQLite/PostgreSQL for sub-50ms query latency.
- Migration `a1b2c3d4e5f6_add_phase7_execution_flow_schema.py` applied via `alembic upgrade head`.

### 2.5 Execution Graph Builder & REST API Service (`ExecutionFlowGraphBuilder` & `ExecutionFlowService`)
- Builds directed acyclic/cyclic call graphs centered around detected entry points.
- Computes step-by-step linear call order with caller, callee, file path, line number, and passed data descriptions.
- Computes non-overlapping 2D layout coordinates for responsive rendering.
- Bounded traversal with depth and node limit safety guards.

### 2.6 AI-Grounded Execution Explainer (`app.services.execution_explainer_service.ExecutionExplainerService`)
- Uses `ProviderManager` (Ollama `qwen3.5:4b` primary, Gemini Free Tier fallback).
- Grounded prompt providing strictly verified static call traces and source code snippets.
- Structured XML synthesis parsed into:
  - Overall flow summary.
  - Step-by-step verified execution explanations with source file and line citations.
  - Explicit disclosures of uncertainties (dynamic dispatch, middleware, environment state).

### 2.7 Frontend React Flow Workspace & AI Modal (`ExecutionPage.tsx`, `execution.api.ts`)
- Dual-mode visualization: Interactive call graph and sequential step-by-step view.
- "Explain Flow with AI" modal displaying grounded summaries, step cards, and uncertainty alerts.
- Node inspection panel displaying source code preview, parameters, return types, callers, and callees.
- Deep linking from any node directly into the Project Explorer file tree.

---

## 3. Backend REST Endpoints

All endpoints require repository authorization via JWT Bearer authentication:

| HTTP Method | Route | Description |
|---|---|---|
| `POST` | `/api/v1/repositories/{id}/execution/analyze` | Triggers static call extraction, resolution, and trace generation |
| `GET` | `/api/v1/repositories/{id}/execution/workspace` | Retrieves full execution workspace (traces, nodes, edges, function symbols) |
| `GET` | `/api/v1/repositories/{id}/execution/entry-points` | Lists detected application entry points with filtering |
| `GET` | `/api/v1/repositories/{id}/execution/nodes/{symbol_id}/calls` | Retrieves incoming callers and outgoing callees for a symbol |
| `GET` | `/api/v1/repositories/{id}/execution/trace-path` | Traces directed execution path between source and target symbols |
| `POST` | `/api/v1/repositories/{id}/execution/explain` | Generates AI-grounded flow explanation with step verification and uncertainty disclosure |

---

## 4. Verification & Testing

All Phase 7 tests and prior regression tests pass cleanly:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_call_extractor.py backend/tests/test_call_resolution_and_entry_points.py backend/tests/test_execution_api.py -v
```
**Results**:
- `test_call_extractor.py`: 7/7 passed (Python AST calls, chained calls, class methods, Tree-sitter TypeScript calls, arrow functions).
- `test_call_resolution_and_entry_points.py`: 3/3 passed (Local scope resolution, cross-file imports, entry-point detector).
- `test_execution_api.py`: 2/2 passed (Full upload -> analyze -> workspace -> entry-points -> callers/callees -> trace-path -> AI explain, plus multi-tenant security isolation).
- **Total: 12 passed in 11.08s**.

Prior phase regression tests (`test_phase3_indexing_analysis.py`, `test_phase4_parsers.py`, `test_architecture_api.py`):
- **15 passed in 16.95s** with zero regressions.

Frontend production build:
- `npm run build`: Built cleanly in 5.78s with zero TypeScript errors.
