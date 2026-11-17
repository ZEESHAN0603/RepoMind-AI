from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.analysis.module_resolver import ModuleResolver
from app.analysis.schemas import ParsedCall, ParsedEndpoint, ParsedImportExport, ParsedSymbol, ConfidenceLevel


@dataclass
class ResolvedCall:
    caller_name: Optional[str]
    callee_name: str
    caller_file_path: str
    callee_file_path: Optional[str]
    line_number: int
    call_type: str = "function_call"
    resolution_status: str = "unresolved"  # "resolved_internal", "external", "heuristic", "unresolved"
    confidence: str = "verified"  # "verified", "inferred", "unknown"
    caller_symbol_id: Optional[str] = None
    callee_symbol_id: Optional[str] = None
    callee_symbol_name: Optional[str] = None
    arguments: List[str] = field(default_factory=list)
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "caller_name": self.caller_name,
            "callee_name": self.callee_name,
            "caller_file_path": self.caller_file_path,
            "callee_file_path": self.callee_file_path,
            "line_number": self.line_number,
            "call_type": self.call_type,
            "resolution_status": self.resolution_status,
            "confidence": self.confidence,
            "caller_symbol_id": self.caller_symbol_id,
            "callee_symbol_id": self.callee_symbol_id,
            "callee_symbol_name": self.callee_symbol_name,
            "arguments": self.arguments,
            "evidence": self.evidence,
        }


class CallResolver:
    """
    Statically resolves raw function/method calls to concrete symbol definitions
    across local files, imported modules, and third-party external libraries.
    """

    KNOWN_EXTERNAL_PREFIXES = {
        # Python stdlib & popular libraries
        "os", "sys", "math", "json", "re", "time", "datetime", "logging", "asyncio", "typing",
        "pathlib", "uuid", "hashlib", "copy", "collections", "functools", "itertools",
        "fastapi", "pydantic", "sqlalchemy", "starlette", "httpx", "requests", "jwt",
        "passlib", "pytest", "alembic", "uvicorn", "celery", "dotenv",
        # JS/TS stdlib & popular libraries
        "react", "react-dom", "react-router-dom", "vue", "angular", "express", "axios",
        "lodash", "zod", "lucide-react", "clsx", "tailwind-merge", "sonner", "@xyflow/react",
        "console", "Math", "JSON", "Promise", "Object", "Array", "String", "Number", "Boolean",
    }

    def __init__(
        self,
        workspace_files: List[str],
        symbols_by_file: Dict[str, List[Any]],  # file_path -> list of CodeSymbol or ParsedSymbol
        imports_by_file: Dict[str, List[Any]],  # file_path -> list of CodeImportExport or ParsedImportExport
    ) -> None:
        self.workspace_files = [f.replace("\\", "/").lstrip("/") for f in workspace_files]
        self.resolver = ModuleResolver(self.workspace_files)

        # Normalize symbols by file
        self.symbols_by_file: Dict[str, List[Any]] = {
            f.replace("\\", "/").lstrip("/"): syms for f, syms in symbols_by_file.items()
        }

        # Build fast lookup indexes
        # file_path -> { symbol_name: symbol }
        self._symbols_in_file: Dict[str, Dict[str, Any]] = {}
        # file_path -> { (scope, name): symbol }
        self._scoped_symbols_in_file: Dict[str, Dict[Tuple[Optional[str], str], Any]] = {}
        # global name -> list of (file_path, symbol)
        self._global_symbols: Dict[str, List[Tuple[str, Any]]] = {}

        for fp, sym_list in self.symbols_by_file.items():
            name_map = {}
            scoped_map = {}
            for s in sym_list:
                s_name = getattr(s, "name", "")
                s_scope = getattr(s, "scope", None)
                name_map[s_name] = s
                scoped_map[(s_scope, s_name)] = s

                if s_name not in self._global_symbols:
                    self._global_symbols[s_name] = []
                self._global_symbols[s_name].append((fp, s))

            self._symbols_in_file[fp] = name_map
            self._scoped_symbols_in_file[fp] = scoped_map

        # Normalize imports by file: file_path -> list of imports
        self.imports_by_file: Dict[str, List[Any]] = {
            f.replace("\\", "/").lstrip("/"): imps for f, imps in imports_by_file.items()
        }

    def resolve_calls_for_file(
        self,
        file_path: str,
        calls: List[ParsedCall],
    ) -> List[ResolvedCall]:
        norm_fp = file_path.replace("\\", "/").lstrip("/")
        resolved_list: List[ResolvedCall] = []

        local_symbols = self._symbols_in_file.get(norm_fp, {})
        local_scoped = self._scoped_symbols_in_file.get(norm_fp, {})
        file_imports = self.imports_by_file.get(norm_fp, [])

        for call in calls:
            resolved = self._resolve_single_call(
                norm_fp=norm_fp,
                call=call,
                local_symbols=local_symbols,
                local_scoped=local_scoped,
                file_imports=file_imports,
            )
            resolved_list.append(resolved)

        return resolved_list

    def _resolve_single_call(
        self,
        norm_fp: str,
        call: ParsedCall,
        local_symbols: Dict[str, Any],
        local_scoped: Dict[Tuple[Optional[str], str], Any],
        file_imports: List[Any],
    ) -> ResolvedCall:
        callee_full = call.callee_name.strip()
        caller_name = call.caller_name
        callee_attr = call.callee_attribute

        # Match caller symbol ID if caller_name is known
        caller_symbol_id = None
        if caller_name:
            c_sym = local_symbols.get(caller_name.split(".")[-1])
            if c_sym:
                caller_symbol_id = getattr(c_sym, "id", None)

        # 1. Local Scope Resolution (self.method, this.method, or direct function name)
        # Check if caller has an enclosing class scope
        enclosing_class = None
        if caller_name and "." in caller_name:
            enclosing_class = caller_name.split(".")[0]

        # Case 1A: Method call on self/this within enclosing class (e.g. self.verify_password)
        if enclosing_class and (callee_full.startswith("self.") or callee_full.startswith("this.")):
            method_name = callee_attr or callee_full.split(".")[-1]
            target_sym = local_scoped.get((enclosing_class, method_name)) or local_symbols.get(method_name)
            if target_sym:
                return ResolvedCall(
                    caller_name=caller_name,
                    callee_name=callee_full,
                    caller_file_path=norm_fp,
                    callee_file_path=norm_fp,
                    line_number=call.line_number,
                    call_type="method_call",
                    resolution_status="resolved_internal",
                    confidence="verified",
                    caller_symbol_id=caller_symbol_id,
                    callee_symbol_id=getattr(target_sym, "id", None),
                    callee_symbol_name=getattr(target_sym, "name", method_name),
                    arguments=call.arguments,
                    evidence=call.evidence,
                )

        # Case 1B: Direct local function or class call (e.g. helper_func() or MyClass())
        if callee_full in local_symbols:
            target_sym = local_symbols[callee_full]
            return ResolvedCall(
                caller_name=caller_name,
                callee_name=callee_full,
                caller_file_path=norm_fp,
                callee_file_path=norm_fp,
                line_number=call.line_number,
                call_type=call.call_type,
                resolution_status="resolved_internal",
                confidence="verified",
                caller_symbol_id=caller_symbol_id,
                callee_symbol_id=getattr(target_sym, "id", None),
                callee_symbol_name=getattr(target_sym, "name", callee_full),
                arguments=call.arguments,
                evidence=call.evidence,
            )

        # 2. Cross-File Import Resolution
        # Look through imports in the current file
        for imp in file_imports:
            imp_source = getattr(imp, "source_module", "")
            imp_symbol = getattr(imp, "symbol_name", None)
            imp_alias = getattr(imp, "alias", None)

            # Determine if this import matches the callee expression
            matched_import = False
            target_symbol_to_find = None

            base_callee = callee_full.split(".")[0]
            if imp_alias and imp_alias == base_callee:
                matched_import = True
                target_symbol_to_find = callee_attr or imp_symbol
            elif imp_symbol and imp_symbol == base_callee:
                matched_import = True
                target_symbol_to_find = callee_attr if "." in callee_full else imp_symbol
            elif not imp_symbol and base_callee == imp_source.split(".")[-1]:
                # whole-module import, e.g. import utils -> utils.do_something()
                matched_import = True
                target_symbol_to_find = callee_attr or (callee_full.split(".")[1] if "." in callee_full else None)

            if matched_import:
                # Resolve target file path via ModuleResolver
                target_file, is_external = self.resolver.resolve_import(norm_fp, imp_source)
                if target_file and target_file in self._symbols_in_file:
                    target_file_symbols = self._symbols_in_file[target_file]
                    if target_symbol_to_find and target_symbol_to_find in target_file_symbols:
                        target_sym = target_file_symbols[target_symbol_to_find]
                        return ResolvedCall(
                            caller_name=caller_name,
                            callee_name=callee_full,
                            caller_file_path=norm_fp,
                            callee_file_path=target_file,
                            line_number=call.line_number,
                            call_type="cross_file_call",
                            resolution_status="resolved_internal",
                            confidence="verified",
                            caller_symbol_id=caller_symbol_id,
                            callee_symbol_id=getattr(target_sym, "id", None),
                            callee_symbol_name=getattr(target_sym, "name", target_symbol_to_find),
                            arguments=call.arguments,
                            evidence=call.evidence,
                        )
                    # If target symbol not explicitly matched, but target file is resolved
                    return ResolvedCall(
                        caller_name=caller_name,
                        callee_name=callee_full,
                        caller_file_path=norm_fp,
                        callee_file_path=target_file,
                        line_number=call.line_number,
                        call_type="cross_file_call",
                        resolution_status="resolved_internal",
                        confidence="inferred",
                        caller_symbol_id=caller_symbol_id,
                        callee_symbol_name=target_symbol_to_find or callee_full,
                        arguments=call.arguments,
                        evidence=call.evidence,
                    )
                elif is_external:
                    return ResolvedCall(
                        caller_name=caller_name,
                        callee_name=callee_full,
                        caller_file_path=norm_fp,
                        callee_file_path=f"external/{imp_source}",
                        line_number=call.line_number,
                        call_type="external",
                        resolution_status="external",
                        confidence="verified",
                        caller_symbol_id=caller_symbol_id,
                        arguments=call.arguments,
                        evidence=call.evidence,
                    )

        # 3. Known External Package / Standard Library Heuristic
        root_package = callee_full.split(".")[0].split("(")[0].strip()
        if root_package in self.KNOWN_EXTERNAL_PREFIXES:
            return ResolvedCall(
                caller_name=caller_name,
                callee_name=callee_full,
                caller_file_path=norm_fp,
                callee_file_path=f"external/{root_package}",
                line_number=call.line_number,
                call_type="external",
                resolution_status="external",
                confidence="verified",
                caller_symbol_id=caller_symbol_id,
                arguments=call.arguments,
                evidence=call.evidence,
            )

        # 4. Global Unique Symbol Heuristic Match
        # If callee_attr or callee_full matches a unique exported symbol anywhere in the repo
        search_name = callee_attr or callee_full
        candidates = self._global_symbols.get(search_name, [])
        if len(candidates) == 1:
            cand_fp, cand_sym = candidates[0]
            if cand_fp != norm_fp:
                return ResolvedCall(
                    caller_name=caller_name,
                    callee_name=callee_full,
                    caller_file_path=norm_fp,
                    callee_file_path=cand_fp,
                    line_number=call.line_number,
                    call_type="cross_file_call",
                    resolution_status="heuristic",
                    confidence="inferred",
                    caller_symbol_id=caller_symbol_id,
                    callee_symbol_id=getattr(cand_sym, "id", None),
                    callee_symbol_name=getattr(cand_sym, "name", search_name),
                    arguments=call.arguments,
                    evidence=call.evidence,
                )

        # 5. Unresolved / Dynamic Call
        return ResolvedCall(
            caller_name=caller_name,
            callee_name=callee_full,
            caller_file_path=norm_fp,
            callee_file_path=None,
            line_number=call.line_number,
            call_type=call.call_type,
            resolution_status="unresolved",
            confidence="unknown",
            caller_symbol_id=caller_symbol_id,
            arguments=call.arguments,
            evidence=call.evidence,
        )
