from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile
from app.repositories.code_intelligence_repository import CodeIntelligenceRepository
from app.repositories.file_repository import FileRepository
from app.services.workspace_service import WorkspaceService

# Configurable chunking constants
MAX_CHUNK_CHARS = 1600      # ~400 tokens max per chunk
CHUNK_OVERLAP_CHARS = 200   # Overlap for split large symbols or windowed files
MIN_CHUNK_CHARS = 40        # Skip trivial single-line whitespace chunks

EXCLUDED_FILENAMES: Set[str] = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.staging",
    ".env.example",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lock",
    "bun.lockb",
    "poetry.lock",
    "Cargo.lock",
}

EXCLUDED_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf", ".exe", ".dll", ".so", ".dylib",
    ".pyc", ".pyo", ".pyd",
    ".min.js", ".min.css", ".map",
}


@dataclass
class CodeChunkData:
    chunk_index: int
    file_id: str
    file_path: str
    symbol_id: Optional[str]
    symbol_name: Optional[str]
    symbol_type: Optional[str]
    scope: Optional[str]
    chunk_type: str  # "symbol", "file_section", "manifest", "overview"
    content: str
    start_line: int
    end_line: int
    token_count: int
    language: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChunkingService:
    """
    Produces repository-aware, syntax-grounded code chunks leveraging
    Phase 4 AST code symbols, imports, and file hierarchies.
    """

    def __init__(self, workspace_service: Optional[WorkspaceService] = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    def should_index_file(self, file_entity: RepositoryFile) -> bool:
        """Determines if a file should be indexed, excluding binaries, secrets, and lockfiles."""
        if file_entity.file_type != "file" or file_entity.is_binary:
            return False

        path_obj = Path(file_entity.path)
        filename = path_obj.name.lower()

        if filename in EXCLUDED_FILENAMES or filename.startswith(".env"):
            return False

        ext = path_obj.suffix.lower()
        if ext in EXCLUDED_EXTENSIONS:
            return False

        # Exclude common test snapshot or coverage files
        if "coverage/" in file_entity.path or ".pytest_cache/" in file_entity.path:
            return False

        return True

    def _estimate_tokens(self, text: str) -> int:
        """Approximates token count (avg 4 chars per token)."""
        return max(1, len(text) // 4)

    def _format_chunk_content(
        self,
        file_path: str,
        start_line: int,
        end_line: int,
        raw_code: str,
        symbol_name: Optional[str] = None,
        symbol_type: Optional[str] = None,
        scope: Optional[str] = None,
        imports_summary: Optional[str] = None,
    ) -> str:
        """Builds a contextual header for the chunk to ground retrieval and citation."""
        header_parts = [f"# File: {file_path}", f"Lines: {start_line}-{end_line}"]
        if symbol_name:
            header_parts.append(f"{symbol_type or 'Symbol'}: {symbol_name}")
        if scope:
            header_parts.append(f"Scope: {scope}")

        header = " | ".join(header_parts)
        sections = [header]
        if imports_summary:
            sections.append(f"# Contextual Imports: {imports_summary}")

        sections.append(raw_code.strip())
        return "\n".join(sections)

    async def generate_chunks_for_repository(
        self,
        session: AsyncSession,
        repository_id: str,
        user_id: str,
    ) -> List[CodeChunkData]:
        """
        Extracts chunks for all eligible files in the repository using
        Phase 4 CodeSymbol records, imports, and file contents.
        """
        file_repo = FileRepository(session)
        ci_repo = CodeIntelligenceRepository(session)

        workspace_path = self.workspace_service.get_repository_workspace_path(user_id, repository_id)
        all_files = await file_repo.list_files_by_repo(repository_id)

        chunks: List[CodeChunkData] = []
        global_chunk_idx = 0

        for file_entity in all_files:
            if not self.should_index_file(file_entity):
                continue

            file_disk_path = workspace_path / file_entity.path
            if not file_disk_path.is_file():
                continue

            try:
                with open(file_disk_path, "r", encoding="utf-8", errors="replace") as f:
                    file_text = f.read()
            except Exception as e:
                logger.warning("Could not read file %s for chunking: %s", file_entity.path, e)
                continue

            file_lines = file_text.splitlines()
            total_lines = len(file_lines)
            if total_lines == 0 or len(file_text.strip()) < MIN_CHUNK_CHARS:
                continue

            # Retrieve Phase 4 extracted symbols and imports for this file
            symbols = await ci_repo.list_symbols_by_file(file_entity.id)
            imports = await ci_repo.list_imports_exports_by_repo(repository_id)
            file_imports = [
                i.source_module for i in imports
                if i.file_id == file_entity.id and i.statement_type == "import"
            ]
            imports_summary = ", ".join(file_imports[:5]) if file_imports else None

            # Case A: File contains recognized Phase 4 code symbols
            if symbols:
                covered_line_ranges: List[tuple] = []

                for sym in symbols:
                    start_l = max(1, sym.start_line)
                    end_l = min(total_lines, sym.end_line)
                    symbol_lines = file_lines[start_l - 1:end_l]
                    symbol_code = "\n".join(symbol_lines)
                    covered_line_ranges.append((start_l, end_l))

                    if not symbol_code.strip():
                        continue

                    # If symbol fits in one bounded chunk
                    if len(symbol_code) <= MAX_CHUNK_CHARS:
                        content = self._format_chunk_content(
                            file_path=file_entity.path,
                            start_line=start_l,
                            end_line=end_l,
                            raw_code=symbol_code,
                            symbol_name=sym.name,
                            symbol_type=sym.symbol_type,
                            scope=sym.scope,
                            imports_summary=imports_summary,
                        )
                        chunks.append(
                            CodeChunkData(
                                chunk_index=global_chunk_idx,
                                file_id=file_entity.id,
                                file_path=file_entity.path,
                                symbol_id=sym.id,
                                symbol_name=sym.name,
                                symbol_type=sym.symbol_type,
                                scope=sym.scope,
                                chunk_type="symbol",
                                content=content,
                                start_line=start_l,
                                end_line=end_l,
                                token_count=self._estimate_tokens(content),
                                language=file_entity.language,
                                metadata={
                                    "is_async": sym.is_async,
                                    "visibility": sym.visibility,
                                    "confidence": sym.confidence,
                                },
                            )
                        )
                        global_chunk_idx += 1
                    else:
                        # Split very large symbol into overlapping line windows
                        chunk_step = max(20, (MAX_CHUNK_CHARS // 60))
                        overlap = 5
                        cur_idx = 0

                        while cur_idx < len(symbol_lines):
                            window_lines = symbol_lines[cur_idx:cur_idx + chunk_step]
                            sub_start = start_l + cur_idx
                            sub_end = min(end_l, sub_start + len(window_lines) - 1)
                            sub_code = "\n".join(window_lines)

                            content = self._format_chunk_content(
                                file_path=file_entity.path,
                                start_line=sub_start,
                                end_line=sub_end,
                                raw_code=sub_code,
                                symbol_name=f"{sym.name} (part)",
                                symbol_type=sym.symbol_type,
                                scope=sym.scope,
                                imports_summary=imports_summary,
                            )
                            chunks.append(
                                CodeChunkData(
                                    chunk_index=global_chunk_idx,
                                    file_id=file_entity.id,
                                    file_path=file_entity.path,
                                    symbol_id=sym.id,
                                    symbol_name=sym.name,
                                    symbol_type=sym.symbol_type,
                                    scope=sym.scope,
                                    chunk_type="symbol",
                                    content=content,
                                    start_line=sub_start,
                                    end_line=sub_end,
                                    token_count=self._estimate_tokens(content),
                                    language=file_entity.language,
                                    metadata={"is_large_split": True, "part_start_line": sub_start},
                                )
                            )
                            global_chunk_idx += 1
                            cur_idx += (chunk_step - overlap)
                            if cur_idx >= len(symbol_lines) - overlap:
                                break

            # Case B: File has no AST symbols (e.g. config, script, markdown, or unsupported language)
            else:
                window_size = 50
                step = 40
                cur_l = 0

                while cur_l < total_lines:
                    window = file_lines[cur_l:cur_l + window_size]
                    w_start = cur_l + 1
                    w_end = min(total_lines, cur_l + len(window))
                    w_code = "\n".join(window)

                    if len(w_code.strip()) >= MIN_CHUNK_CHARS:
                        content = self._format_chunk_content(
                            file_path=file_entity.path,
                            start_line=w_start,
                            end_line=w_end,
                            raw_code=w_code,
                            symbol_name=None,
                            symbol_type="file_section",
                            scope=None,
                            imports_summary=imports_summary,
                        )
                        chunks.append(
                            CodeChunkData(
                                chunk_index=global_chunk_idx,
                                file_id=file_entity.id,
                                file_path=file_entity.path,
                                symbol_id=None,
                                symbol_name=None,
                                symbol_type=None,
                                scope=None,
                                chunk_type="file_section",
                                content=content,
                                start_line=w_start,
                                end_line=w_end,
                                token_count=self._estimate_tokens(content),
                                language=file_entity.language,
                                metadata={"window_start": w_start, "window_end": w_end},
                            )
                        )
                        global_chunk_idx += 1

                    cur_l += step
                    if cur_l >= total_lines - 5:
                        break

        logger.info(
            "Chunking complete for repo %s: generated %d code chunks.",
            repository_id,
            len(chunks),
        )
        return chunks
