from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider_manager import REDACTION_RULES, ProviderManager
from app.ai.schemas import ChatMessage
from app.core.exceptions import NotFoundException
from app.core.logging import logger
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.architecture_snapshot import ArchitectureSnapshot
from app.models.code_call import CodeCall
from app.models.code_dependency import CodeDependency
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.dependency_snapshot import DependencySnapshot
from app.models.execution_entry_point import ExecutionEntryPoint
from app.models.execution_snapshot import ExecutionSnapshot
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.models.repository_language import RepositoryLanguage
from app.models.repository_manifest import RepositoryDependencyManifest
from app.models.repository_update_run import RepositoryUpdateRun
from app.models.version_file_change import VersionFileChange
from app.models.version_symbol_change import VersionSymbolChange
from app.repositories.documentation_repository import DocumentationRepository
from app.repositories.file_repository import FileRepository
from app.repositories.repository_repository import RepositoryRepository
from app.services.workspace_service import WorkspaceService


class DocumentationGenerationService:
    """
    Synthesizes accurate, evidence-grounded technical documentation for repositories
    by reusing completed intelligence from Phases 3–9.
    """

    def __init__(
        self,
        workspace_service: Optional[WorkspaceService] = None,
        provider_manager: Optional[ProviderManager] = None,
    ) -> None:
        self.workspace_service = workspace_service or WorkspaceService()
        self.provider_manager = provider_manager or ProviderManager()

    def _sanitize_secrets(self, text: str) -> str:
        """Applies REDACTION_RULES to sanitize secrets and tokens before AI dispatch."""
        sanitized = text
        for pattern, replacement in REDACTION_RULES:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def _safe_mermaid_id(self, name: str) -> str:
        """Normalizes node names into safe alphanumeric identifiers for Mermaid diagrams."""
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', name)
        if not clean or clean[0].isdigit():
            clean = f"node_{clean}"
        return clean

    # =========================================================================
    # 1. README Generator
    # =========================================================================
    async def generate_readme(
        self,
        session: AsyncSession,
        repository: Repository,
        files: List[RepositoryFile],
        languages: List[RepositoryLanguage],
        manifests: List[RepositoryDependencyManifest],
        endpoints: List[ApiRouteEndpoint],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates a comprehensive README grounded strictly in repository evidence."""
        evidence: Dict[str, Any] = {
            "files_analyzed": len(files),
            "languages": [l.language for l in languages],
            "manifests": [m.manifest_type for m in manifests],
            "endpoints_count": len(endpoints),
        }

        # Determine tech stack & package managers
        detected_tech = []
        install_commands = []
        run_commands = []
        for l in languages[:5]:
            detected_tech.append(f"{l.language} ({l.percentage}%)")

        workspace_path = self.workspace_service.get_repository_workspace_path(
            repository.owner_id, repository.id
        )

        env_vars_found = []
        # Check for .env.example / .env.sample
        env_files = [f for f in files if f.path.lower() in (".env.example", ".env.sample", ".env.template")]
        if env_files and workspace_path.exists():
            env_disk_path = workspace_path / env_files[0].path
            if env_disk_path.is_file():
                try:
                    with open(env_disk_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                var_name = line.split("=", 1)[0].strip()
                                if var_name:
                                    env_vars_found.append(var_name)
                except Exception as e:
                    logger.warning("Could not parse env file: %s", e)

        # Inspect package.json / requirements.txt for install & run commands
        pkg_json_file = next((f for f in files if f.path.lower() == "package.json"), None)
        scripts_summary = []
        if pkg_json_file and workspace_path.exists():
            pkg_path = workspace_path / pkg_json_file.path
            if pkg_path.is_file():
                try:
                    with open(pkg_path, "r", encoding="utf-8", errors="ignore") as f:
                        pkg_data = json.load(f)
                        scripts = pkg_data.get("scripts", {})
                        for s_name, s_cmd in scripts.items():
                            scripts_summary.append(f"- `npm run {s_name}`: `{s_cmd}`")
                    install_commands.append("npm install")
                    if "dev" in scripts:
                        run_commands.append("npm run dev")
                    elif "start" in scripts:
                        run_commands.append("npm start")
                except Exception as e:
                    logger.warning("Could not read package.json: %s", e)

        req_txt_file = next((f for f in files if f.path.lower() == "requirements.txt"), None)
        if req_txt_file:
            install_commands.append("pip install -r requirements.txt")

        pyproject_file = next((f for f in files if f.path.lower() == "pyproject.toml"), None)
        if pyproject_file:
            install_commands.append("poetry install  # or pip install .")

        cargo_file = next((f for f in files if f.path.lower() == "cargo.toml"), None)
        if cargo_file:
            install_commands.append("cargo build")
            run_commands.append("cargo run")

        # Top-level directory structure
        top_level_dirs = sorted(list({f.path.split("/")[0] for f in files if "/" in f.path}))

        # Assemble markdown
        lines = [
            f"# {repository.name}",
            "",
            "> Technical repository overview and documentation generated automatically by **RepoMind**.",
            "",
            "## Overview & Purpose",
            "",
            f"**{repository.name}** is a software repository containing {len(files)} discovered files across {len(languages)} programming languages.",
            f"Repository visibility: `{repository.visibility}` | Default branch: `{repository.default_branch}`.",
            "",
            "## Technology Stack",
            "",
            "### Languages",
            "",
        ]
        for lang in languages[:8]:
            lines.append(f"- **{lang.language}**: {lang.percentage}% ({lang.file_count} files, {lang.byte_count:,} bytes)")

        lines.extend([
            "",
            "### Project Structure",
            "",
            "Key top-level directories discovered in the repository:",
            "",
        ])
        for d in top_level_dirs[:12]:
            lines.append(f"- `/{d}`")

        lines.extend([
            "",
            "## Getting Started",
            "",
            "### Prerequisites & Installation",
            "",
        ])
        if install_commands:
            lines.append("```bash")
            for cmd in install_commands:
                lines.append(cmd)
            lines.append("```")
        else:
            lines.append("_[Unknown: No standard dependency manifest identified]_")

        lines.extend([
            "",
            "### Environment Configuration",
            "",
        ])
        if env_vars_found:
            lines.append("The following environment variables were detected from template files:")
            lines.append("")
            for ev in env_vars_found[:25]:
                lines.append(f"- `{ev}`")
        else:
            lines.append("No `.env.example` or environment template was detected in the repository.")

        lines.extend([
            "",
            "### Running the Application",
            "",
        ])
        if run_commands:
            lines.append("```bash")
            for cmd in run_commands:
                lines.append(cmd)
            lines.append("```")
        elif scripts_summary:
            lines.append("Available package execution scripts:")
            lines.append("")
            lines.extend(scripts_summary[:10])
        else:
            lines.append("_[Execution instructions unknown: verify entry point files directly]_")

        if endpoints:
            lines.extend([
                "",
                "## API Overview",
                "",
                f"Discovered **{len(endpoints)}** HTTP route endpoints across the codebase.",
                "",
                "| Method | Route Path | Framework | Source Location |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for ep in endpoints[:15]:
                lines.append(f"| `{ep.http_method}` | `{ep.path}` | {ep.framework} | `{ep.file_id}#L{ep.start_line}` |")

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 2. Code-Level Documentation Generator
    # =========================================================================
    async def generate_code_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        symbols: List[CodeSymbol],
        files: List[RepositoryFile],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates structured code reference for functions, classes, and interfaces."""
        file_map = {f.id: f.path for f in files}
        evidence: Dict[str, Any] = {
            "total_symbols": len(symbols),
            "functions": len([s for s in symbols if s.symbol_type == "function"]),
            "classes": len([s for s in symbols if s.symbol_type == "class"]),
        }

        lines = [
            f"# {repository.name} — Code-Level Technical Reference",
            "",
            "> Detailed specification of extracted functions, classes, interfaces, and public interfaces.",
            "",
            f"Total indexed symbols: **{len(symbols)}**",
            "",
        ]

        # Group symbols by file
        symbols_by_file: Dict[str, List[CodeSymbol]] = defaultdict(list)
        for s in symbols:
            symbols_by_file[file_map.get(s.file_id, "unknown")].append(s)

        for file_path, file_symbols in sorted(symbols_by_file.items())[:20]:
            lines.extend([
                f"## File: `{file_path}`",
                "",
            ])
            for s in sorted(file_symbols, key=lambda x: x.start_line)[:15]:
                scope_str = f" in `{s.scope}`" if s.scope else ""
                lines.extend([
                    f"### `{s.name}` ({s.symbol_type}){scope_str}",
                    "",
                    f"- **Location**: `{file_path}#L{s.start_line}-L{s.end_line}`",
                    f"- **Visibility**: `{s.visibility}` | **Confidence**: `{s.confidence}`",
                ])

                if s.signature:
                    lines.append(f"- **Signature**: `{s.signature}`")

                if s.return_type:
                    lines.append(f"- **Return Type**: `{s.return_type}`")

                if s.docstring:
                    lines.extend([
                        "",
                        "> " + "\n> ".join(s.docstring.strip().splitlines()),
                        "",
                    ])

                try:
                    params = json.loads(s.parameters)
                    if params:
                        lines.append("")
                        lines.append("**Parameters:**")
                        for p in params:
                            p_type = f": `{p.get('type_annotation')}`" if p.get('type_annotation') else ""
                            p_def = f" (default: `{p.get('default_value')}`)" if p.get('default_value') else ""
                            lines.append(f"- `{p.get('name')}`{p_type}{p_def}")
                except Exception:
                    pass

                lines.append("")

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 3. API Documentation Generator
    # =========================================================================
    async def generate_api_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        endpoints: List[ApiRouteEndpoint],
        files: List[RepositoryFile],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates comprehensive HTTP API documentation from detected route handlers."""
        file_map = {f.id: f.path for f in files}
        evidence: Dict[str, Any] = {
            "total_endpoints": len(endpoints),
            "frameworks": list({ep.framework for ep in endpoints}),
        }

        lines = [
            f"# {repository.name} — API Reference Documentation",
            "",
            "> Verified REST API route declarations extracted from backend source code via static analysis.",
            "",
            f"Total discovered endpoints: **{len(endpoints)}**",
            "",
        ]

        if not endpoints:
            lines.extend([
                "No HTTP API route endpoints were detected in this repository.",
                "",
                "Supported frameworks for automated API discovery include:",
                "- FastAPI (`@router.get`, `@app.post`, etc.)",
                "- Express (`app.get()`, `router.post()`, etc.)",
                "- Flask (`@app.route()`)",
                "- NestJS (`@Get()`, `@Post()`)",
            ])
            return "\n".join(lines) + "\n", evidence

        # Group by framework or path prefix
        lines.extend([
            "## Discovered Endpoints Summary",
            "",
            "| HTTP Method | Route Path | Handler Function | Framework | Source File |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ])
        for ep in endpoints:
            fpath = file_map.get(ep.file_id, "unknown")
            lines.append(f"| **{ep.http_method}** | `{ep.path}` | `{ep.handler_name}` | {ep.framework} | `{fpath}#L{ep.start_line}` |")

        lines.extend(["", "## Endpoint Details", ""])
        for ep in endpoints:
            fpath = file_map.get(ep.file_id, "unknown")
            lines.extend([
                f"### `{ep.http_method}` {ep.path}",
                "",
                f"- **Handler Function**: `{ep.handler_name}`",
                f"- **Framework**: {ep.framework}",
                f"- **Source Reference**: `{fpath}#L{ep.start_line}-L{ep.end_line}`",
                f"- **Confidence**: `{ep.confidence}`",
                "",
            ])
            try:
                meta = json.loads(ep.metadata_json)
                if meta:
                    lines.append("**Extracted Route Metadata:**")
                    lines.append("```json")
                    lines.append(json.dumps(meta, indent=2))
                    lines.append("```")
                    lines.append("")
            except Exception:
                pass

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 4. Architecture Documentation Generator
    # =========================================================================
    async def generate_architecture_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        arch_snapshot: Optional[ArchitectureSnapshot],
        files: List[RepositoryFile],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates architectural system documentation with embedded Mermaid diagrams."""
        evidence: Dict[str, Any] = {
            "has_snapshot": arch_snapshot is not None,
            "node_count": arch_snapshot.node_count if arch_snapshot else 0,
            "edge_count": arch_snapshot.edge_count if arch_snapshot else 0,
        }

        lines = [
            f"# {repository.name} — Architecture Documentation",
            "",
            "> Layered system topology, component boundaries, and module relationships.",
            "",
        ]

        if not arch_snapshot or not arch_snapshot.graph_data_json:
            lines.extend([
                "No precomputed architecture snapshot found. Static analysis generates architecture views",
                "across System, Frontend, Backend, API, Database, and Module layers.",
            ])
            return "\n".join(lines) + "\n", evidence

        graph_data: Dict[str, Any] = {}
        try:
            graph_data = json.loads(arch_snapshot.graph_data_json)
        except Exception:
            pass

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        # Generate Mermaid diagram from nodes and edges (capped to 25 nodes to ensure readability)
        mermaid_lines = ["```mermaid", "flowchart TD"]
        rendered_nodes: Set[str] = set()

        for n in nodes[:20]:
            nid = self._safe_mermaid_id(n.get("id", "node"))
            nlabel = n.get("label", nid).replace('"', "'")
            ntype = n.get("type", "component")
            mermaid_lines.append(f'  {nid}["{nlabel} ({ntype})"]')
            rendered_nodes.add(nid)

        edge_count = 0
        for e in edges:
            src = self._safe_mermaid_id(e.get("source", ""))
            tgt = self._safe_mermaid_id(e.get("target", ""))
            if src in rendered_nodes and tgt in rendered_nodes:
                elabel = e.get("label", "").replace('"', "'")
                if elabel:
                    mermaid_lines.append(f'  {src} -->|"{elabel}"| {tgt}')
                else:
                    mermaid_lines.append(f"  {src} --> {tgt}")
                edge_count += 1
                if edge_count >= 25:
                    break

        mermaid_lines.append("```")

        lines.extend([
            "## System Component Topology",
            "",
            "\n".join(mermaid_lines),
            "",
            "## Architecture Layers & Responsibilities",
            "",
            f"The analyzed architecture contains **{len(nodes)}** key structural nodes and **{len(edges)}** dependency connections.",
            "",
            "### Component Breakdown",
            "",
            "| Component Name | Type | Technology / Layer | Responsibility |",
            "| :--- | :--- | :--- | :--- |",
        ])

        for n in nodes[:25]:
            nlabel = n.get("label", n.get("id"))
            ntype = n.get("type", "Module")
            tech = n.get("technology", "Source Code")
            desc = n.get("description", "System module")
            lines.append(f"| **{nlabel}** | {ntype} | {tech} | {desc} |")

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 5. Execution Flow Documentation Generator
    # =========================================================================
    async def generate_execution_flow_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        entry_points: List[ExecutionEntryPoint],
        calls: List[CodeCall],
        files: List[RepositoryFile],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates execution-flow documentation highlighting entry points and call chains."""
        file_map = {f.id: f.path for f in files}
        evidence: Dict[str, Any] = {
            "entry_points_count": len(entry_points),
            "calls_count": len(calls),
        }

        lines = [
            f"# {repository.name} — Execution Flow Tracing",
            "",
            "> Detailed explanation of discovered system entry points and static function invocation chains.",
            "",
            "### Static Analysis Limitations Disclosure",
            "> **Notice:** The execution flows documented below are extracted via **static source code analysis**.",
            "> Static analysis cannot observe runtime dynamic dispatch, external network payloads, reflection,",
            "> or framework callbacks. Verified steps indicate verified static linkages, while external boundaries",
            "> represent points where execution delegates outside the analyzed repository.",
            "",
            "## Discovered Entry Points",
            "",
            f"Total entry points: **{len(entry_points)}**",
            "",
            "| Type | Name | Route / Command | File Location | Verified |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]

        for ep in entry_points:
            verified_badge = "Yes" if ep.is_verified else "Inferred"
            route_str = f"`{ep.http_method or ''} {ep.route_path or ''}`".strip() or "—"
            lines.append(f"| `{ep.entry_point_type}` | **{ep.name}** | {route_str} | `{ep.file_path}#L{ep.line_number}` | {verified_badge} |")

        lines.extend(["", "## Static Call Chains & Invocations", ""])
        if calls:
            lines.extend([
                "| Caller Symbol | Callee Symbol | Call Type | Status | Location |",
                "| :--- | :--- | :--- | :--- | :--- |",
            ])
            for c in calls[:30]:
                fpath = file_map.get(c.file_id, "unknown")
                lines.append(f"| `{c.caller_symbol_name or 'module'}` | `{c.callee_name}` | `{c.call_type}` | `{c.resolution_status}` | `{fpath}#L{c.line_number}` |")
        else:
            lines.append("No static call chains currently extracted.")

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 6. Dependency & Cycle Documentation Generator
    # =========================================================================
    async def generate_dependency_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        dependencies: List[CodeDependency],
        manifests: List[RepositoryDependencyManifest],
        dep_snapshot: Optional[DependencySnapshot],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates internal and external dependency reports, including circular dependency alerts."""
        evidence: Dict[str, Any] = {
            "dependencies_count": len(dependencies),
            "manifests_count": len(manifests),
            "has_cycles": dep_snapshot.circular_count > 0 if dep_snapshot else False,
        }

        lines = [
            f"# {repository.name} — Dependency Analysis & Intelligence",
            "",
            "> Module import dependencies, third-party packages, and circular dependency evaluation.",
            "",
        ]

        if dep_snapshot:
            lines.extend([
                "## Dependency Metrics Summary",
                "",
                f"- **Total Modules Analyzed**: {dep_snapshot.total_modules}",
                f"- **Total Import Statements**: {dep_snapshot.total_imports}",
                f"- **Internal Dependencies**: {dep_snapshot.internal_count}",
                f"- **External Package Dependencies**: {dep_snapshot.external_count}",
                f"- **Circular Dependency Cycles**: {dep_snapshot.circular_count}",
                f"- **Unresolved Dependencies**: {dep_snapshot.unresolved_count}",
                "",
            ])

        # Circular Dependencies
        circular_deps = [d for d in dependencies if d.is_circular]
        lines.append("## Circular Dependency Analysis")
        lines.append("")
        if circular_deps:
            lines.extend([
                "> ⚠️ **Circular Dependencies Detected**: The following module imports form closed dependency cycles.",
                "",
                "| Source Module | Target Module | Statement | Location |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for cd in circular_deps[:15]:
                lines.append(f"| `{cd.source_path}` | `{cd.target_path or cd.target_module}` | `{cd.statement_type}` | Line {cd.line_number} |")
            lines.append("")
        else:
            lines.extend([
                "✅ **No circular dependency cycles detected.** The codebase maintains a clean directed acyclic dependency structure.",
                "",
            ])

        # External Manifest Packages
        lines.extend([
            "## Third-Party Package Manifests",
            "",
        ])
        if manifests:
            for m in manifests:
                lines.extend([
                    f"### Manifest: `{m.file_path}` ({m.manifest_type})",
                    "",
                ])
                try:
                    deps = json.loads(m.dependencies_json)
                    if isinstance(deps, dict):
                        lines.extend([
                            "| Package Name | Declared Version Constraint |",
                            "| :--- | :--- |",
                        ])
                        for pkg, ver in list(deps.items())[:25]:
                            lines.append(f"| `{pkg}` | `{ver}` |")
                    elif isinstance(deps, list):
                        lines.extend([
                            "| Package Name |",
                            "| :--- |",
                        ])
                        for pkg in deps[:25]:
                            lines.append(f"| `{pkg}` |")
                    lines.append("")
                except Exception:
                    lines.append("No packages parsed.")
        else:
            lines.append("No package dependency manifests found.")

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # 7. Update & Changelog Documentation Generator
    # =========================================================================
    async def generate_changelog_docs(
        self,
        session: AsyncSession,
        repository: Repository,
        update_runs: List[RepositoryUpdateRun],
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates update history, version diffs, and change release notes."""
        evidence: Dict[str, Any] = {
            "total_runs": len(update_runs),
        }

        lines = [
            f"# {repository.name} — Repository Update Changelog",
            "",
            "> Historical change intelligence, version comparisons, and AST symbol mutations.",
            "",
        ]

        if not update_runs:
            lines.extend([
                "No repository update runs have been recorded yet.",
                "When repository commits or version ZIPs are ingested, incremental diffs and impact assessments appear here.",
            ])
            return "\n".join(lines) + "\n", evidence

        for run in update_runs[:10]:
            base_sha = run.base_commit_sha[:7] if run.base_commit_sha else "initial"
            target_sha = run.target_commit_sha[:7] if run.target_commit_sha else run.id[:7]
            lines.extend([
                f"## Update Run: `{base_sha}` → `{target_sha}`",
                "",
                f"- **Run ID**: `{run.id}`",
                f"- **Status**: `{run.status}`",
                f"- **Files Changed**: {run.total_files_changed} (+{run.total_additions} / -{run.total_deletions})",
                f"- **Symbols Mutated**: {run.total_symbols_changed}",
                f"- **Date**: {run.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if run.created_at else 'N/A'}",
                "",
            ])

            if run.ai_summary_markdown:
                lines.extend([
                    "### Grounded AI Change Summary",
                    "",
                    run.ai_summary_markdown.strip(),
                    "",
                ])

        content = "\n".join(lines) + "\n"
        return content, evidence

    # =========================================================================
    # Orchestrator
    # =========================================================================
    async def generate_all_documents(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
        doc_types: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Orchestrates full repository documentation generation across all selected sections,
        persisting results into Supabase repository_documents.
        """
        repo_repo = RepositoryRepository(session)
        file_repo = FileRepository(session)
        doc_repo = DocumentationRepository(session)

        repo = await repo_repo.get_by_id(repository_id)
        if not repo:
            raise NotFoundException("Repository not found")

        # Fetch required intelligence models
        files = await file_repo.list_files_by_repo(repository_id)
        languages = list((await session.execute(
            select(RepositoryLanguage).where(RepositoryLanguage.repository_id == repository_id)
        )).scalars().all())
        manifests = list((await session.execute(
            select(RepositoryDependencyManifest).where(RepositoryDependencyManifest.repository_id == repository_id)
        )).scalars().all())
        symbols = list((await session.execute(
            select(CodeSymbol).where(CodeSymbol.repository_id == repository_id)
        )).scalars().all())
        endpoints = list((await session.execute(
            select(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repository_id)
        )).scalars().all())
        arch_snapshot = (await session.execute(
            select(ArchitectureSnapshot).where(ArchitectureSnapshot.repository_id == repository_id)
        )).scalar_one_or_none()
        entry_points = list((await session.execute(
            select(ExecutionEntryPoint).where(ExecutionEntryPoint.repository_id == repository_id)
        )).scalars().all())
        calls = list((await session.execute(
            select(CodeCall).where(CodeCall.repository_id == repository_id)
        )).scalars().all())
        dependencies = list((await session.execute(
            select(CodeDependency).where(CodeDependency.repository_id == repository_id)
        )).scalars().all())
        dep_snapshot = (await session.execute(
            select(DependencySnapshot).where(DependencySnapshot.repository_id == repository_id)
        )).scalar_one_or_none()
        update_runs = list((await session.execute(
            select(RepositoryUpdateRun)
            .where(RepositoryUpdateRun.repository_id == repository_id)
            .order_by(RepositoryUpdateRun.created_at.desc())
        )).scalars().all())

        all_types = doc_types or [
            "readme",
            "architecture",
            "api",
            "execution_flow",
            "dependencies",
            "update_changelog",
            "code_reference",
        ]

        generated_docs = []

        for dtype in all_types:
            content = ""
            title = ""
            desc = ""
            evidence: Dict[str, Any] = {}

            if dtype == "readme":
                title = "README Overview"
                desc = "Project purpose, quickstart instructions, environment configuration, and technology stack."
                content, evidence = await self.generate_readme(session, repo, files, languages, manifests, endpoints)

            elif dtype == "architecture":
                title = "System Architecture"
                desc = "Layered system boundaries, interactive component topology diagrams, and module responsibilities."
                content, evidence = await self.generate_architecture_docs(session, repo, arch_snapshot, files)

            elif dtype == "api":
                title = "API Reference"
                desc = "Verified REST API routes, handler functions, frameworks, and endpoint specifications."
                content, evidence = await self.generate_api_docs(session, repo, endpoints, files)

            elif dtype == "execution_flow":
                title = "Execution Flow Tracing"
                desc = "Entry-point discovery, function invocation chains, and static analysis boundaries."
                content, evidence = await self.generate_execution_flow_docs(session, repo, entry_points, calls, files)

            elif dtype == "dependencies":
                title = "Dependency & Cycle Intelligence"
                desc = "Internal module dependencies, third-party package manifests, and circular dependency evaluation."
                content, evidence = await self.generate_dependency_docs(session, repo, dependencies, manifests, dep_snapshot)

            elif dtype == "update_changelog":
                title = "Repository Update Changelog"
                desc = "Historical update runs, version-to-version comparisons, and AST symbol mutations."
                content, evidence = await self.generate_changelog_docs(session, repo, update_runs)

            elif dtype in ("code_reference", "module"):
                title = "Code-Level Reference"
                desc = "Functions, classes, parameters, return types, exceptions, and line-level source citations."
                content, evidence = await self.generate_code_docs(session, repo, symbols, files)

            if content:
                doc_record = await doc_repo.save_or_update_document(
                    repository_id=repository_id,
                    doc_type=dtype,
                    title=title,
                    description=desc,
                    content=content,
                    status="draft",
                    confidence="verified",
                    source_evidence=evidence,
                    change_summary="Automatic documentation generation",
                    user_id=user_id,
                )
                generated_docs.append({
                    "id": doc_record.id,
                    "repository_id": repository_id,
                    "doc_type": doc_record.doc_type,
                    "title": doc_record.title,
                    "description": doc_record.description,
                    "status": doc_record.status,
                    "confidence": doc_record.confidence,
                    "version_number": doc_record.version_number,
                    "content_length": len(doc_record.content),
                    "last_generated_at": doc_record.last_generated_at,
                    "approved_at": doc_record.approved_at,
                    "approved_by": doc_record.approved_by,
                })

        await session.commit()
        return generated_docs
