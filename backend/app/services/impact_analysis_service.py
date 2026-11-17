from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_call import CodeCall
from app.models.code_dependency import CodeDependency
from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile
from app.services.architecture_service import ArchitectureService
from app.services.dependency_service import DependencyService
from app.services.execution_flow_service import ExecutionFlowService


class ImpactAnalysisService:
    """
    Computes evidence-based blast-radius impact analysis by traversing
    Phase 6 (Architecture), Phase 7 (Call Graph), and Phase 8 (Dependency Graph) results.
    """

    def __init__(
        self,
        dependency_service: Optional[DependencyService] = None,
        execution_service: Optional[ExecutionFlowService] = None,
        architecture_service: Optional[ArchitectureService] = None,
    ) -> None:
        self.dependency_service = dependency_service or DependencyService()
        self.execution_service = execution_service or ExecutionFlowService()
        self.architecture_service = architecture_service or ArchitectureService()

    async def compute_impact(
        self,
        session: AsyncSession,
        repository_id: str,
        changed_files: List[Dict[str, Any]],
        changed_symbols: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Calculates multi-level impact classification:
        - directly_changed
        - directly_affected
        - indirectly_affected
        - potentially_affected
        - unknown
        """
        impact_records: List[Dict[str, Any]] = []
        visited_identifiers: Set[str] = set()

        changed_file_paths = {f["path"].replace("\\", "/").lstrip("/") for f in changed_files}
        modified_or_deleted_paths = {
            f["path"].replace("\\", "/").lstrip("/")
            for f in changed_files
            if f.get("change_type") in ("modified", "deleted", "renamed")
        }

        # 1. Directly Changed Records
        for f in changed_files:
            ident = f"file:{f['path']}"
            visited_identifiers.add(ident)
            impact_records.append({
                "affected_type": "file",
                "affected_identifier": ident,
                "affected_path": f["path"],
                "impact_level": "directly_changed",
                "evidence_reason": f"File was {f.get('change_type', 'modified')}",
                "depth": 0,
            })

        for s in changed_symbols:
            ident = f"symbol:{s.get('scope') or ''}:{s.get('symbol_name')}"
            visited_identifiers.add(ident)
            impact_records.append({
                "affected_type": s.get("symbol_type", "symbol"),
                "affected_identifier": ident,
                "affected_path": s.get("file_path", ""),
                "impact_level": "directly_changed",
                "evidence_reason": f"Symbol was {s.get('change_type', 'modified')}",
                "depth": 0,
            })

        # 2. Dependency Graph Impact (Phase 8 traversal)
        # Find all modules that import the modified files
        try:
            dep_graph = await self.dependency_service.get_or_build_graph(session, repository_id)
            # Build reverse adjacency: target_path -> list of source_paths (who imports target_path)
            incoming_deps: Dict[str, List[str]] = defaultdict(list)
            for rel in dep_graph.relationships:
                if rel.category in ("internal", "circular"):
                    target_norm = rel.target_path.replace("\\", "/").lstrip("/")
                    source_norm = rel.source_path.replace("\\", "/").lstrip("/")
                    incoming_deps[target_norm].append(source_norm)

            for target_p in modified_or_deleted_paths:
                # Direct importers (Depth 1)
                direct_importers = set(incoming_deps.get(target_p, []))
                for imp in direct_importers:
                    ident = f"file:{imp}"
                    if ident not in visited_identifiers:
                        visited_identifiers.add(ident)
                        impact_records.append({
                            "affected_type": "file",
                            "affected_identifier": ident,
                            "affected_path": imp,
                            "impact_level": "directly_affected",
                            "evidence_reason": f"Directly imports modified module '{target_p}'",
                            "depth": 1,
                        })

                # Transitive importers (Depth 2+)
                queue = deque([(imp, 2) for imp in direct_importers])
                seen_transitive: Set[str] = set(direct_importers) | {target_p}

                while queue:
                    curr, depth = queue.popleft()
                    if depth > 4:  # limit traversal depth
                        continue
                    for nxt in incoming_deps.get(curr, []):
                        if nxt not in seen_transitive:
                            seen_transitive.add(nxt)
                            ident = f"file:{nxt}"
                            if ident not in visited_identifiers:
                                visited_identifiers.add(ident)
                                impact_records.append({
                                    "affected_type": "file",
                                    "affected_identifier": ident,
                                    "affected_path": nxt,
                                    "impact_level": "indirectly_affected",
                                    "evidence_reason": f"Transitively depends on '{target_p}' (depth {depth})",
                                    "depth": depth,
                                })
                            queue.append((nxt, depth + 1))
        except Exception as ex:
            logger.warning("Could not traverse dependency impact for repo %s: %s", repository_id, ex)

        # 3. Call Graph Impact (Phase 7 caller resolution)
        # Check callers of modified symbols
        try:
            calls_query = select(CodeCall).where(CodeCall.repository_id == repository_id)
            calls_res = await session.execute(calls_query)
            all_calls = list(calls_res.scalars().all())

            # Map callee_name -> list of calls
            incoming_calls: Dict[str, List[CodeCall]] = defaultdict(list)
            for c in all_calls:
                incoming_calls[c.callee_name].append(c)

            for sym in changed_symbols:
                s_name = sym.get("symbol_name")
                if not s_name:
                    continue

                for call in incoming_calls.get(s_name, []):
                    caller_ident = f"call:{call.caller_file_path}:{call.caller_name}"
                    if caller_ident not in visited_identifiers:
                        visited_identifiers.add(caller_ident)
                        level = "directly_affected" if call.confidence == "verified" else "potentially_affected"
                        impact_records.append({
                            "affected_type": "caller",
                            "affected_identifier": caller_ident,
                            "affected_path": call.caller_file_path,
                            "impact_level": level,
                            "evidence_reason": f"Invokes modified symbol '{s_name}' at line {call.line_number}",
                            "depth": 1,
                        })
        except Exception as ex:
            logger.warning("Could not traverse call graph impact for repo %s: %s", repository_id, ex)

        # 4. API Endpoints Impact (Phase 4 endpoints handled by changed symbols or files)
        try:
            endpoints_query = select(ApiRouteEndpoint).where(ApiRouteEndpoint.repository_id == repository_id)
            ep_res = await session.execute(endpoints_query)
            endpoints = list(ep_res.scalars().all())

            changed_sym_names = {s.get("symbol_name") for s in changed_symbols}

            for ep in endpoints:
                ep_ident = f"endpoint:{ep.http_method}:{ep.path}"
                if ep_ident in visited_identifiers:
                    continue

                # Direct match on handler name
                if ep.handler_name in changed_sym_names:
                    visited_identifiers.add(ep_ident)
                    impact_records.append({
                        "affected_type": "endpoint",
                        "affected_identifier": ep_ident,
                        "affected_path": ep.path,
                        "impact_level": "directly_affected",
                        "evidence_reason": f"Route handler '{ep.handler_name}' was modified",
                        "depth": 1,
                    })
        except Exception as ex:
            logger.warning("Could not map endpoint impact for repo %s: %s", repository_id, ex)

        # 5. Architecture Components Impact (Phase 6 mapping)
        try:
            arch_data = await self.architecture_service.get_or_build_graph(session, repository_id)
            arch_nodes = arch_data.get("nodes", [])
            for node in arch_nodes:
                node_path = (node.get("path") or "").replace("\\", "/").lstrip("/")
                if node_path in changed_file_paths or node_path in modified_or_deleted_paths:
                    node_ident = f"arch_node:{node.get('id')}:{node.get('label')}"
                    if node_ident not in visited_identifiers:
                        visited_identifiers.add(node_ident)
                        impact_records.append({
                            "affected_type": "architecture_component",
                            "affected_identifier": node_ident,
                            "affected_path": node_path,
                            "impact_level": "indirectly_affected",
                            "evidence_reason": f"Architectural layer/component contains modified files",
                            "depth": 2,
                        })
        except Exception as ex:
            logger.warning("Could not map architecture impact for repo %s: %s", repository_id, ex)

        # Calculate counts
        counts = {
            "directly_changed": len([r for r in impact_records if r["impact_level"] == "directly_changed"]),
            "directly_affected": len([r for r in impact_records if r["impact_level"] == "directly_affected"]),
            "indirectly_affected": len([r for r in impact_records if r["impact_level"] == "indirectly_affected"]),
            "potentially_affected": len([r for r in impact_records if r["impact_level"] == "potentially_affected"]),
            "unknown": len([r for r in impact_records if r["impact_level"] == "unknown"]),
        }

        return {
            "impact_records": impact_records,
            "metrics": counts,
            "total_impacted": len(impact_records),
        }

    @classmethod
    def build_impact_graph(
        cls,
        update_run_id: str,
        file_changes: List[Any],
        impact_records: List[Any],
    ) -> Dict[str, Any]:
        """Synthesizes interactive sub-graph nodes and edges for blast radius visualization."""
        nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        seen_nodes: Set[str] = set()

        for fc in file_changes:
            nid = f"file:{fc.path}"
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({
                    "id": nid,
                    "label": Path(fc.path).name,
                    "node_type": "file",
                    "impact_level": "directly_changed",
                    "path": fc.path,
                })

        for rec in impact_records:
            nid = rec.affected_identifier
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                label = rec.affected_identifier.split(":")[-1]
                nodes.append({
                    "id": nid,
                    "label": label,
                    "node_type": rec.affected_type,
                    "impact_level": rec.impact_level,
                    "path": rec.affected_path,
                })

            # Edge from changed file/symbol to impacted record
            for fc in file_changes:
                if fc.path in rec.evidence_reason or rec.affected_path == fc.path:
                    edges.append({
                        "source": f"file:{fc.path}",
                        "target": nid,
                        "edge_type": "impacts",
                        "impact_level": rec.impact_level,
                    })

        return {
            "update_run_id": update_run_id,
            "nodes": nodes,
            "edges": edges,
        }
