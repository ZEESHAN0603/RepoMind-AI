import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.core.config import settings
from app.models.repository_file import RepositoryFile
from app.schemas.repository import RepositoryFileNode

# Common extension to language mapping
EXTENSION_LANGUAGE_MAP: Dict[str, str] = {
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
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "SASS",
    ".less": "Less",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".xml": "XML",
    ".sql": "SQL",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".dockerfile": "Dockerfile",
}

BINARY_EXTENSIONS: Set[str] = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".bmp", ".tiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".7z", ".rar", ".bz2",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a",
    ".pyc", ".pyo", ".pyd", ".class",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".mkv",
    ".woff", ".woff2", ".ttf", ".eot",
}


class DiscoveryService:
    """Recursively discovers repository files and builds metadata indexes."""

    @classmethod
    def is_binary_file(cls, file_path: Path) -> bool:
        """Determines if a file is binary using extension and initial byte inspection."""
        ext = file_path.suffix.lower()
        if ext in BINARY_EXTENSIONS:
            return True

        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                # If null byte is present, file is considered binary
                if b"\x00" in chunk:
                    return True
        except Exception:
            return True
        return False

    @classmethod
    def detect_language_for_file(cls, file_path: Path) -> Optional[str]:
        """Detects language by filename and extension."""
        name_lower = file_path.name.lower()
        if name_lower == "dockerfile":
            return "Dockerfile"
        if name_lower == "makefile":
            return "Makefile"
        if name_lower == "gemfile":
            return "Ruby"

        ext = file_path.suffix.lower()
        return EXTENSION_LANGUAGE_MAP.get(ext)

    @classmethod
    def discover_repository(
        cls,
        workspace_dir: Path,
        repository_id: str,
        ignore_dirs: Optional[List[str]] = None,
    ) -> Tuple[List[RepositoryFile], int, int, int]:
        """
        Discovers all files and folders recursively in the repository workspace.
        Returns:
            - files: List[RepositoryFile] entities
            - total_file_count: int
            - total_folder_count: int
            - total_bytes: int
        """
        workspace_dir = workspace_dir.resolve()
        ignored = set(ignore_dirs or settings.DEFAULT_IGNORE_DIRS)

        discovered_entities: List[RepositoryFile] = []
        folder_count = 0
        file_count = 0
        total_bytes = 0

        for root, dirs, files in os.walk(workspace_dir):
            # In-place filtering of ignored directories so os.walk does not descend into them
            dirs[:] = [d for d in dirs if d not in ignored and not d.startswith(".git")]

            current_root = Path(root)
            rel_dir = current_root.relative_to(workspace_dir).as_posix()

            # Record directory entities if not the root
            if rel_dir != ".":
                folder_count += 1
                discovered_entities.append(
                    RepositoryFile(
                        repository_id=repository_id,
                        path=rel_dir,
                        name=current_root.name,
                        extension="",
                        file_type="folder",
                        size_bytes=0,
                        is_binary=False,
                        language=None,
                    )
                )

            for filename in sorted(files):
                full_path = current_root / filename
                rel_path = full_path.relative_to(workspace_dir).as_posix()
                try:
                    file_size = full_path.stat().st_size
                except OSError:
                    file_size = 0

                is_bin = cls.is_binary_file(full_path)
                lang = None if is_bin else cls.detect_language_for_file(full_path)

                total_bytes += file_size
                file_count += 1

                discovered_entities.append(
                    RepositoryFile(
                        repository_id=repository_id,
                        path=rel_path,
                        name=filename,
                        extension=full_path.suffix.lower(),
                        file_type="file",
                        size_bytes=file_size,
                        is_binary=is_bin,
                        language=lang,
                    )
                )

        return discovered_entities, file_count, folder_count, total_bytes

    @classmethod
    def build_tree_from_files(cls, files: List[RepositoryFile]) -> List[RepositoryFileNode]:
        """Converts flat list of RepositoryFile records into hierarchical RepositoryFileNode tree."""
        # Map path to node
        node_map: Dict[str, RepositoryFileNode] = {}
        root_nodes: List[RepositoryFileNode] = []

        # Sort files by path depth
        sorted_files = sorted(files, key=lambda f: f.path)

        for f in sorted_files:
            node = RepositoryFileNode(
                id=f.id,
                name=f.name,
                path=f.path,
                type=f.file_type,
                language=f.language,
                size_bytes=f.size_bytes,
                is_binary=f.is_binary,
                children=[] if f.file_type == "folder" else None,
            )
            node_map[f.path] = node

            # Check if has parent
            parts = f.path.split("/")
            if len(parts) > 1:
                parent_path = "/".join(parts[:-1])
                parent_node = node_map.get(parent_path)
                if parent_node and parent_node.children is not None:
                    parent_node.children.append(node)
                else:
                    root_nodes.append(node)
            else:
                root_nodes.append(node)

        return root_nodes

