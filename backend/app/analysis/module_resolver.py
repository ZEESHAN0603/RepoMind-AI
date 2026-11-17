import os
from pathlib import PurePosixPath
from typing import Dict, List, Optional, Set, Tuple


class ModuleResolver:
    """
    Resolves static import statements to concrete repository file paths
    across Python, TypeScript/JavaScript, and multi-language projects.
    """

    TS_JS_EXTENSIONS = [
        ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
        "/index.ts", "/index.tsx", "/index.js", "/index.jsx"
    ]
    PYTHON_EXTENSIONS = [".py", "/__init__.py", ".pyi"]

    def __init__(self, workspace_files: List[str]) -> None:
        """
        :param workspace_files: List of all normalized POSIX relative file paths in repository.
        """
        # Store normalized paths using forward slashes
        self.workspace_files = [f.replace("\\", "/").lstrip("/") for f in workspace_files]
        self._file_set: Set[str] = set(self.workspace_files)

        # Detect package roots (e.g. "backend", "src", "app", "")
        self.package_roots = self._detect_package_roots()

    def _detect_package_roots(self) -> List[str]:
        """Identifies root directories where packages and source files originate."""
        roots = {""}
        for f in self.workspace_files:
            parts = f.split("/")
            if len(parts) > 1:
                top = parts[0]
                if top in ("backend", "frontend", "src", "app", "packages", "server", "client", "lib"):
                    roots.add(top)
                if len(parts) > 2 and parts[0] in ("backend", "frontend", "packages"):
                    roots.add(f"{parts[0]}/{parts[1]}")
        return sorted(list(roots), key=lambda r: len(r), reverse=True)

    def resolve_import(
        self,
        importing_file: str,
        source_module: str,
    ) -> Tuple[Optional[str], bool]:
        """
        Resolves an import source string to a target repository file path.

        :param importing_file: The relative path of the file containing the import.
        :param source_module: The imported module string (e.g., './utils', 'app.models.user', 'react').
        :return: (resolved_relative_path or None, is_external)
        """
        if not source_module or not source_module.strip():
            return None, False

        mod = source_module.strip().replace("\\", "/")
        norm_importing = importing_file.replace("\\", "/").lstrip("/")
        importing_dir = str(PurePosixPath(norm_importing).parent)
        if importing_dir == ".":
            importing_dir = ""

        # 1. Handle TypeScript / JavaScript path alias '@/...'
        if mod.startswith("@/"):
            alias_sub = mod[2:]  # remove '@/'
            # Search in 'src/' or package root + 'src/'
            for root in self.package_roots:
                prefix = f"{root}/src" if root else "src"
                candidate_base = f"{prefix}/{alias_sub}".replace("//", "/")
                target = self._match_file_with_extensions(candidate_base, self.TS_JS_EXTENSIONS)
                if target:
                    return target, False
            # Check direct candidate base without 'src/'
            target = self._match_file_with_extensions(alias_sub, self.TS_JS_EXTENSIONS)
            if target:
                return target, False

        # 2. Handle Explicit Relative Imports (starts with '.' or '..')
        if mod.startswith("."):
            return self._resolve_relative_import(importing_dir, mod, norm_importing)

        # 3. Handle Python dotted module imports (e.g. 'app.models.user')
        if not mod.startswith("@") and not mod.startswith("/") and "." in mod:
            as_path = mod.replace(".", "/")
            # Try matching across known package roots
            for root in self.package_roots:
                candidate = f"{root}/{as_path}".lstrip("/")
                target = self._match_file_with_extensions(candidate, self.PYTHON_EXTENSIONS)
                if target:
                    return target, False

        # 4. Handle non-dotted single-word or top-level module (e.g. 'utils', 'config', 'app')
        for root in self.package_roots:
            candidate = f"{root}/{mod}".lstrip("/")
            # Check Python
            target = self._match_file_with_extensions(candidate, self.PYTHON_EXTENSIONS)
            if target:
                return target, False
            # Check JS/TS
            target = self._match_file_with_extensions(candidate, self.TS_JS_EXTENSIONS)
            if target:
                return target, False

        # 5. Check direct file match
        if mod in self._file_set:
            return mod, False

        # If it cannot be matched anywhere inside the repository, it is an external package
        # (e.g. 'fastapi', 'react', 'sqlalchemy', 'lucide-react', 'os', 'sys')
        return None, True

    def _resolve_relative_import(
        self,
        importing_dir: str,
        mod: str,
        importing_file: str,
    ) -> Tuple[Optional[str], bool]:
        """Resolves relative imports like './foo', '../bar', '.service'."""
        is_python = importing_file.endswith((".py", ".pyi"))
        extensions = self.PYTHON_EXTENSIONS if is_python else self.TS_JS_EXTENSIONS

        # Python relative dot syntax (e.g. '..models.user' or '.services')
        if is_python and not mod.startswith("./") and not mod.startswith("../"):
            # Count leading dots
            num_dots = len(mod) - len(mod.lstrip("."))
            sub_mod = mod.lstrip(".").replace(".", "/")
            # Navigate up
            parts = importing_dir.split("/") if importing_dir else []
            # In Python, 1 dot is current package directory (parts)
            # 2 dots is parent directory, etc.
            steps_up = num_dots - 1
            if steps_up > 0 and len(parts) >= steps_up:
                base_parts = parts[:-steps_up]
            elif steps_up == 0:
                base_parts = parts
            else:
                base_parts = []

            base_dir = "/".join(base_parts)
            candidate = f"{base_dir}/{sub_mod}".lstrip("/").replace("//", "/")
            target = self._match_file_with_extensions(candidate, extensions)
            if target:
                return target, False
            return None, False

        # Standard path relative import ('./...' or '../...')
        try:
            combined = PurePosixPath(importing_dir) / mod
            norm_str = os.path.normpath(str(combined)).replace("\\", "/")
            if norm_str.startswith("./"):
                norm_str = norm_str[2:]
            elif norm_str == ".":
                norm_str = ""

            target = self._match_file_with_extensions(norm_str, extensions)
            if target:
                return target, False
        except Exception:
            pass

        return None, False

    def _match_file_with_extensions(self, base_path: str, extensions: List[str]) -> Optional[str]:
        """Checks if base_path or base_path + extension matches a file in file_set."""
        base = base_path.rstrip("/")
        if base in self._file_set:
            return base

        for ext in extensions:
            cand = base + ext
            if cand in self._file_set:
                return cand

        return None
