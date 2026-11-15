from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ParseStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    SKIPPED = "skipped"


class SymbolType(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"
    STRUCT = "struct"


class ConfidenceLevel(str, Enum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


@dataclass
class ParsedParameter:
    name: str
    type_annotation: Optional[str] = None
    default_value: Optional[str] = None
    is_optional: bool = False
    is_variadic: bool = False
    is_kwarg: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type_annotation": self.type_annotation,
            "default_value": self.default_value,
            "is_optional": self.is_optional,
            "is_variadic": self.is_variadic,
            "is_kwarg": self.is_kwarg,
        }


@dataclass
class ParsedSymbol:
    name: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    start_column: Optional[int] = None
    end_column: Optional[int] = None
    scope: Optional[str] = None  # Enclosing class or function name
    signature: str = ""
    docstring: Optional[str] = None
    is_async: bool = False
    is_generator: bool = False
    is_exported: bool = False
    visibility: str = "public"  # public, protected, private
    parameters: List[ParsedParameter] = field(default_factory=list)
    return_type: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    bases_or_interfaces: List[str] = field(default_factory=list)
    confidence: ConfidenceLevel = ConfidenceLevel.VERIFIED


@dataclass
class ParsedImportExport:
    statement_type: str  # "import" or "export"
    source_module: str
    symbol_name: Optional[str] = None  # None for whole-module import or export default
    alias: Optional[str] = None
    is_relative: bool = False
    is_default: bool = False
    line_number: int = 1


@dataclass
class ParsedEndpoint:
    http_method: str  # GET, POST, PUT, DELETE, PATCH, etc.
    path: str
    handler_name: str
    framework: str  # FastAPI, Flask, Express, NestJS, Spring Boot
    start_line: int
    end_line: int
    confidence: ConfidenceLevel = ConfidenceLevel.VERIFIED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParserError:
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    error_type: str = "SyntaxError"


@dataclass
class FileParseResult:
    status: ParseStatus
    language: str
    parser_name: str
    parser_version: str
    symbols: List[ParsedSymbol] = field(default_factory=list)
    imports_exports: List[ParsedImportExport] = field(default_factory=list)
    endpoints: List[ParsedEndpoint] = field(default_factory=list)
    errors: List[ParserError] = field(default_factory=list)

