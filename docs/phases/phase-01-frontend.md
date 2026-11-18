# Phase 1: Frontend Foundation & User Interface

## Status: Completed

### Scope & Invariants
- **Framework**: React 19 with TypeScript and Vite.
- **Styling**: Tailwind CSS v4, Lucide React icons, Radix UI primitives.
- **Visualizations**: `@xyflow/react` for interactive architecture and dependency graphs, Monaco Editor for source code browsing, React-Markdown with remark-gfm for documentation.
- **State Management**: Modular Zustand stores for auth, repository selection, file exploration, graph visualizations, chat sessions, updates, and documentation.
- **Routing**: React Router v7 with declarative nested layouts and route guards for authenticated sessions.
- **Security**: No secrets or AI provider keys stored in frontend; all tokens stored in secured storage with automatic refresh interceptors.

---

### Key Capabilities & Components

#### 1. Routing & Layout Architecture
- `src/App.tsx`: Central application routing with routes for Dashboard, Repository Detail, Code Intelligence, Architecture Viewer, Flow Tracing, Dependencies, Update Intelligence, Documentation, and Settings.
- Route protection checking authentication state and redirecting unauthenticated users to `/login`.

#### 2. Authentication & User Management
- Modern authentication views: Login, Registration, and Password Reset.
- Form validation, error toast notifications via `sonner`, and session persistence via `authStore`.

#### 3. Repository Dashboard & Ingestion UI
- Repository list with status indicators (`pending`, `processing`, `completed`, `failed`).
- Modal for ZIP file drag-and-drop upload and GitHub repository URL input with branch selection.
- Ingestion progress tracking with real-time status polling.

#### 4. Interactive Code Explorer
- Multi-pane IDE-style layout with collapsible file tree, breadcrumb navigation, and tabbed file viewing.
- Code viewer with syntax highlighting and symbol navigation.

#### 5. Interactive Intelligence Views
- **Architecture Graph**: Interactive node-edge visualization using `@xyflow/react` showing system layers, modules, and relationships.
- **Execution Flow**: Visual call-chain explorer tracking entry points to terminal database/network calls.
- **Dependency Graph**: Visualization of direct, transitive, circular, and external package dependencies.
- **Update Intelligence**: Diff viewer and change-impact analyzer comparing repository snapshots.
- **Documentation Studio**: Markdown viewer and editor supporting README, API, and Architecture docs with export triggers.

#### 6. AI Assistant / Chat Drawer
- Context-aware drawer allowing natural-language queries against repository code.
- Source citation cards with jump-to-code navigation.
