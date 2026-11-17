import difflib
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.logging import logger

MAX_DIFF_PATCH_BYTES = 200 * 1024  # 200 KB per file unified diff cap

MANIFEST_FILENAMES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "go.mod",
    "go.sum",
    "cargo.toml",
    "cargo.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "gemfile",
    "gemfile.lock",
    "composer.json",
    "composer.lock",
}

CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml"}
CONFIG_FILENAMES = {
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "tsconfig.json",
    ".eslintrc",
    ".eslintrc.json",
    ".prettierrc",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
}

DOC_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}


class UpdateDetectionService:
    """Detects, categorizes, and diffs file changes between repository snapshots or commits."""

    @classmethod
    def compute_sha256(cls, content: str | bytes) -> str:
        """Computes SHA-256 hash of text or bytes content."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    @classmethod
    def categorize_file(cls, path: str) -> str:
        """Classifies a relative file path into source, manifest, config, documentation, or other."""
        norm_path = path.replace("\\", "/").lower()
        filename = Path(norm_path).name
        ext = Path(norm_path).suffix

        # 1. Manifest
        if filename in MANIFEST_FILENAMES:
            return "manifest"

        # 2. Config
        if filename in CONFIG_FILENAMES or filename.startswith(".env") or ext in CONFIG_EXTENSIONS:
            return "config"

        # 3. Documentation
        if ext in DOC_EXTENSIONS or norm_path.startswith("docs/") or "license" in filename or "readme" in filename:
            return "documentation"

        # 4. Source (known programming language extensions)
        source_exts = {
            ".py", ".pyw", ".js", ".jsx", ".mjs", ".ts", ".tsx",
            ".java", ".go", ".rs", ".c", ".h", ".cpp", ".hpp",
            ".cc", ".cs", ".rb", ".php", ".swift", ".kt", ".scala",
            ".sh", ".bash", ".ps1", ".sql", ".html", ".css", ".scss",
        }
        if ext in source_exts:
            return "source"

        return "other"

    @classmethod
    def compute_unified_diff(
        cls,
        old_content: Optional[str],
        new_content: Optional[str],
        file_path: str,
    ) -> Tuple[int, int, str]:
        """
        Computes line additions, deletions, and a bounded unified diff patch string.
        Returns: (additions, deletions, diff_patch)
        """
        old_lines = (old_content or "").splitlines(keepends=True)
        new_lines = (new_content or "").splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        additions = 0
        deletions = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "insert":
                additions += (j2 - j1)
            elif tag == "delete":
                deletions += (i2 - i1)
            elif tag == "replace":
                deletions += (i2 - i1)
                additions += (j2 - j1)

        diff_gen = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            n=3,
        )
        diff_text = "".join(diff_gen)

        # Enforce memory safety cap
        if len(diff_text.encode("utf-8")) > MAX_DIFF_PATCH_BYTES:
            diff_text = diff_text[:MAX_DIFF_PATCH_BYTES] + "\n\n... [DIFF TRUNCATED - OVERSIZED] ..."

        return additions, deletions, diff_text

    @classmethod
    def detect_file_changes(
        cls,
        base_files: Dict[str, str],   # path -> file content (or None if not fetched)
        target_files: Dict[str, str], # path -> file content
        known_renames: Optional[Dict[str, str]] = None, # new_path -> old_path (from Git)
    ) -> List[Dict[str, Any]]:
        """
        Compares base and target file sets and produces structured file change records.
        Detects added, modified, deleted, and renamed files.
        """
        base_paths = set(base_files.keys())
        target_paths = set(target_files.keys())
        known_renames = known_renames or {}

        changes: List[Dict[str, Any]] = []

        # 1. Identify added & potential renames
        added_paths = target_paths - base_paths
        deleted_paths = base_paths - target_paths
        common_paths = base_paths & target_paths

        # Map hashes for rename detection if content is available
        base_hash_to_path: Dict[str, str] = {}
        for p in deleted_paths:
            content = base_files.get(p)
            if content is not None:
                h = cls.compute_sha256(content)
                base_hash_to_path[h] = p

        matched_renames: Dict[str, str] = {}  # new_path -> old_path

        # Check explicit Git renames first
        for new_p, old_p in known_renames.items():
            if new_p in added_paths and old_p in deleted_paths:
                matched_renames[new_p] = old_p

        # Check content-hash based renames for remaining added paths
        for new_p in list(added_paths):
            if new_p in matched_renames:
                continue
            new_content = target_files.get(new_p)
            if new_content is not None:
                new_h = cls.compute_sha256(new_content)
                if new_h in base_hash_to_path:
                    old_p = base_hash_to_path.pop(new_h)
                    matched_renames[new_p] = old_p

        # 2. Process Renamed & Added Files
        for p in sorted(added_paths):
            new_content = target_files.get(p, "")
            new_hash = cls.compute_sha256(new_content)
            new_size = len(new_content.encode("utf-8"))
            category = cls.categorize_file(p)

            if p in matched_renames:
                old_p = matched_renames[p]
                old_content = base_files.get(old_p, "")
                old_hash = cls.compute_sha256(old_content)
                old_size = len(old_content.encode("utf-8"))
                adds, dels, patch = cls.compute_unified_diff(old_content, new_content, p)
                changes.append({
                    "path": p,
                    "old_path": old_p,
                    "change_type": "renamed",
                    "file_category": category,
                    "additions": adds,
                    "deletions": dels,
                    "old_size_bytes": old_size,
                    "new_size_bytes": new_size,
                    "old_content_hash": old_hash,
                    "new_content_hash": new_hash,
                    "diff_patch": patch,
                    "summary": f"Renamed from {old_p} to {p} (+{adds}/-{dels})",
                })
                deleted_paths.discard(old_p)
            else:
                adds, dels, patch = cls.compute_unified_diff("", new_content, p)
                changes.append({
                    "path": p,
                    "old_path": None,
                    "change_type": "added",
                    "file_category": category,
                    "additions": adds,
                    "deletions": dels,
                    "old_size_bytes": 0,
                    "new_size_bytes": new_size,
                    "old_content_hash": None,
                    "new_content_hash": new_hash,
                    "diff_patch": patch,
                    "summary": f"Added file {p} (+{adds} lines)",
                })

        # 3. Process Modified Files
        for p in sorted(common_paths):
            old_content = base_files.get(p, "")
            new_content = target_files.get(p, "")
            old_hash = cls.compute_sha256(old_content)
            new_hash = cls.compute_sha256(new_content)

            if old_hash != new_hash:
                old_size = len(old_content.encode("utf-8"))
                new_size = len(new_content.encode("utf-8"))
                adds, dels, patch = cls.compute_unified_diff(old_content, new_content, p)
                category = cls.categorize_file(p)
                changes.append({
                    "path": p,
                    "old_path": None,
                    "change_type": "modified",
                    "file_category": category,
                    "additions": adds,
                    "deletions": dels,
                    "old_size_bytes": old_size,
                    "new_size_bytes": new_size,
                    "old_content_hash": old_hash,
                    "new_content_hash": new_hash,
                    "diff_patch": patch,
                    "summary": f"Modified {p} (+{adds}/-{dels} lines)",
                })

        # 4. Process Deleted Files
        for p in sorted(deleted_paths):
            old_content = base_files.get(p, "")
            old_hash = cls.compute_sha256(old_content)
            old_size = len(old_content.encode("utf-8"))
            adds, dels, patch = cls.compute_unified_diff(old_content, "", p)
            category = cls.categorize_file(p)
            changes.append({
                "path": p,
                "old_path": None,
                "change_type": "deleted",
                "file_category": category,
                "additions": 0,
                "deletions": dels,
                "old_size_bytes": old_size,
                "new_size_bytes": 0,
                "old_content_hash": old_hash,
                "new_content_hash": None,
                "diff_patch": patch,
                "summary": f"Deleted file {p} (-{dels} lines)",
            })

        return changes
