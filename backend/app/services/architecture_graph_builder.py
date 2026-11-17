import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.module_resolver import ModuleResolver
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile
from app.services.architecture_classifier import ArchitectureClassifier


class ArchitectureGraphBuilder:
    """
    Synthesizes extracted static code intelligence (files, symbols, imports, endpoints)
    into a directed, multi-view architecture graph with 2D layered layout coordinates.
    """

    LAYER_X_POSITIONS = {
        "frontend_page": 50,
        "frontend": 400,
        "api": 750,
        "backend": 1100,
        "ai": 1100,
        "worker": 1100,
        "database": 1450,
        "utility": 1800,
        "external": 2150,
        "internal": 1100,
    }

    def __init__(
        self,
        repository_id: str,
        files: List[RepositoryFile],
        symbols: List[CodeSymbol],
        imports_exports: List[CodeImportExport],
        endpoints: List[ApiRouteEndpoint],
    ) -> None:
        self.repository_id = repository_id
        self.files = [f for f in files if f.file_type == "file" and not f.is_binary]
        self.symbols = symbols
        self.imports_exports = imports_exports
        self.endpoints = endpoints

        # Map file_id -> RepositoryFile
        self.file_map: Dict[str, RepositoryFile] = {f.id: f for f in self.files}
        # Map file_path -> RepositoryFile
        self.path_map: Dict[str, RepositoryFile] = {
            f.path.replace("\\", "/"): f for f in self.files
        }

        # Group symbols by file_id
        self.symbols_by_file: Dict[str, List[CodeSymbol]] = defaultdict(list)
        for s in symbols:
            self.symbols_by_file[s.file_id].append(s)

        # Group endpoints by file_id
        self.endpoints_by_file: Dict[str, List[ApiRouteEndpoint]] = defaultdict(list)
        for ep in endpoints:
            self.endpoints_by_file[ep.file_id].append(ep)

        # Group imports by file_id
        self.imports_by_file: Dict[str, List[CodeImportExport]] = defaultdict(list)
        for ie in imports_exports:
            self.imports_by_file[ie.file_id].append(ie)

        # Initialize ModuleResolver
        all_paths = list(self.path_map.keys())
        self.resolver = ModuleResolver(all_paths)

    def build_graph(self) -> Dict[str, Any]:
        """
        Builds the complete architecture graph data structure matching the frontend schema:
        {
            "repositoryId": str,
            "nodes": [...],
            "edges": [...],
            "views": {
                "system": { "viewMode": "system", "title": "System Overview", "nodes": [...], "edges": [...] },
                "frontend": { ... },
                "backend": { ... },
                "api": { ... },
                "database": { ... },
                "modules": { ... }
            }
        }
        """
        raw_nodes: Dict[str, Dict[str, Any]] = {}
        raw_edges: Dict[str, Dict[str, Any]] = {}

        # 1. Generate nodes for all source files
        for f in self.files:
            file_path = f.path.replace("\\", "/")
            node_id = f"node:{file_path}"

            file_symbols = self.symbols_by_file.get(f.id, [])
            file_endpoints = self.endpoints_by_file.get(f.id, [])

            category, group, role_desc, confidence = ArchitectureClassifier.classify_file(
                file_path=file_path,
                symbols=file_symbols,
                endpoints=file_endpoints,
            )

            # Collect exported symbols
            exports: List[str] = []
            for s in file_symbols:
                if s.is_exported or s.visibility == "public":
                    exports.append(s.name)
            if not exports and file_symbols:
                exports = [s.name for s in file_symbols[:5]]

            # Derive concise display label from file name
            file_name = file_path.split("/")[-1]
            label = file_name.split(".")[0]
            if label == "index" and len(file_path.split("/")) > 1:
                label = f"{file_path.split('/')[-2]}/index"

            raw_nodes[node_id] = {
                "id": node_id,
                "label": label,
                "category": category,
                "group": group,
                "filePath": file_path,
                "description": role_desc,
                "exports": exports[:10],
                "confidence": confidence,
                "position": {"x": 0.0, "y": 0.0},
            }

        # 2. Generate edges from imports/exports
        external_nodes: Dict[str, Dict[str, Any]] = {}

        for f in self.files:
            file_path = f.path.replace("\\", "/")
            source_node_id = f"node:{file_path}"
            file_imports = self.imports_by_file.get(f.id, [])

            for imp in file_imports:
                if imp.statement_type != "import":
                    continue

                target_path, is_ext = self.resolver.resolve_import(file_path, imp.source_module)

                if target_path:
                    target_node_id = f"node:{target_path}"
                    if target_node_id != source_node_id and target_node_id in raw_nodes:
                        edge_id = f"edge:{source_node_id}->{target_node_id}:import"
                        if edge_id not in raw_edges:
                            raw_edges[edge_id] = {
                                "id": edge_id,
                                "source": source_node_id,
                                "target": target_node_id,
                                "label": "imports",
                                "confidence": "verified",
                            }
                elif is_ext:
                    # Capture prominent third-party packages as external nodes
                    pkg = imp.source_module.split("/")[0].lstrip("@")
                    if pkg in ("react", "fastapi", "sqlalchemy", "pydantic", "radix-ui", "tailwindcss", "express"):
                        ext_id = f"ext:{pkg}"
                        if ext_id not in external_nodes:
                            external_nodes[ext_id] = {
                                "id": ext_id,
                                "label": pkg,
                                "category": "external",
                                "group": "external",
                                "filePath": f"node_modules/{pkg}",
                                "description": f"External Library ({pkg})",
                                "exports": [],
                                "confidence": "verified",
                                "position": {"x": 0.0, "y": 0.0},
                            }
                        edge_id = f"edge:{source_node_id}->{ext_id}:external"
                        if edge_id not in raw_edges:
                            raw_edges[edge_id] = {
                                "id": edge_id,
                                "source": source_node_id,
                                "target": ext_id,
                                "label": "uses",
                                "confidence": "verified",
                            }

        # Include prominent external nodes
        for ext_id, ext_node in external_nodes.items():
            raw_nodes[ext_id] = ext_node

        # 3. Detect Frontend-to-Backend API calls
        self._link_frontend_api_calls(raw_nodes, raw_edges)

        # 4. Assign 2D Layered Coordinates
        self._calculate_layered_positions(raw_nodes)

        nodes_list = list(raw_nodes.values())
        edges_list = list(raw_edges.values())

        # 5. Build View Mode Slices
        views = self._generate_view_slices(nodes_list, edges_list)

        return {
            "repositoryId": self.repository_id,
            "nodes": nodes_list,
            "edges": edges_list,
            "views": views,
        }

    def _link_frontend_api_calls(
        self,
        nodes: Dict[str, Any],
        edges: Dict[str, Any],
    ) -> None:
        """Heuristically connects frontend API services to corresponding backend endpoints."""
        if not self.endpoints:
            return

        # Map endpoint path segments to backend file nodes
        endpoint_patterns: List[Tuple[str, str, str]] = []  # (pattern, http_method, node_id)
        for ep in self.endpoints:
            backend_file = self.file_map.get(ep.file_id)
            if backend_file:
                b_path = backend_file.path.replace("\\", "/")
                # Normalize endpoint path (e.g. /api/v1/repositories -> repositories)
                parts = [p for p in ep.path.strip("/").split("/") if not p.startswith("{") and not p.startswith(":")]
                core_segment = parts[-1] if parts else ""
                if core_segment:
                    endpoint_patterns.append((core_segment.lower(), ep.http_method, f"node:{b_path}"))

        # Check frontend files
        for n_id, n in nodes.items():
            if n["category"] == "frontend" and ("api" in n["filePath"].lower() or "service" in n["filePath"].lower()):
                fp_lower = n["filePath"].lower()
                for seg, method, target_node_id in endpoint_patterns:
                    if seg in fp_lower and target_node_id != n_id and target_node_id in nodes:
                        edge_id = f"edge:{n_id}->{target_node_id}:api_call"
                        if edge_id not in edges:
                            edges[edge_id] = {
                                "id": edge_id,
                                "source": n_id,
                                "target": target_node_id,
                                "label": f"{method} API",
                                "confidence": "inferred",
                            }

    def _calculate_layered_positions(self, nodes: Dict[str, Any]) -> None:
        """Assigns non-overlapping (x, y) coordinates based on architectural layer columns."""
        layer_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for n in nodes.values():
            cat = n.get("category", "internal")
            desc = n.get("description", "")
            if "Page" in desc:
                bucket_key = "frontend_page"
            elif cat in self.LAYER_X_POSITIONS:
                bucket_key = cat
            else:
                bucket_key = "internal"

            layer_buckets[bucket_key].append(n)

        # Position each column
        for bucket_key, node_list in layer_buckets.items():
            x = self.LAYER_X_POSITIONS.get(bucket_key, 1100)
            # Sort alphabetically by label for visual consistency
            node_list.sort(key=lambda item: item["label"])

            for idx, node in enumerate(node_list):
                y = 50 + (idx * 140)
                node["position"] = {"x": float(x), "y": float(y)}

    def _generate_view_slices(
        self,
        all_nodes: List[Dict[str, Any]],
        all_edges: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        """Slices nodes and edges into the 6 canonical architecture views."""
        node_id_map = {n["id"]: n for n in all_nodes}

        def slice_graph(
            view_mode: str,
            title: str,
            subtitle: str,
            allowed_categories: Optional[Set[str]] = None,
            filter_fn: Optional[Any] = None,
        ) -> Dict[str, Any]:
            if filter_fn:
                v_nodes = [n for n in all_nodes if filter_fn(n)]
            elif allowed_categories:
                v_nodes = [n for n in all_nodes if n.get("category") in allowed_categories]
            else:
                v_nodes = all_nodes

            v_node_ids = {n["id"] for n in v_nodes}
            v_edges = [e for e in all_edges if e["source"] in v_node_ids and e["target"] in v_node_ids]

            return {
                "viewMode": view_mode,
                "title": title,
                "subtitle": subtitle,
                "nodes": v_nodes,
                "edges": v_edges,
            }

        return {
            "system": slice_graph(
                "system",
                "System Overview",
                "High-level application architecture and major subsystem boundaries.",
            ),
            "frontend": slice_graph(
                "frontend",
                "Frontend Architecture",
                "Pages, views, UI components, state stores, and client services.",
                filter_fn=lambda n: n.get("category") in ("frontend", "utility")
                or n.get("filePath", "").startswith(("src/", "frontend/"))
                or n.get("filePath", "").endswith((".tsx", ".jsx", ".vue", ".svelte")),
            ),
            "backend": slice_graph(
                "backend",
                "Backend Architecture",
                "API routers, domain services, workers, repositories, and AI services.",
                filter_fn=lambda n: n.get("category") in ("backend", "api", "ai", "worker", "database", "internal", "utility")
                or (n.get("category") == "authentication" and not n.get("filePath", "").startswith(("src/", "frontend/"))),
            ),
            "api": slice_graph(
                "api",
                "API Connections",
                "HTTP endpoints, controllers, route handlers, and API client adapters.",
                filter_fn=lambda n: n.get("category") == "api" or "api" in n.get("filePath", "").lower(),
            ),
            "database": slice_graph(
                "database",
                "Database Relationships",
                "Relational models, database entities, schema definitions, and ORM tables.",
                filter_fn=lambda n: n.get("category") == "database"
                or "model" in n.get("filePath", "").lower()
                or "schema" in n.get("filePath", "").lower(),
            ),
            "modules": slice_graph(
                "modules",
                "Module Dependencies",
                "Complete package and file import topology across all subsystems.",
            ),
        }
