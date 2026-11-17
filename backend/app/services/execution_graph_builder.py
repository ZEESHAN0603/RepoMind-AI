from collections import defaultdict, deque
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_call import CodeCall
from app.models.code_symbol import CodeSymbol
from app.models.execution_entry_point import ExecutionEntryPoint
from app.models.repository_file import RepositoryFile


class ExecutionFlowGraphBuilder:
    """
    Synthesizes static calls, symbols, and entry points into an interactive,
    depth-layered execution flow graph workspace compatible with @xyflow/react.
    """

    MAX_TRAVERSAL_DEPTH = 5
    MAX_NODES_PER_TRACE = 50

    def __init__(
        self,
        repository_id: str,
        repository_name: str,
        files: List[RepositoryFile],
        symbols: List[CodeSymbol],
        endpoints: List[ApiRouteEndpoint],
        calls: List[CodeCall],
        entry_points: List[ExecutionEntryPoint],
        workspace_path: Optional[Path] = None,
    ) -> None:
        self.repository_id = repository_id
        self.repository_name = repository_name
        self.files = files
        self.symbols = symbols
        self.endpoints = endpoints
        self.calls = calls
        self.entry_points = entry_points
        self.workspace_path = workspace_path

        # Index file_id -> RepositoryFile
        self.file_map: Dict[str, RepositoryFile] = {f.id: f for f in self.files}
        # Index path -> RepositoryFile
        self.path_map: Dict[str, RepositoryFile] = {
            f.path.replace("\\", "/").lstrip("/"): f for f in self.files
        }

        # Index symbol_id -> CodeSymbol
        self.symbol_map: Dict[str, CodeSymbol] = {s.id: s for s in self.symbols}
        # Index (file_path, symbol_name) -> CodeSymbol
        self.symbol_by_path_name: Dict[Tuple[str, str], CodeSymbol] = {}
        for s in self.symbols:
            f = self.file_map.get(s.file_id)
            if f:
                fp = f.path.replace("\\", "/").lstrip("/")
                self.symbol_by_path_name[(fp, s.name)] = s

        # Index calls: caller_id -> list of calls, callee_id -> list of calls
        self.outgoing_calls_by_symbol: Dict[str, List[CodeCall]] = defaultdict(list)
        self.incoming_calls_by_symbol: Dict[str, List[CodeCall]] = defaultdict(list)
        for c in self.calls:
            if c.caller_symbol_id:
                self.outgoing_calls_by_symbol[c.caller_symbol_id].append(c)
            if c.callee_symbol_id:
                self.incoming_calls_by_symbol[c.callee_symbol_id].append(c)

    def build_workspace(self) -> Dict[str, Any]:
        """Builds the full ExecutionTraceWorkspace JSON payload."""
        functions = self._build_function_symbols()
        traces = self._build_execution_traces(functions)

        return {
            "repositoryId": self.repository_id,
            "repositoryName": self.repository_name,
            "functions": functions,
            "traces": traces,
        }

    def _build_function_symbols(self) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []

        for s in self.symbols:
            if s.symbol_type not in ("function", "method"):
                continue

            f = self.file_map.get(s.file_id)
            fp = f.path.replace("\\", "/") if f else "unknown"

            # Parse parameters
            params_str = "()"
            try:
                params_list = json.loads(s.parameters) if s.parameters else []
                if params_list:
                    p_formatted = [f"{p.get('name', '')}: {p.get('type_annotation') or 'any'}" for p in params_list]
                    params_str = f"({', '.join(p_formatted)})"
            except Exception:
                pass

            # Derive nodeType
            node_type = "method" if s.scope else "function"
            if "api" in fp.lower() or "endpoint" in fp.lower() or "route" in fp.lower():
                node_type = "api"
            elif "repository" in fp.lower() or "model" in fp.lower() or "db" in fp.lower():
                node_type = "database"

            # Callers & Callees
            incoming = self.incoming_calls_by_symbol.get(s.id, [])
            outgoing = self.outgoing_calls_by_symbol.get(s.id, [])

            caller_ids = list({c.caller_symbol_id for c in incoming if c.caller_symbol_id})
            callee_ids = list({c.callee_symbol_id for c in outgoing if c.callee_symbol_id})

            # Related function names
            related: Set[str] = set()
            for c in incoming:
                if c.caller_name:
                    related.add(c.caller_name.split(".")[-1])
            for c in outgoing:
                related.add(c.callee_name.split(".")[-1])
            related.discard(s.name)

            # Code snippet
            code_snippet = self._get_snippet_for_symbol(f, s)

            # Status
            status = "verified"
            if any(c.resolution_status == "unresolved" for c in outgoing):
                status = "unresolved"
            elif any(c.resolution_status == "heuristic" for c in outgoing):
                status = "inferred"

            result.append({
                "id": s.id,
                "label": s.name,
                "name": s.name,
                "filePath": fp,
                "lineNumber": s.start_line,
                "nodeType": node_type,
                "parameters": params_str,
                "returnType": s.return_type or "void",
                "description": s.docstring or f"{s.symbol_type.capitalize()} `{s.name}` defined in `{fp}`.",
                "status": status,
                "callers": caller_ids,
                "callees": callee_ids,
                "relatedFunctions": sorted(list(related))[:6],
                "codeSnippet": code_snippet,
            })

        return result

    def _build_execution_traces(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        func_map = {f["id"]: f for f in functions}
        traces: List[Dict[str, Any]] = []

        # If no explicit entry points exist, treat first 5 functions as heuristic entry points
        target_entry_points = self.entry_points
        if not target_entry_points and functions:
            target_entry_points = [
                ExecutionEntryPoint(
                    id=f"ep-heur-{idx}",
                    repository_id=self.repository_id,
                    symbol_id=fn["id"],
                    file_path=fn["filePath"],
                    entry_type="function",
                    display_name=fn["name"],
                    symbol_name=fn["name"],
                    line_number=fn["lineNumber"],
                    confidence="heuristic",
                    description=f"Entry function `{fn['name']}`",
                )
                for idx, fn in enumerate(functions[:5])
            ]

        for ep in target_entry_points:
            root_node_id = ep.symbol_id or f"ep-node-{ep.id}"
            flow_id = f"flow-{ep.id}"

            # If entry point points to a symbol
            root_fn = func_map.get(ep.symbol_id) if ep.symbol_id else None

            # Traverse execution tree from root
            nodes_dict: Dict[str, Dict[str, Any]] = {}
            edges_list: List[Dict[str, Any]] = []
            steps_list: List[Dict[str, Any]] = []

            # Initialize Root Node
            if root_fn:
                nodes_dict[root_fn["id"]] = {
                    **root_fn,
                    "depth": 0,
                    "position": {"x": 50.0, "y": 80.0},
                }
            else:
                nodes_dict[root_node_id] = {
                    "id": root_node_id,
                    "label": ep.display_name,
                    "nodeType": "api" if ep.entry_type == "api_route" else "function",
                    "filePath": ep.file_path,
                    "lineNumber": ep.line_number,
                    "parameters": "()",
                    "returnType": "void",
                    "description": ep.description,
                    "status": "verified" if ep.confidence == "verified" else "inferred",
                    "callers": [],
                    "callees": [],
                    "relatedFunctions": [],
                    "codeSnippet": f"# Entry Point: {ep.display_name}\n# File: {ep.file_path}:{ep.line_number}",
                    "depth": 0,
                    "position": {"x": 50.0, "y": 80.0},
                }

            # BFS Traversal
            queue: deque = deque([(root_node_id, 0)])
            visited: Set[str] = {root_node_id}
            depth_counts: Dict[int, int] = defaultdict(int)
            depth_counts[0] = 1
            step_counter = 1

            while queue and len(nodes_dict) < self.MAX_NODES_PER_TRACE:
                curr_id, curr_depth = queue.popleft()
                if curr_depth >= self.MAX_TRAVERSAL_DEPTH:
                    continue

                outgoing = self.outgoing_calls_by_symbol.get(curr_id, [])

                # If root was synthetic entry point with matching file, connect to functions in that file
                if not outgoing and curr_id == root_node_id and ep.entry_type == "api_route":
                    # Connect to route handler function if symbol matches
                    for fn in functions:
                        if fn["filePath"] == ep.file_path and fn["name"] == ep.symbol_name:
                            target_id = fn["id"]
                            if target_id not in nodes_dict:
                                next_depth = curr_depth + 1
                                y_pos = 60.0 + (depth_counts[next_depth] * 140.0)
                                depth_counts[next_depth] += 1
                                nodes_dict[target_id] = {
                                    **fn,
                                    "depth": next_depth,
                                    "position": {"x": 50.0 + (next_depth * 300.0), "y": y_pos},
                                }
                                queue.append((target_id, next_depth))

                            edge_id = f"e:{curr_id}->{target_id}"
                            edges_list.append({
                                "id": edge_id,
                                "source": curr_id,
                                "target": target_id,
                                "label": "handles",
                                "status": "verified",
                            })
                            steps_list.append({
                                "stepOrder": step_counter,
                                "caller": ep.display_name,
                                "callee": fn["name"],
                                "dataPassed": "Request Context",
                                "description": f"HTTP route triggers handler function `{fn['name']}`.",
                                "status": "verified",
                            })
                            step_counter += 1

                for c in outgoing:
                    callee_id = c.callee_symbol_id
                    target_fn = func_map.get(callee_id) if callee_id else None

                    # If internal function resolved
                    if target_fn:
                        t_id = target_fn["id"]
                        if t_id not in nodes_dict:
                            next_depth = curr_depth + 1
                            y_pos = 60.0 + (depth_counts[next_depth] * 140.0)
                            depth_counts[next_depth] += 1
                            nodes_dict[t_id] = {
                                **target_fn,
                                "depth": next_depth,
                                "position": {"x": 50.0 + (next_depth * 300.0), "y": y_pos},
                            }
                            if t_id not in visited:
                                visited.add(t_id)
                                queue.append((t_id, next_depth))

                        edge_id = f"e:{curr_id}->{t_id}:{c.line_number}"
                        if not any(e["id"] == edge_id for e in edges_list):
                            edges_list.append({
                                "id": edge_id,
                                "source": curr_id,
                                "target": t_id,
                                "label": "calls",
                                "status": c.resolution_status if c.resolution_status in ("verified", "inferred") else "verified",
                                "dataPassed": ", ".join(json.loads(c.arguments_json)) if c.arguments_json != "[]" else "",
                            })

                        caller_label = nodes_dict[curr_id].get("name", nodes_dict[curr_id].get("label", "caller"))
                        steps_list.append({
                            "stepOrder": step_counter,
                            "caller": caller_label,
                            "callee": target_fn["name"],
                            "dataPassed": ", ".join(json.loads(c.arguments_json)) if c.arguments_json != "[]" else "",
                            "description": c.evidence or f"`{caller_label}` invokes `{target_fn['name']}` at line {c.line_number}.",
                            "status": "verified",
                        })
                        step_counter += 1

                    elif c.resolution_status == "external" or c.resolution_status == "unresolved":
                        # External library or unresolved dynamic call
                        ext_node_id = f"call-node:{c.id}"
                        if ext_node_id not in nodes_dict and len(nodes_dict) < self.MAX_NODES_PER_TRACE:
                            next_depth = curr_depth + 1
                            y_pos = 60.0 + (depth_counts[next_depth] * 140.0)
                            depth_counts[next_depth] += 1

                            node_type = "external" if c.resolution_status == "external" else "function"
                            nodes_dict[ext_node_id] = {
                                "id": ext_node_id,
                                "label": c.callee_name,
                                "nodeType": node_type,
                                "filePath": c.callee_file_path or c.caller_file_path,
                                "lineNumber": c.line_number,
                                "parameters": "()",
                                "returnType": "unknown",
                                "description": f"{c.resolution_status.capitalize()} call `{c.callee_name}`",
                                "status": "verified" if c.resolution_status == "external" else "unresolved",
                                "callers": [curr_id],
                                "callees": [],
                                "relatedFunctions": [],
                                "codeSnippet": c.evidence or f"# Call to {c.callee_name}",
                                "depth": next_depth,
                                "position": {"x": 50.0 + (next_depth * 300.0), "y": y_pos},
                            }

                            edge_id = f"e:{curr_id}->{ext_node_id}"
                            edges_list.append({
                                "id": edge_id,
                                "source": curr_id,
                                "target": ext_node_id,
                                "label": "invokes" if c.resolution_status == "external" else "unresolved",
                                "status": "verified" if c.resolution_status == "external" else "unresolved",
                                "dataPassed": ", ".join(json.loads(c.arguments_json)) if c.arguments_json != "[]" else "",
                            })

                            caller_label = nodes_dict[curr_id].get("name", nodes_dict[curr_id].get("label", "caller"))
                            steps_list.append({
                                "stepOrder": step_counter,
                                "caller": caller_label,
                                "callee": c.callee_name,
                                "dataPassed": ", ".join(json.loads(c.arguments_json)) if c.arguments_json != "[]" else "",
                                "description": c.evidence or f"`{caller_label}` calls `{c.callee_name}`.",
                                "status": "verified" if c.resolution_status == "external" else "unresolved",
                            })
                            step_counter += 1

            traces.append({
                "flow": {
                    "id": flow_id,
                    "title": ep.display_name,
                    "triggerType": "api-endpoint" if ep.entry_type == "api_route" else (
                        "event" if ep.entry_type == "frontend_event" else "function"
                    ),
                    "entryPoint": ep.display_name,
                    "summary": ep.description or f"Execution flow initiated by {ep.display_name}.",
                    "rootNodeId": root_node_id,
                    "steps": steps_list,
                },
                "nodes": list(nodes_dict.values()),
                "edges": edges_list,
            })

        return traces

    def _get_snippet_for_symbol(self, file_ent: Optional[RepositoryFile], sym: CodeSymbol) -> str:
        if not self.workspace_path or not file_ent:
            return f"# {sym.symbol_type.capitalize()}: {sym.signature}\n# Defined at lines {sym.start_line}-{sym.end_line}"

        disk_path = self.workspace_path / file_ent.path
        if disk_path.is_file():
            try:
                with open(disk_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                start = max(0, sym.start_line - 1)
                end = min(len(lines), sym.end_line)
                return "".join(lines[start:end])
            except Exception:
                pass

        return f"# {sym.symbol_type.capitalize()}: {sym.signature}\n# Defined at lines {sym.start_line}-{sym.end_line}"
