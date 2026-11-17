import re
from pathlib import PurePosixPath
from typing import List, Optional, Tuple

from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile


class ArchitectureClassifier:
    """
    Classifies files, modules, and symbols into architectural layers and roles.
    Assigns categories matching the frontend's ArchNodeCategory specification:
    frontend, backend, api, database, authentication, external, internal, utility, ai, worker.
    """

    @staticmethod
    def classify_file(
        file_path: str,
        symbols: Optional[List[CodeSymbol]] = None,
        endpoints: Optional[List[ApiRouteEndpoint]] = None,
    ) -> Tuple[str, str, str, str]:
        """
        Returns (category, group, role_description, confidence)
        """
        p = file_path.replace("\\", "/").lower()
        posix = PurePosixPath(file_path.replace("\\", "/"))
        parent_dir = str(posix.parent)
        group = parent_dir if parent_dir != "." else "root"

        # 1. AI Services and Providers
        if any(seg in p for seg in ("/ai/", "/rag/", "llm", "embedding", "chunking", "provider")):
            return "ai", group, "AI & Vector Intelligence Service", "verified"

        # 2. Authentication & Security
        if any(term in p for term in ("auth", "security", "token", "jwt", "password", "session")):
            return "authentication", group, "Authentication & Security Module", "verified"

        # 3. API Routes / Endpoints
        if endpoints or any(seg in p for seg in ("/api/", "/routes/", "/endpoints/", "/controllers/")):
            return "api", group, "API Route Endpoint Controller", "verified"

        # 4. Database Models / Schemas / Migrations
        if any(seg in p for seg in ("/models/", "/schemas/", "/db/", "/entities/", "schema", "migration")):
            if "schema" in p and not ("model" in p or "db" in p):
                return "database", group, "Data Schema Definition", "verified"
            return "database", group, "Database Model & Entity Schema", "verified"

        # 5. Background Workers & Queues
        if any(term in p for term in ("worker", "queue", "celery", "scheduler", "cron", "ingest", "task")):
            return "worker", group, "Background Worker / Task Processor", "verified"

        # 6. Frontend Components, Pages, Stores
        if p.startswith("src/") or p.startswith("frontend/") or p.endswith((".tsx", ".jsx", ".vue", ".svelte", ".html", ".css")):
            if "store" in p or "redux" in p or "zustand" in p or "context" in p:
                return "frontend", group, "Frontend State Management Store", "verified"
            if "page" in p or "view" in p or "/routes" in p:
                return "frontend", group, "Frontend Page / View Component", "verified"
            if "component" in p or "ui" in p:
                return "frontend", group, "Frontend UI Component", "verified"
            if "service" in p or "api" in p:
                return "frontend", group, "Frontend API Client Adapter", "verified"
            return "frontend", group, "Frontend Module", "verified"

        # 7. Backend Domain Services & Repositories
        if any(seg in p for seg in ("/services/", "/repositories/", "/managers/", "/handlers/")):
            if "repository" in p or "dao" in p:
                return "backend", group, "Data Access Repository", "verified"
            return "backend", group, "Backend Domain Service", "verified"

        # 8. Utilities & Helpers
        if any(seg in p for seg in ("/utils/", "/helpers/", "/common/", "/lib/", "constants", "formatters", "types")):
            return "utility", group, "Shared Utility / Helper Module", "verified"

        # 9. External Integrations / Third-party adapters
        if any(term in p for term in ("github", "stripe", "webhook", "client", "external", "aws", "s3")):
            return "external", group, "External Service Integration", "inferred"

        # 10. Default Backend / Internal
        if p.startswith("backend/") or p.endswith(".py") or p.endswith(".go") or p.endswith(".rs") or p.endswith(".java"):
            return "backend", group, "Backend Internal Module", "inferred"

        return "internal", group, "Repository Module", "inferred"
