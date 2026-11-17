from dataclasses import dataclass, field
import json
from pathlib import PurePosixPath
from typing import Any, Dict, List, Optional, Set


@dataclass
class DetectedEntryPoint:
    entry_type: str  # "api_route", "main_entry", "cli_command", "background_job", "frontend_event"
    display_name: str
    file_path: str
    symbol_name: Optional[str] = None
    symbol_id: Optional[str] = None
    route_path: Optional[str] = None
    http_method: Optional[str] = None
    line_number: int = 1
    confidence: str = "verified"  # "verified" or "heuristic"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_type": self.entry_type,
            "display_name": self.display_name,
            "file_path": self.file_path,
            "symbol_name": self.symbol_name,
            "symbol_id": self.symbol_id,
            "route_path": self.route_path,
            "http_method": self.http_method,
            "line_number": self.line_number,
            "confidence": self.confidence,
            "description": self.description,
        }


class EntryPointDetector:
    """
    Identifies application execution entry points across backend endpoints,
    application startup scripts, CLI commands, background jobs, and frontend UI events.
    """

    STARTUP_FILE_NAMES = {
        "main.py", "app.py", "server.py", "run.py", "wsgi.py", "asgi.py",
        "index.ts", "index.tsx", "main.ts", "main.tsx", "server.ts", "app.ts", "App.tsx",
    }

    CLI_DECORATORS = {"command", "cli", "click.command", "app.command", "task"}
    BACKGROUND_JOB_MARKERS = {"celery.task", "task", "job", "cron", "worker", "scheduled"}

    @classmethod
    def detect_entry_points(
        cls,
        files: List[Any],  # RepositoryFile or path strings
        symbols: List[Any],  # CodeSymbol or ParsedSymbol
        endpoints: List[Any],  # ApiRouteEndpoint or ParsedEndpoint
    ) -> List[DetectedEntryPoint]:
        entry_points: List[DetectedEntryPoint] = []
        seen_keys: Set[str] = set()

        # Build symbol map by (file_path, symbol_name)
        # Handle file paths from file entities or strings
        file_map: Dict[str, Any] = {}
        for f in files:
            f_id = getattr(f, "id", None)
            f_path = getattr(f, "path", str(f)).replace("\\", "/").lstrip("/")
            if f_id:
                file_map[f_id] = f_path
            file_map[f_path] = f_path

        symbols_by_path: Dict[str, List[Any]] = {}
        for s in symbols:
            s_file_id = getattr(s, "file_id", None)
            s_fp = file_map.get(s_file_id) if s_file_id else getattr(s, "file_path", None)
            if not s_fp and hasattr(s, "file") and getattr(s, "file"):
                s_fp = getattr(s.file, "path", None)

            if s_fp:
                s_fp_norm = s_fp.replace("\\", "/").lstrip("/")
                if s_fp_norm not in symbols_by_path:
                    symbols_by_path[s_fp_norm] = []
                symbols_by_path[s_fp_norm].append(s)

        # 1. Detect Verified API Route Endpoints
        for ep in endpoints:
            ep_file_id = getattr(ep, "file_id", None)
            ep_path_str = file_map.get(ep_file_id, getattr(ep, "file_path", ""))
            ep_http = getattr(ep, "http_method", "GET").upper()
            ep_route = getattr(ep, "path", "/")
            ep_handler = getattr(ep, "handler_name", "handler")
            ep_line = getattr(ep, "start_line", 1)
            ep_framework = getattr(ep, "framework", "API")

            # Try to match symbol ID
            matching_sym_id = None
            for s in symbols_by_path.get(ep_path_str, []):
                if getattr(s, "name", "") == ep_handler:
                    matching_sym_id = getattr(s, "id", None)
                    break

            key = f"api:{ep_http}:{ep_route}:{ep_path_str}"
            if key not in seen_keys:
                seen_keys.add(key)
                entry_points.append(
                    DetectedEntryPoint(
                        entry_type="api_route",
                        display_name=f"{ep_http} {ep_route}",
                        file_path=ep_path_str,
                        symbol_name=ep_handler,
                        symbol_id=matching_sym_id,
                        route_path=ep_route,
                        http_method=ep_http,
                        line_number=ep_line,
                        confidence="verified",
                        description=f"{ep_framework} route handler `{ep_handler}`",
                    )
                )

        # 2. Detect Application Startup Entry Points
        for f in files:
            fp = getattr(f, "path", str(f)).replace("\\", "/").lstrip("/")
            file_name = PurePosixPath(fp).name

            if file_name in cls.STARTUP_FILE_NAMES:
                # Find main function if defined
                sym_list = symbols_by_path.get(fp, [])
                main_sym = next((s for s in sym_list if getattr(s, "name", "").lower() in ("main", "run", "start")), None)

                key = f"main:{fp}"
                if key not in seen_keys:
                    seen_keys.add(key)
                    entry_points.append(
                        DetectedEntryPoint(
                            entry_type="main_entry",
                            display_name=f"Startup: {file_name}",
                            file_path=fp,
                            symbol_name=getattr(main_sym, "name", None) if main_sym else None,
                            symbol_id=getattr(main_sym, "id", None) if main_sym else None,
                            line_number=getattr(main_sym, "start_line", 1) if main_sym else 1,
                            confidence="verified" if main_sym else "heuristic",
                            description=f"Application bootstrap entry point in `{file_name}`",
                        )
                    )

        # 3. Detect CLI Commands & Background Jobs via Decorators / Symbol Names
        for fp, sym_list in symbols_by_path.items():
            for s in sym_list:
                s_name = getattr(s, "name", "")
                s_id = getattr(s, "id", None)
                s_line = getattr(s, "start_line", 1)

                # Parse decorators if present (JSON string or list)
                decorators = getattr(s, "decorators", [])
                if isinstance(decorators, str):
                    try:
                        decorators = json.loads(decorators)
                    except Exception:
                        decorators = []

                dec_str = " ".join(decorators).lower()

                # CLI check
                if any(cli_mark in dec_str for cli_mark in cls.CLI_DECORATORS) or s_name.startswith("cli_"):
                    key = f"cli:{fp}:{s_name}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        entry_points.append(
                            DetectedEntryPoint(
                                entry_type="cli_command",
                                display_name=f"CLI: {s_name}",
                                file_path=fp,
                                symbol_name=s_name,
                                symbol_id=s_id,
                                line_number=s_line,
                                confidence="verified",
                                description=f"Command-line entry function `{s_name}`",
                            )
                        )

                # Background job check
                if any(job_mark in dec_str for job_mark in cls.BACKGROUND_JOB_MARKERS) or "worker" in s_name.lower() or "job" in s_name.lower():
                    key = f"job:{fp}:{s_name}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        entry_points.append(
                            DetectedEntryPoint(
                                entry_type="background_job",
                                display_name=f"Job: {s_name}",
                                file_path=fp,
                                symbol_name=s_name,
                                symbol_id=s_id,
                                line_number=s_line,
                                confidence="verified" if decorators else "heuristic",
                                description=f"Background task / job runner `{s_name}`",
                            )
                        )

                # API / Route Handler Candidate Check
                if (any(p in fp.lower() for p in ("/api/", "api/", "routes/", "controllers/", "handlers/")) or "endpoint" in s_name.lower()) and getattr(s, "symbol_type", "") in ("function", "method"):
                    key = f"api_candidate:{fp}:{s_name}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        entry_points.append(
                            DetectedEntryPoint(
                                entry_type="api_route",
                                display_name=f"Endpoint: {s_name}",
                                file_path=fp,
                                symbol_name=s_name,
                                symbol_id=s_id,
                                line_number=s_line,
                                confidence="heuristic",
                                description=f"API handler candidate `{s_name}` in `{fp}`",
                            )
                        )

                # Frontend UI Event / Handler Trigger Check
                if ("src" in fp or "client" in fp or "frontend" in fp) and (
                    s_name.startswith("handle") or s_name.startswith("submit") or s_name.startswith("on")
                ):
                    key = f"ui_event:{fp}:{s_name}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        entry_points.append(
                            DetectedEntryPoint(
                                entry_type="frontend_event",
                                display_name=f"UI Trigger: {s_name}",
                                file_path=fp,
                                symbol_name=s_name,
                                symbol_id=s_id,
                                line_number=s_line,
                                confidence="heuristic",
                                description=f"User interaction event trigger `{s_name}`",
                            )
                        )

        # Fallback for library repositories: pick top-level functions as heuristic entry points
        if not entry_points:
            for fp, sym_list in symbols_by_path.items():
                for s in sym_list[:3]:
                    s_name = getattr(s, "name", "")
                    s_id = getattr(s, "id", None)
                    s_line = getattr(s, "start_line", 1)
                    key = f"func:{fp}:{s_name}"
                    if key not in seen_keys:
                        seen_keys.add(key)
                        entry_points.append(
                            DetectedEntryPoint(
                                entry_type="function",
                                display_name=f"Function: {s_name}",
                                file_path=fp,
                                symbol_name=s_name,
                                symbol_id=s_id,
                                line_number=s_line,
                                confidence="heuristic",
                                description=f"Entry function candidate `{s_name}` in `{fp}`",
                            )
                        )
                        if len(entry_points) >= 5:
                            break
                if len(entry_points) >= 5:
                    break

        return entry_points
