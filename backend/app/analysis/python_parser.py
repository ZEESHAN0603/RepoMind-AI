import ast
import sys
from typing import Any, List, Optional, Set, Tuple

from app.analysis.base import BaseCodeParser
from app.analysis.schemas import (
    ConfidenceLevel,
    FileParseResult,
    ParsedEndpoint,
    ParsedImportExport,
    ParsedParameter,
    ParsedSymbol,
    ParserError,
    ParseStatus,
    SymbolType,
)


class PythonAstParser(BaseCodeParser):
    """Production-grade Python parser using standard library AST."""

    @property
    def language_name(self) -> str:
        return "Python"

    @property
    def parser_name(self) -> str:
        return "python_ast"

    @property
    def parser_version(self) -> str:
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    def parse_source(self, code: str, file_path: Optional[str] = None) -> FileParseResult:
        if not code.strip():
            return FileParseResult(
                status=ParseStatus.SUCCESS,
                language=self.language_name,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                symbols=[],
                imports_exports=[],
                endpoints=[],
                errors=[],
            )

        try:
            tree = ast.parse(code, filename=file_path or "<string>")
        except SyntaxError as se:
            return FileParseResult(
                status=ParseStatus.FAILED,
                language=self.language_name,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                symbols=[],
                imports_exports=[],
                endpoints=[],
                errors=[
                    ParserError(
                        message=se.msg or "Syntax error during parsing",
                        line=se.lineno,
                        column=se.offset,
                        error_type="SyntaxError",
                    )
                ],
            )
        except Exception as ex:
            return FileParseResult(
                status=ParseStatus.FAILED,
                language=self.language_name,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                symbols=[],
                imports_exports=[],
                endpoints=[],
                errors=[ParserError(message=str(ex), error_type=type(ex).__name__)],
            )

        symbols: List[ParsedSymbol] = []
        imports_exports: List[ParsedImportExport] = []
        endpoints: List[ParsedEndpoint] = []
        errors: List[ParserError] = []

        # Find explicit __all__ exports if defined
        exported_names: Set[str] = self._extract_all_exports(tree)

        # Traverse AST nodes
        self._traverse_node(
            node=tree,
            scope=None,
            symbols=symbols,
            imports_exports=imports_exports,
            endpoints=endpoints,
            exported_names=exported_names,
        )

        return FileParseResult(
            status=ParseStatus.SUCCESS,
            language=self.language_name,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            symbols=symbols,
            imports_exports=imports_exports,
            endpoints=endpoints,
            errors=errors,
        )

    def _traverse_node(
        self,
        node: ast.AST,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        imports_exports: List[ParsedImportExport],
        endpoints: List[ParsedEndpoint],
        exported_names: Set[str],
    ) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef) or isinstance(child, ast.AsyncFunctionDef):
                self._process_function(
                    child,
                    scope=scope,
                    symbols=symbols,
                    endpoints=endpoints,
                    exported_names=exported_names,
                )
            elif isinstance(child, ast.ClassDef):
                self._process_class(
                    child,
                    scope=scope,
                    symbols=symbols,
                    imports_exports=imports_exports,
                    endpoints=endpoints,
                    exported_names=exported_names,
                )
            elif isinstance(child, (ast.Import, ast.ImportFrom)):
                self._process_import(child, imports_exports)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                self._process_type_alias_or_variable(child, scope, symbols)
            else:
                # Recurse for blocks (if, with, try, etc.)
                if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self._traverse_node(
                        child,
                        scope=scope,
                        symbols=symbols,
                        imports_exports=imports_exports,
                        endpoints=endpoints,
                        exported_names=exported_names,
                    )

    def _process_function(
        self,
        node: Any,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        endpoints: List[ParsedEndpoint],
        exported_names: Set[str],
    ) -> None:
        is_async = isinstance(node, ast.AsyncFunctionDef)
        is_method = scope is not None
        symbol_type = SymbolType.METHOD if is_method else SymbolType.FUNCTION

        # Check visibility
        name = node.name
        visibility = "private" if name.startswith("__") and not name.endswith("__") else (
            "protected" if name.startswith("_") else "public"
        )
        is_exported = (name in exported_names) or (visibility == "public" and not is_method)

        # Detect generator
        is_generator = any(
            isinstance(sub, (ast.Yield, ast.YieldFrom)) for sub in ast.walk(node)
        )

        # Extract parameters
        parameters: List[ParsedParameter] = []
        pos_args = node.args.posonlyargs + node.args.args
        defaults_offset = len(pos_args) - len(node.args.defaults)

        for i, arg in enumerate(pos_args):
            default_val = None
            if i >= defaults_offset:
                def_idx = i - defaults_offset
                if def_idx < len(node.args.defaults):
                    default_val = self._unparse_safe(node.args.defaults[def_idx])

            ann = self._unparse_safe(arg.annotation) if arg.annotation else None
            parameters.append(
                ParsedParameter(
                    name=arg.arg,
                    type_annotation=ann,
                    default_value=default_val,
                    is_optional=(default_val is not None and default_val == "None"),
                    is_variadic=False,
                    is_kwarg=False,
                )
            )

        if node.args.vararg:
            parameters.append(
                ParsedParameter(
                    name=f"*{node.args.vararg.arg}",
                    type_annotation=self._unparse_safe(node.args.vararg.annotation) if node.args.vararg.annotation else None,
                    is_variadic=True,
                )
            )

        for i, kwarg in enumerate(node.args.kwonlyargs):
            kw_default = None
            if i < len(node.args.kw_defaults) and node.args.kw_defaults[i] is not None:
                kw_default = self._unparse_safe(node.args.kw_defaults[i])

            parameters.append(
                ParsedParameter(
                    name=kwarg.arg,
                    type_annotation=self._unparse_safe(kwarg.annotation) if kwarg.annotation else None,
                    default_value=kw_default,
                    is_optional=(kw_default is not None and kw_default == "None"),
                )
            )

        if node.args.kwarg:
            parameters.append(
                ParsedParameter(
                    name=f"**{node.args.kwarg.arg}",
                    type_annotation=self._unparse_safe(node.args.kwarg.annotation) if node.args.kwarg.annotation else None,
                    is_kwarg=True,
                )
            )

        # Return type
        return_type = self._unparse_safe(node.returns) if node.returns else None

        # Decorators
        decorators = [self._unparse_safe(d) for d in node.decorator_list]

        # Reconstructed signature
        async_str = "async " if is_async else ""
        params_str = ", ".join(
            f"{p.name}" + (f": {p.type_annotation}" if p.type_annotation else "") +
            (f" = {p.default_value}" if p.default_value is not None else "")
            for p in parameters
        )
        return_str = f" -> {return_type}" if return_type else ""
        signature = f"{async_str}def {name}({params_str}){return_str}"

        # Docstring
        docstring = ast.get_docstring(node)

        # End line fallback
        end_line = getattr(node, "end_lineno", node.lineno)
        end_col = getattr(node, "end_col_offset", None)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=symbol_type,
                start_line=node.lineno,
                end_line=end_line,
                start_column=node.col_offset,
                end_column=end_col,
                scope=scope,
                signature=signature,
                docstring=docstring,
                is_async=is_async,
                is_generator=is_generator,
                is_exported=is_exported,
                visibility=visibility,
                parameters=parameters,
                return_type=return_type,
                decorators=decorators,
                bases_or_interfaces=[],
                confidence=ConfidenceLevel.VERIFIED,
            )
        )

        # API Route Detection
        self._check_api_endpoint(node, decorators, endpoints)

        # Recurse for nested functions or inner classes
        inner_scope = f"{scope}.{name}" if scope else name
        for sub in node.body:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_function(
                    sub,
                    scope=inner_scope,
                    symbols=symbols,
                    endpoints=endpoints,
                    exported_names=exported_names,
                )
            elif isinstance(sub, ast.ClassDef):
                self._process_class(
                    sub,
                    scope=inner_scope,
                    symbols=symbols,
                    imports_exports=[],
                    endpoints=endpoints,
                    exported_names=exported_names,
                )

    def _process_class(
        self,
        node: ast.ClassDef,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        imports_exports: List[ParsedImportExport],
        endpoints: List[ParsedEndpoint],
        exported_names: Set[str],
    ) -> None:
        name = node.name
        visibility = "private" if name.startswith("__") and not name.endswith("__") else (
            "protected" if name.startswith("_") else "public"
        )
        is_exported = (name in exported_names) or (visibility == "public" and scope is None)

        bases = [self._unparse_safe(b) for b in node.bases]
        decorators = [self._unparse_safe(d) for d in node.decorator_list]
        docstring = ast.get_docstring(node)

        bases_str = f"({', '.join(bases)})" if bases else ""
        signature = f"class {name}{bases_str}"

        end_line = getattr(node, "end_lineno", node.lineno)
        end_col = getattr(node, "end_col_offset", None)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=SymbolType.CLASS,
                start_line=node.lineno,
                end_line=end_line,
                start_column=node.col_offset,
                end_column=end_col,
                scope=scope,
                signature=signature,
                docstring=docstring,
                is_exported=is_exported,
                visibility=visibility,
                decorators=decorators,
                bases_or_interfaces=bases,
                confidence=ConfidenceLevel.VERIFIED,
            )
        )

        # Traverse class body for methods and nested classes
        class_scope = f"{scope}.{name}" if scope else name
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._process_function(
                    item,
                    scope=class_scope,
                    symbols=symbols,
                    endpoints=endpoints,
                    exported_names=exported_names,
                )
            elif isinstance(item, ast.ClassDef):
                self._process_class(
                    item,
                    scope=class_scope,
                    symbols=symbols,
                    imports_exports=imports_exports,
                    endpoints=endpoints,
                    exported_names=exported_names,
                )

    def _process_import(self, node: Any, imports_exports: List[ParsedImportExport]) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports_exports.append(
                    ParsedImportExport(
                        statement_type="import",
                        source_module=alias.name,
                        symbol_name=None,
                        alias=alias.asname,
                        is_relative=False,
                        is_default=False,
                        line_number=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            is_relative = (node.level or 0) > 0
            if is_relative:
                module_name = ("." * (node.level or 0)) + module_name

            for alias in node.names:
                imports_exports.append(
                    ParsedImportExport(
                        statement_type="import",
                        source_module=module_name,
                        symbol_name=alias.name,
                        alias=alias.asname,
                        is_relative=is_relative,
                        is_default=False,
                        line_number=node.lineno,
                    )
                )

    def _process_type_alias_or_variable(
        self,
        node: Any,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
    ) -> None:
        # Check for TypeAlias annotations or Union/Type expressions
        # e.g.: UserId = int or UserId: TypeAlias = int
        if isinstance(node, ast.AnnAssign):
            target_name = self._unparse_safe(node.target)
            ann = self._unparse_safe(node.annotation)
            if "TypeAlias" in ann or (node.value and any(t in ann for t in ("Union", "Optional", "Literal", "Callable"))):
                val_str = self._unparse_safe(node.value) if node.value else ann
                symbols.append(
                    ParsedSymbol(
                        name=target_name,
                        symbol_type=SymbolType.TYPE_ALIAS,
                        start_line=node.lineno,
                        end_line=getattr(node, "end_lineno", node.lineno),
                        start_column=node.col_offset,
                        end_column=getattr(node, "end_col_offset", None),
                        scope=scope,
                        signature=f"{target_name}: TypeAlias = {val_str}",
                        confidence=ConfidenceLevel.VERIFIED,
                    )
                )

    def _check_api_endpoint(
        self,
        node: Any,
        decorators: List[str],
        endpoints: List[ParsedEndpoint],
    ) -> None:
        """Inspects function decorators for FastAPI/Flask route patterns."""
        http_methods = {"get", "post", "put", "delete", "patch", "options", "head", "api_route"}
        for dec in node.decorator_list:
            if isinstance(dec, ast.Call):
                func = dec.func
                method_name = None
                framework = "Unknown"

                # Check router.get("/path") or app.post("/path")
                if isinstance(func, ast.Attribute):
                    attr_lower = func.attr.lower()
                    if attr_lower in http_methods:
                        method_name = attr_lower.upper()
                        framework = "FastAPI"
                        if attr_lower == "route":
                            framework = "Flask"

                # Extract path argument (first positional arg)
                path = "/"
                if dec.args:
                    first_arg = dec.args[0]
                    if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                        path = first_arg.value

                # Check methods keyword arg in Flask: @app.route('/path', methods=['GET', 'POST'])
                for kw in dec.keywords:
                    if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                        methods_found = [
                            m.value.upper() for m in kw.value.elts
                            if isinstance(m, ast.Constant) and isinstance(m.value, str)
                        ]
                        for m in methods_found:
                            endpoints.append(
                                ParsedEndpoint(
                                    http_method=m,
                                    path=path,
                                    handler_name=node.name,
                                    framework="Flask",
                                    start_line=node.lineno,
                                    end_line=getattr(node, "end_lineno", node.lineno),
                                    confidence=ConfidenceLevel.VERIFIED,
                                )
                            )
                        return

                if method_name:
                    endpoints.append(
                        ParsedEndpoint(
                            http_method=method_name if method_name != "API_ROUTE" else "ANY",
                            path=path,
                            handler_name=node.name,
                            framework=framework,
                            start_line=node.lineno,
                            end_line=getattr(node, "end_lineno", node.lineno),
                            confidence=ConfidenceLevel.VERIFIED,
                        )
                    )

    def _extract_all_exports(self, tree: ast.AST) -> Set[str]:
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                            return {
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            }
        return set()

    @staticmethod
    def _unparse_safe(node: Optional[ast.AST]) -> str:
        if node is None:
            return ""
        try:
            return ast.unparse(node)
        except Exception:
            return ""

