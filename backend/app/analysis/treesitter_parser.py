from typing import Any, Dict, List, Optional, Set, Tuple
import tree_sitter_languages

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

# Supported language mappings to tree-sitter language names
TREE_SITTER_LANGUAGE_MAP = {
    "JavaScript": "javascript",
    "TypeScript": "typescript",
    "Java": "java",
    "Go": "go",
    "C": "c",
    "C++": "cpp",
    "C#": "c_sharp",
    "Rust": "rust",
    "PHP": "php",
}


class TreeSitterCodeParser(BaseCodeParser):
    """Multi-language parser adapter powered by Tree-sitter."""

    def __init__(self, language: str) -> None:
        self._language = language
        self._ts_lang_name = TREE_SITTER_LANGUAGE_MAP.get(language, language.lower())
        try:
            self._parser = tree_sitter_languages.get_parser(self._ts_lang_name)
        except Exception:
            self._parser = None

    @property
    def language_name(self) -> str:
        return self._language

    @property
    def parser_name(self) -> str:
        return "tree_sitter"

    @property
    def parser_version(self) -> str:
        return "0.21.3"

    def parse_source(self, code: str, file_path: Optional[str] = None) -> FileParseResult:
        if not self._parser:
            return FileParseResult(
                status=ParseStatus.UNSUPPORTED,
                language=self.language_name,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                errors=[ParserError(message=f"Tree-sitter grammar for {self.language_name} not available")],
            )

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
            source_bytes = code.encode("utf-8")
            tree = self._parser.parse(source_bytes)
        except Exception as ex:
            return FileParseResult(
                status=ParseStatus.FAILED,
                language=self.language_name,
                parser_name=self.parser_name,
                parser_version=self.parser_version,
                errors=[ParserError(message=f"Failed to parse source: {ex}", error_type=type(ex).__name__)],
            )

        symbols: List[ParsedSymbol] = []
        imports_exports: List[ParsedImportExport] = []
        endpoints: List[ParsedEndpoint] = []
        errors: List[ParserError] = []

        root_node = tree.root_node
        has_errors = self._collect_errors(root_node, errors)

        self._walk_node(
            node=root_node,
            source_bytes=source_bytes,
            scope=None,
            symbols=symbols,
            imports_exports=imports_exports,
            endpoints=endpoints,
        )

        status = ParseStatus.PARTIAL if (has_errors and (symbols or imports_exports)) else (
            ParseStatus.FAILED if has_errors and not symbols and not imports_exports else ParseStatus.SUCCESS
        )

        return FileParseResult(
            status=status,
            language=self.language_name,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            symbols=symbols,
            imports_exports=imports_exports,
            endpoints=endpoints,
            errors=errors,
        )

    def _collect_errors(self, node: Any, errors: List[ParserError]) -> bool:
        found_error = False
        if node.type == "ERROR" or node.is_missing:
            errors.append(
                ParserError(
                    message=f"Syntax parsing error at line {node.start_point[0] + 1}, column {node.start_point[1]}",
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    error_type="SyntaxError",
                )
            )
            found_error = True

        for child in node.children:
            if self._collect_errors(child, errors):
                found_error = True

        return found_error

    def _walk_node(
        self,
        node: Any,
        source_bytes: bytes,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        imports_exports: List[ParsedImportExport],
        endpoints: List[ParsedEndpoint],
    ) -> None:
        node_type = node.type

        # Function declarations
        if node_type in (
            "function_declaration",
            "function_definition",
            "method_definition",
            "method_declaration",
            "function_item",  # Rust
        ):
            self._handle_function_node(node, source_bytes, scope, symbols, endpoints)
            return

        # Arrow functions or function expressions assigned to variables
        # const myFn = () => { ... }
        elif node_type in ("lexical_declaration", "variable_declaration"):
            self._handle_variable_declaration(node, source_bytes, scope, symbols)
            return

        # Classes and interfaces
        elif node_type in (
            "class_declaration",
            "class_definition",
            "interface_declaration",
            "struct_specifier",
            "type_declaration",
            "enum_declaration",
        ):
            self._handle_class_or_interface(node, source_bytes, scope, symbols, imports_exports, endpoints)
            return

        # Imports & Exports
        elif node_type in (
            "import_statement",
            "import_declaration",
            "package_clause",
            "use_declaration",
        ):
            self._handle_import(node, source_bytes, imports_exports)
            return
        elif node_type in ("export_statement", "export_declaration"):
            self._handle_export(node, source_bytes, imports_exports, symbols, endpoints)
            return

        # API endpoint detection: Express routing calls app.get(...), router.post(...)
        elif node_type == "call_expression":
            self._check_express_endpoint(node, source_bytes, endpoints)

        # Recurse children for general blocks
        for child in node.children:
            self._walk_node(
                node=child,
                source_bytes=source_bytes,
                scope=scope,
                symbols=symbols,
                imports_exports=imports_exports,
                endpoints=endpoints,
            )

    def _handle_function_node(
        self,
        node: Any,
        source_bytes: bytes,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        endpoints: List[ParsedEndpoint],
    ) -> None:
        name_node = node.child_by_field_name("name")
        name = self._node_text(name_node, source_bytes) if name_node else "anonymous"

        is_method = scope is not None or node.type in ("method_definition", "method_declaration")
        symbol_type = SymbolType.METHOD if is_method else SymbolType.FUNCTION

        # Parameters
        params_node = node.child_by_field_name("parameters")
        parameters = self._extract_parameters(params_node, source_bytes)

        # Return type
        return_type_node = node.child_by_field_name("return_type") or node.child_by_field_name("type")
        return_type = self._node_text(return_type_node, source_bytes) if return_type_node else None

        # Check async
        is_async = any(c.type == "async" for c in node.children)

        # Line/cols
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        start_col = node.start_point[1]
        end_col = node.end_point[1]

        # Signature
        sig_text = self._get_first_line(node, source_bytes)

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=symbol_type,
                start_line=start_line,
                end_line=end_line,
                start_column=start_col,
                end_column=end_col,
                scope=scope,
                signature=sig_text or f"function {name}()",
                docstring=None,
                is_async=is_async,
                is_exported=False,
                parameters=parameters,
                return_type=return_type,
                confidence=ConfidenceLevel.VERIFIED,
            )
        )

        # Check for Spring Boot controller annotations or similar
        self._check_java_endpoint(node, source_bytes, name, endpoints)

        # Recurse inside function body for nested functions
        body_node = node.child_by_field_name("body")
        if body_node:
            fn_scope = f"{scope}.{name}" if scope else name
            for child in body_node.children:
                self._walk_node(child, source_bytes, fn_scope, symbols, [], endpoints)

    def _handle_variable_declaration(
        self,
        node: Any,
        source_bytes: bytes,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
    ) -> None:
        # Matches: const myFunc = (x: number) => { ... }
        for child in node.children:
            if child.type in ("variable_declarator", "lexical_declarator"):
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function_expression"):
                    name = self._node_text(name_node, source_bytes)
                    params_node = value_node.child_by_field_name("parameters")
                    params = self._extract_parameters(params_node, source_bytes)
                    ret_node = value_node.child_by_field_name("return_type")
                    ret_type = self._node_text(ret_node, source_bytes) if ret_node else None
                    is_async = any(c.type == "async" for c in value_node.children)

                    symbols.append(
                        ParsedSymbol(
                            name=name,
                            symbol_type=SymbolType.FUNCTION,
                            start_line=node.start_point[0] + 1,
                            end_line=node.end_point[0] + 1,
                            start_column=node.start_point[1],
                            end_column=node.end_point[1],
                            scope=scope,
                            signature=self._get_first_line(node, source_bytes),
                            is_async=is_async,
                            parameters=params,
                            return_type=ret_type,
                            confidence=ConfidenceLevel.VERIFIED,
                        )
                    )

    def _handle_class_or_interface(
        self,
        node: Any,
        source_bytes: bytes,
        scope: Optional[str],
        symbols: List[ParsedSymbol],
        imports_exports: List[ParsedImportExport],
        endpoints: List[ParsedEndpoint],
    ) -> None:
        name_node = node.child_by_field_name("name")
        name = self._node_text(name_node, source_bytes) if name_node else "AnonymousClass"

        sym_type = SymbolType.CLASS
        if "interface" in node.type:
            sym_type = SymbolType.INTERFACE
        elif "enum" in node.type:
            sym_type = SymbolType.ENUM
        elif "struct" in node.type:
            sym_type = SymbolType.STRUCT

        # Extract bases / heritage
        bases: List[str] = []
        for child in node.children:
            if child.type in ("class_heritage", "extends_clause", "implements_clause", "super_class"):
                bases.append(self._node_text(child, source_bytes))

        symbols.append(
            ParsedSymbol(
                name=name,
                symbol_type=sym_type,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                start_column=node.start_point[1],
                end_column=node.end_point[1],
                scope=scope,
                signature=self._get_first_line(node, source_bytes),
                bases_or_interfaces=bases,
                confidence=ConfidenceLevel.VERIFIED,
            )
        )

        # Walk class body
        body_node = node.child_by_field_name("body")
        if body_node:
            class_scope = f"{scope}.{name}" if scope else name
            for child in body_node.children:
                self._walk_node(child, source_bytes, class_scope, symbols, imports_exports, endpoints)

    def _handle_import(
        self,
        node: Any,
        source_bytes: bytes,
        imports_exports: List[ParsedImportExport],
    ) -> None:
        source_node = node.child_by_field_name("source")
        module_path = self._node_text(source_node, source_bytes).strip("\"'") if source_node else ""

        line_num = node.start_point[0] + 1
        is_rel = module_path.startswith(".")

        # Extract imported symbols if available
        imports_exports.append(
            ParsedImportExport(
                statement_type="import",
                source_module=module_path,
                symbol_name=None,
                is_relative=is_rel,
                line_number=line_num,
            )
        )

    def _handle_export(
        self,
        node: Any,
        source_bytes: bytes,
        imports_exports: List[ParsedImportExport],
        symbols: List[ParsedSymbol],
        endpoints: List[ParsedEndpoint],
    ) -> None:
        line_num = node.start_point[0] + 1
        decl_node = node.child_by_field_name("declaration")
        start_count = len(symbols)
        if decl_node:
            self._walk_node(decl_node, source_bytes, None, symbols, imports_exports, endpoints)
            for i in range(start_count, len(symbols)):
                symbols[i].is_exported = True

        imports_exports.append(
            ParsedImportExport(
                statement_type="export",
                source_module="",
                symbol_name=self._get_first_line(node, source_bytes),
                line_number=line_num,
            )
        )

    def _check_express_endpoint(
        self,
        node: Any,
        source_bytes: bytes,
        endpoints: List[ParsedEndpoint],
    ) -> None:
        # Express route call: app.get('/users', (req, res) => ...)
        fn_node = node.child_by_field_name("function")
        if fn_node and fn_node.type == "member_expression":
            prop_node = fn_node.child_by_field_name("property")
            if prop_node:
                method_name = self._node_text(prop_node, source_bytes).lower()
                if method_name in ("get", "post", "put", "delete", "patch", "all", "use"):
                    args_node = node.child_by_field_name("arguments")
                    if args_node and len(args_node.children) > 1:
                        first_arg = args_node.children[1]  # index 1 after '('
                        if first_arg.type == "string":
                            path_val = self._node_text(first_arg, source_bytes).strip("\"'")
                            endpoints.append(
                                ParsedEndpoint(
                                    http_method=method_name.upper() if method_name != "all" else "ANY",
                                    path=path_val,
                                    handler_name="express_route_handler",
                                    framework="Express",
                                    start_line=node.start_point[0] + 1,
                                    end_line=node.end_point[0] + 1,
                                    confidence=ConfidenceLevel.VERIFIED,
                                )
                            )

    def _check_java_endpoint(
        self,
        node: Any,
        source_bytes: bytes,
        handler_name: str,
        endpoints: List[ParsedEndpoint],
    ) -> None:
        """Checks for Spring Boot annotations (@GetMapping, @PostMapping, etc.) in Java method nodes."""
        for child in node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type == "annotation":
                        name_node = mod.child_by_field_name("name")
                        ann_name = self._node_text(name_node, source_bytes) if name_node else ""
                        method_map = {
                            "GetMapping": "GET",
                            "PostMapping": "POST",
                            "PutMapping": "PUT",
                            "DeleteMapping": "DELETE",
                            "PatchMapping": "PATCH",
                            "RequestMapping": "ANY",
                        }
                        if ann_name in method_map:
                            arg_node = mod.child_by_field_name("arguments")
                            path_val = "/"
                            if arg_node:
                                path_val = self._node_text(arg_node, source_bytes).strip("()\"' ")

                            endpoints.append(
                                ParsedEndpoint(
                                    http_method=method_map[ann_name],
                                    path=path_val,
                                    handler_name=handler_name,
                                    framework="Spring Boot",
                                    start_line=node.start_point[0] + 1,
                                    end_line=node.end_point[0] + 1,
                                    confidence=ConfidenceLevel.VERIFIED,
                                )
                            )

    def _extract_parameters(self, params_node: Any, source_bytes: bytes) -> List[ParsedParameter]:
        params: List[ParsedParameter] = []
        if not params_node:
            return params

        for child in params_node.children:
            if child.type in ("identifier", "required_parameter", "optional_parameter", "formal_parameter"):
                p_name_node = child.child_by_field_name("name") or child
                p_type_node = child.child_by_field_name("type")
                p_name = self._node_text(p_name_node, source_bytes)
                p_type = self._node_text(p_type_node, source_bytes) if p_type_node else None
                if p_name not in ("(", ")", ","):
                    params.append(
                        ParsedParameter(
                            name=p_name,
                            type_annotation=p_type,
                            is_optional="?" in p_name or child.type == "optional_parameter",
                        )
                    )
        return params

    @staticmethod
    def _node_text(node: Optional[Any], source_bytes: bytes) -> str:
        if not node:
            return ""
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    @classmethod
    def _get_first_line(cls, node: Any, source_bytes: bytes) -> str:
        full_text = cls._node_text(node, source_bytes)
        first_line = full_text.splitlines()[0] if full_text else ""
        return first_line.strip()
