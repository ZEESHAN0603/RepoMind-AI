from collections import defaultdict, deque
import math
import os
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.module_resolver import ModuleResolver
from app.schemas.dependency import (
    CircularDependencyCycle,
    CycleSeverity,
    DependencyAnalysisData,
    DependencyCategory,
    DependencyModuleNode,
    DependencyNodeType,
    DependencyRelationship,
    Position,
)


class DependencyAnalysisEngine:
    """
    High-performance dependency intelligence and cycle detection engine.
    Extracts direct & transitive dependencies, detects circular dependencies via Tarjan's SCC,
    and isolates unresolved imports with source evidence.
    """

    def __init__(
        self,
        workspace_files: List[str],
        file_languages: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        :param workspace_files: Relative paths of all discovered repository files.
        :param file_languages: Mapping of relative file path -> detected language.
        """
        self.workspace_files = [f.replace("\\", "/").lstrip("/") for f in workspace_files]
        self.file_set = set(self.workspace_files)
        self.file_languages = {
            k.replace("\\", "/").lstrip("/"): v for k, v in (file_languages or {}).items()
        }
        self.module_resolver = ModuleResolver(self.workspace_files)

    def analyze(
        self,
        repository_id: str,
        imports_data: List[Dict[str, Any]],
        manifests_data: Optional[List[Dict[str, Any]]] = None,
    ) -> DependencyAnalysisData:
        """
        Synthesizes complete dependency graph and cycle analysis.

        :param repository_id: Unique UUID of repository.
        :param imports_data: List of extracted imports from static analysis.
        :param manifests_data: List of extracted package manifests.
        """
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        edge_details: Dict[Tuple[str, str], Dict[str, Any]] = {}
        all_nodes: Dict[str, Dict[str, Any]] = {}

        # 1. Initialize internal nodes from workspace files
        for f in self.workspace_files:
            if not f or f.endswith(("/", "\\")):
                continue
            all_nodes[f] = {
                "id": f,
                "label": PurePosixPath(f).name,
                "filePath": f,
                "nodeType": "file",
                "category": "internal",
                "language": self.file_languages.get(f, "Unknown"),
                "exportsCount": 0,
            }

        # 2. Process extracted code imports
        unresolved_count = 0
        internal_count = 0
        external_count = 0
        relationships: List[DependencyRelationship] = []

        for imp in imports_data:
            src_file = imp.get("source_file", "").replace("\\", "/").lstrip("/")
            mod_str = imp.get("source_module", "").strip()
            line_no = imp.get("line_number", 1)
            sym = imp.get("symbol_name")

            if not src_file or not mod_str:
                continue

            # Ensure source node exists
            if src_file not in all_nodes:
                all_nodes[src_file] = {
                    "id": src_file,
                    "label": PurePosixPath(src_file).name,
                    "filePath": src_file,
                    "nodeType": "file",
                    "category": "internal",
                    "language": self.file_languages.get(src_file, "Unknown"),
                    "exportsCount": 0,
                }

            resolved_path, is_ext = self.module_resolver.resolve_import(src_file, mod_str)

            if resolved_path:
                target_key = resolved_path
                cat: DependencyCategory = "internal"
                internal_count += 1
                adjacency[src_file].add(target_key)
            elif is_ext:
                target_key = f"pkg:{mod_str}"
                cat = "external"
                external_count += 1
                if target_key not in all_nodes:
                    all_nodes[target_key] = {
                        "id": target_key,
                        "label": mod_str,
                        "filePath": target_key,
                        "nodeType": "package",
                        "category": "external",
                        "language": all_nodes[src_file]["language"],
                        "exportsCount": 0,
                    }
                adjacency[src_file].add(target_key)
            else:
                # Unresolved import
                target_key = f"unresolved:{mod_str}"
                cat = "unresolved"
                unresolved_count += 1
                if target_key not in all_nodes:
                    all_nodes[target_key] = {
                        "id": target_key,
                        "label": mod_str,
                        "filePath": target_key,
                        "nodeType": "module",
                        "category": "unresolved",
                        "language": all_nodes[src_file]["language"],
                        "exportsCount": 0,
                    }

            edge_key = (src_file, target_key)
            if edge_key not in edge_details:
                edge_details[edge_key] = {
                    "id": f"rel_{len(edge_details) + 1}",
                    "sourceModule": src_file,
                    "sourcePath": src_file,
                    "targetModule": target_key,
                    "targetPath": target_key,
                    "category": cat,
                    "language": all_nodes[src_file]["language"],
                    "importSpecifiers": [sym] if sym else [],
                    "confidence": "verified",
                    "line_number": line_no,
                }
            else:
                if sym and sym not in edge_details[edge_key]["importSpecifiers"]:
                    edge_details[edge_key]["importSpecifiers"].append(sym)

        # 3. Detect Circular Dependencies (restricted to internal nodes)
        cycles = self._detect_cycles_tarjan(adjacency)

        # Mark circular category on edges and nodes
        circular_nodes: Set[str] = set()
        for cyc in cycles:
            for p in cyc.file_paths:
                circular_nodes.add(p)

        for (s, t), rel_dict in edge_details.items():
            if s in circular_nodes and t in circular_nodes:
                # Check if this edge is actually part of a cycle
                for cyc in cycles:
                    for i in range(len(cyc.file_paths) - 1):
                        if cyc.file_paths[i] == s and cyc.file_paths[i + 1] == t:
                            rel_dict["category"] = "circular"
                            break

            relationships.append(DependencyRelationship(**rel_dict))

        # 4. Generate visual layout coordinates (2D grid layout)
        node_models = self._compute_layout(all_nodes, adjacency)

        # 5. Build summary payload
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

        return DependencyAnalysisData(
            repository_id=repository_id,
            last_analyzed=now_iso,
            total_modules=len(node_models),
            total_imports=len(relationships),
            internal_count=internal_count,
            external_count=external_count,
            circular_count=len(cycles),
            unresolved_count=unresolved_count,
            nodes=node_models,
            relationships=relationships,
            cycles=cycles,
        )

    def _detect_cycles_tarjan(
        self,
        adjacency: Dict[str, Set[str]],
    ) -> List[CircularDependencyCycle]:
        """
        Executes Tarjan's Strongly Connected Components algorithm to identify all cycles.
        Deduplicates cycles into canonical forms and computes impact & recommendations.
        """
        # Restrict cycle search to internal workspace files only
        internal_adj: Dict[str, List[str]] = {
            u: [v for v in neighbors if v in self.file_set]
            for u, neighbors in adjacency.items()
            if u in self.file_set
        }

        index = 0
        stack: List[str] = []
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: Set[str] = set()
        sccs: List[List[str]] = []

        def strongconnect(v: str) -> None:
            nonlocal index
            indices[v] = index
            lowlink[v] = index
            index += 1
            stack.append(v)
            on_stack.add(v)

            for w in internal_adj.get(v, []):
                if w not in indices:
                    strongconnect(w)
                    lowlink[v] = min(lowlink[v], lowlink[w])
                elif w in on_stack:
                    lowlink[v] = min(lowlink[v], indices[w])

            if lowlink[v] == indices[v]:
                scc = []
                while True:
                    w = stack.pop()
                    on_stack.remove(w)
                    scc.append(w)
                    if w == v:
                        break
                if len(scc) > 1:
                    sccs.append(scc)
                elif len(scc) == 1 and v in internal_adj.get(v, []):
                    # Self-loop
                    sccs.append(scc)

        for node in list(internal_adj.keys()):
            if node not in indices:
                strongconnect(node)

        # Extract elementary cycles from each SCC
        detected_cycles: List[CircularDependencyCycle] = []
        seen_canonical_cycles: Set[Tuple[str, ...]] = set()

        for scc in sccs:
            subgraph_nodes = set(scc)
            sub_adj = {
                u: [v for v in internal_adj.get(u, []) if v in subgraph_nodes]
                for u in scc
            }

            # Find simple cycles using DFS within SCC
            simple_cycles = self._find_simple_cycles_in_scc(sub_adj)

            for path in simple_cycles:
                if len(path) < 2:
                    continue
                # Canonical representation: rotate to start with smallest element
                core = path[:-1]
                min_idx = core.index(min(core))
                canonical = tuple(core[min_idx:] + core[:min_idx])

                if canonical in seen_canonical_cycles:
                    continue
                seen_canonical_cycles.add(canonical)

                cycle_files = list(canonical) + [canonical[0]]
                cycle_labels = [PurePosixPath(p).stem for p in cycle_files]

                # Severity classification
                count = len(canonical)
                dirs = set(PurePosixPath(p).parent for p in canonical)
                if count >= 4 or len(dirs) > 1:
                    severity: CycleSeverity = "high"
                elif count == 3:
                    severity = "medium"
                else:
                    severity = "low"

                cyc_id = f"cycle_{len(detected_cycles) + 1}"
                desc = f"Circular dependency between {' -> '.join(cycle_labels)}"
                impact = (
                    f"Tight coupling across {count} modules ({len(dirs)} distinct directories). "
                    "Increases regression risk and prevents independent compilation or testing."
                )
                recommendation = (
                    f"Extract shared interfaces or types from {cycle_labels[0]} and {cycle_labels[1]} "
                    "into a separate foundation module, or employ dependency injection."
                )

                detected_cycles.append(
                    CircularDependencyCycle(
                        id=cyc_id,
                        severity=severity,
                        cycle_path=cycle_files,
                        file_paths=cycle_files,
                        affected_count=count,
                        description=desc,
                        impact=impact,
                        recommendation=recommendation,
                        confidence="verified",
                    )
                )

        return detected_cycles

    def _find_simple_cycles_in_scc(self, sub_adj: Dict[str, List[str]]) -> List[List[str]]:
        """Finds elementary directed cycles within a strongly connected subgraph."""
        cycles: List[List[str]] = []
        nodes = list(sub_adj.keys())

        for start_node in nodes:
            visited_in_path: Set[str] = {start_node}
            path: List[str] = [start_node]

            def dfs(current: str) -> None:
                if len(cycles) > 50:  # Bound cycle extraction for large graphs
                    return
                for neighbor in sub_adj.get(current, []):
                    if neighbor == start_node and len(path) > 1:
                        cycles.append(path + [start_node])
                    elif neighbor not in visited_in_path and neighbor > start_node:
                        visited_in_path.add(neighbor)
                        path.append(neighbor)
                        dfs(neighbor)
                        path.pop()
                        visited_in_path.remove(neighbor)

            dfs(start_node)

        return cycles

    def _compute_layout(
        self,
        all_nodes: Dict[str, Dict[str, Any]],
        adjacency: Dict[str, Set[str]],
    ) -> List[DependencyModuleNode]:
        """Computes clean 2D coordinates for @xyflow/react canvas rendering."""
        node_models: List[DependencyModuleNode] = []

        # Sort nodes by category then alphabetical
        sorted_keys = sorted(
            all_nodes.keys(),
            key=lambda k: (all_nodes[k]["category"] != "internal", all_nodes[k]["nodeType"], k),
        )

        columns = max(1, int(math.ceil(math.sqrt(len(sorted_keys) * 1.5))))
        spacing_x = 280
        spacing_y = 140

        for idx, key in enumerate(sorted_keys):
            n_data = all_nodes[key]
            row = idx // columns
            col = idx % columns

            x = float(col * spacing_x + 50)
            y = float(row * spacing_y + 50)

            node_models.append(
                DependencyModuleNode(
                    id=n_data["id"],
                    label=n_data["label"],
                    file_path=n_data["filePath"],
                    node_type=n_data["nodeType"],
                    category=n_data["category"] if n_data["category"] in ("internal", "external") else "internal",
                    language=n_data["language"],
                    exports_count=n_data.get("exportsCount", 0),
                    position=Position(x=x, y=y),
                )
            )

        return node_models
