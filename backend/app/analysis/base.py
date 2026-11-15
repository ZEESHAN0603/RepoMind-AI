from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from app.analysis.schemas import FileParseResult


class BaseCodeParser(ABC):
    """Abstract base class for all language-specific code parsers."""

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Name of the programming language handled by this parser."""
        pass

    @property
    @abstractmethod
    def parser_name(self) -> str:
        """Identifier of the parser engine (e.g. 'python_ast', 'tree_sitter')."""
        pass

    @property
    @abstractmethod
    def parser_version(self) -> str:
        """Version string of the parser engine."""
        pass

    @abstractmethod
    def parse_source(self, code: str, file_path: Optional[str] = None) -> FileParseResult:
        """
        Parses source code text and extracts structured symbols, imports/exports, and endpoints.
        Must never raise uncaught exceptions; errors should be captured in FileParseResult.errors.
        """
        pass

