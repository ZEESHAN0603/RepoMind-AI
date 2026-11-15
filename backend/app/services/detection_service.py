import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

from app.models.repository_file import RepositoryFile
from app.models.repository_language import RepositoryLanguage
from app.models.repository_manifest import RepositoryDependencyManifest

LANGUAGE_COLORS: Dict[str, str] = {
    "Python": "#3572A5",
    "TypeScript": "#3178C6",
    "JavaScript": "#F1E05A",
    "Go": "#00ADD8",
    "Rust": "#DEA584",
    "Java": "#B07219",
    "Kotlin": "#A97BFF",
    "C": "#555555",
    "C++": "#F34B7D",
    "C#": "#178600",
    "Ruby": "#701516",
    "PHP": "#4F5D95",
    "Swift": "#F05138",
    "HTML": "#E34C26",
    "CSS": "#563D7C",
    "SCSS": "#C6538C",
    "Shell": "#89E051",
    "PowerShell": "#012456",
    "SQL": "#E38C00",
    "Markdown": "#083FA1",
    "JSON": "#292929",
    "YAML": "#CB171E",
    "TOML": "#9C4221",
    "Dockerfile": "#384D54",
}

DEFAULT_LANG_COLOR = "#6B7280"

# Framework indicators by ecosystem
NPM_FRAMEWORK_SIGNATURES = {
    "react": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "@angular/core": "Angular",
    "express": "Express",
    "@nestjs/core": "NestJS",
    "tailwindcss": "Tailwind CSS",
    "vite": "Vite",
    "svelte": "Svelte",
    "astro": "Astro",
    "@remix-run/react": "Remix",
}

PYTHON_FRAMEWORK_SIGNATURES = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "pydantic": "Pydantic",
    "sqlalchemy": "SQLAlchemy",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "celery": "Celery",
    "alembic": "Alembic",
    "httpx": "HTTPX",
}

RUST_FRAMEWORK_SIGNATURES = {
    "actix-web": "Actix-web",
    "axum": "Axum",
    "tokio": "Tokio",
    "rocket": "Rocket",
    "diesel": "Diesel",
    "serde": "Serde",
}

GO_FRAMEWORK_SIGNATURES = {
    "gin-gonic/gin": "Gin",
    "labstack/echo": "Echo",
    "gofiber/fiber": "Fiber",
    "gorilla/mux": "Gorilla Mux",
    "gorm.io/gorm": "GORM",
}


class TechnologyDetectionService:
    """Analyzes workspace files to detect languages, frameworks, and dependency manifests."""

    @classmethod
    def calculate_language_distribution(
        cls,
        files: List[RepositoryFile],
        repository_id: str,
    ) -> List[RepositoryLanguage]:
        """Calculates language byte and file distribution across all non-binary files."""
        lang_stats: Dict[str, Dict[str, int]] = {}
        total_source_bytes = 0

        for f in files:
            if f.file_type == "file" and not f.is_binary and f.language:
                lang = f.language
                if lang not in lang_stats:
                    lang_stats[lang] = {"bytes": 0, "files": 0}
                lang_stats[lang]["bytes"] += f.size_bytes
                lang_stats[lang]["files"] += 1
                total_source_bytes += f.size_bytes

        languages: List[RepositoryLanguage] = []
        for lang_name, stats in sorted(lang_stats.items(), key=lambda x: x[1]["bytes"], reverse=True):
            pct = round((stats["bytes"] / total_source_bytes * 100), 2) if total_source_bytes > 0 else 0.0
            color = LANGUAGE_COLORS.get(lang_name, DEFAULT_LANG_COLOR)
            languages.append(
                RepositoryLanguage(
                    repository_id=repository_id,
                    language=lang_name,
                    byte_count=stats["bytes"],
                    file_count=stats["files"],
                    percentage=pct,
                    color=color,
                )
            )

        return languages

    @classmethod
    def detect_manifests(
        cls,
        workspace_dir: Path,
        repository_id: str,
    ) -> List[RepositoryDependencyManifest]:
        """Finds and parses dependency manifests in the workspace."""
        manifests: List[RepositoryDependencyManifest] = []

        manifest_finders = [
            ("package.json", "npm", cls._parse_package_json),
            ("requirements.txt", "pip", cls._parse_requirements_txt),
            ("pyproject.toml", "poetry/pip", cls._parse_pyproject_toml),
            ("Cargo.toml", "cargo", cls._parse_cargo_toml),
            ("go.mod", "go", cls._parse_go_mod),
            ("pom.xml", "maven", cls._parse_pom_xml),
            ("build.gradle", "gradle", cls._parse_gradle),
            ("Gemfile", "bundler", cls._parse_gemfile),
            ("composer.json", "composer", cls._parse_composer_json),
        ]

        workspace_dir = workspace_dir.resolve()

        for filename, ecosystem, parser_fn in manifest_finders:
            for file_path in workspace_dir.rglob(filename):
                # Skip if in ignored directory
                rel_parts = file_path.relative_to(workspace_dir).parts
                if any(p in (".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__") for p in rel_parts):
                    continue

                rel_path = file_path.relative_to(workspace_dir).as_posix()
                try:
                    frameworks = parser_fn(file_path)
                except Exception:
                    frameworks = []

                manifests.append(
                    RepositoryDependencyManifest(
                        repository_id=repository_id,
                        file_path=rel_path,
                        ecosystem=ecosystem,
                        manifest_type=filename,
                        detected_frameworks=json.dumps(frameworks),
                    )
                )

        return manifests

    @staticmethod
    def _parse_package_json(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            found = set()
            for key, framework_name in NPM_FRAMEWORK_SIGNATURES.items():
                if key in deps:
                    found.add(framework_name)
            return sorted(list(found))
        except Exception:
            return []

    @staticmethod
    def _parse_requirements_txt(path: Path) -> List[str]:
        try:
            found = set()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line_clean = line.strip().lower()
                    if not line_clean or line_clean.startswith("#"):
                        continue
                    pkg_name = re.split(r"[=><~;]", line_clean)[0].strip()
                    if pkg_name in PYTHON_FRAMEWORK_SIGNATURES:
                        found.add(PYTHON_FRAMEWORK_SIGNATURES[pkg_name])
            return sorted(list(found))
        except Exception:
            return []

    @staticmethod
    def _parse_pyproject_toml(path: Path) -> List[str]:
        try:
            found = set()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            for pkg_name, framework_name in PYTHON_FRAMEWORK_SIGNATURES.items():
                if re.search(rf"\b{re.escape(pkg_name)}\b", content):
                    found.add(framework_name)
            return sorted(list(found))
        except Exception:
            return []

    @staticmethod
    def _parse_cargo_toml(path: Path) -> List[str]:
        try:
            found = set()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            for crate, framework_name in RUST_FRAMEWORK_SIGNATURES.items():
                if crate in content:
                    found.add(framework_name)
            return sorted(list(found))
        except Exception:
            return []

    @staticmethod
    def _parse_go_mod(path: Path) -> List[str]:
        try:
            found = set()
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            for mod, framework_name in GO_FRAMEWORK_SIGNATURES.items():
                if mod in content:
                    found.add(framework_name)
            return sorted(list(found))
        except Exception:
            return []

    @staticmethod
    def _parse_pom_xml(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            found = []
            if "spring-boot" in content or "org.springframework" in content:
                found.append("Spring Boot")
            return found
        except Exception:
            return []

    @staticmethod
    def _parse_gradle(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            found = []
            if "spring-boot" in content or "org.springframework.boot" in content:
                found.append("Spring Boot")
            return found
        except Exception:
            return []

    @staticmethod
    def _parse_gemfile(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            found = []
            if "rails" in content:
                found.append("Ruby on Rails")
            return found
        except Exception:
            return []

    @staticmethod
    def _parse_composer_json(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            deps = {**data.get("require", {}), **data.get("require-dev", {})}
            found = []
            if "laravel/framework" in deps:
                found.append("Laravel")
            elif "symfony/framework-bundle" in deps:
                found.append("Symfony")
            return found
        except Exception:
            return []

