from pathlib import Path
from typing import Dict, Optional

from app.analysis.base import BaseCodeParser
from app.analysis.python_parser import PythonAstParser
from app.analysis.schemas import FileParseResult, ParseStatus
from app.analysis.treesitter_parser import TREE_SITTER_LANGUAGE_MAP, TreeSitterCodeParser


class UnsupportedLanguageParser(BaseCodeParser):
    """Fallback parser for languages without AST grammars."""

    def __init__(self, language: str) -> None:
        self._language = language

    @property
    def language_name(self) -> str:
        return self._language

    @property
    def parser_name(self) -> str:
        return "unsupported_parser"

    @property
    def parser_version(self) -> str:
        return "1.0.0"

    def parse_source(self, code: str, file_path: Optional[str] = None) -> FileParseResult:
        return FileParseResult(
            status=ParseStatus.UNSUPPORTED,
            language=self.language_name,
            parser_name=self.parser_name,
            parser_version=self.parser_version,
            symbols=[],
            imports_exports=[],
            endpoints=[],
            errors=[],
        )


class ParserRegistry:
    """Registry that resolves language and file metadata to the appropriate code parser."""

    _EXTENSION_MAP: Dict[str, str] = {
        ".py": "Python",
        ".pyw": "Python",
        ".js": "JavaScript",
        ".mjs": "JavaScript",
        ".cjs": "JavaScript",
        ".jsx": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".c": "C",
        ".h": "C",
        ".cpp": "C++",
        ".hpp": "C++",
        ".cc": "C++",
        ".cs": "C#",
        ".php": "PHP",
    }

    _cached_parsers: Dict[str, BaseCodeParser] = {}

    @classmethod
    def get_parser(
        cls,
        language: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> BaseCodeParser:
        # Determine language from file extension if not provided
        if not language and file_path:
            ext = Path(file_path).suffix.lower()
            language = cls._EXTENSION_MAP.get(ext)

        lang_key = (language or "unknown").strip()

        if lang_key in cls._cached_parsers:
            return cls._cached_parsers[lang_key]

        parser: BaseCodeParser
        if lang_key.lower() == "python":
            parser = PythonAstParser()
        elif lang_key in TREE_SITTER_LANGUAGE_MAP:
            parser = TreeSitterCodeParser(lang_key)
        else:
            parser = UnsupportedLanguageParser(lang_key)

        cls._cached_parsers[lang_key] = parser
        return parser

    @classmethod
    def is_language_supported(cls, language: str) -> bool:
        if language.lower() == "python":
            return True
        return language in TREE_SITTER_LANGUAGE_MAP

