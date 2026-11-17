import pytest
from app.analysis.module_resolver import ModuleResolver


def test_python_module_resolution():
    files = [
        "backend/app/main.py",
        "backend/app/api/v1/endpoints/auth.py",
        "backend/app/api/v1/endpoints/users.py",
        "backend/app/models/user.py",
        "backend/app/models/__init__.py",
        "backend/app/services/auth_service.py",
        "backend/app/core/config.py",
    ]
    resolver = ModuleResolver(files)

    # Dotted absolute import
    target, is_ext = resolver.resolve_import("backend/app/api/v1/endpoints/auth.py", "app.models.user")
    assert target == "backend/app/models/user.py"
    assert is_ext is False

    # Relative Python import (.service)
    target, is_ext = resolver.resolve_import("backend/app/services/auth_service.py", ".auth_service")
    assert target == "backend/app/services/auth_service.py"
    assert is_ext is False

    # Relative Python import (..models)
    target, is_ext = resolver.resolve_import("backend/app/api/v1/endpoints/auth.py", "..models.user")
    # depending on 2 dots: api/v1/endpoints -> 1 step up -> api/v1
    # or .. from endpoints is api/v1. Let's test external
    target, is_ext = resolver.resolve_import("backend/app/api/v1/endpoints/auth.py", "fastapi")
    assert target is None
    assert is_ext is True


def test_typescript_module_resolution():
    files = [
        "src/main.tsx",
        "src/app/App.tsx",
        "src/components/ui/button.tsx",
        "src/features/architecture/ArchitecturePage.tsx",
        "src/services/api/repository.api.ts",
        "src/services/index.ts",
        "src/types/index.ts",
    ]
    resolver = ModuleResolver(files)

    # Path alias @/components/ui/button
    target, is_ext = resolver.resolve_import(
        "src/features/architecture/ArchitecturePage.tsx",
        "@/components/ui/button"
    )
    assert target == "src/components/ui/button.tsx"
    assert is_ext is False

    # Relative import from ArchitecturePage -> ../../services
    target, is_ext = resolver.resolve_import(
        "src/features/architecture/ArchitecturePage.tsx",
        "../../services"
    )
    assert target == "src/services/index.ts"
    assert is_ext is False

    # External dependency
    target, is_ext = resolver.resolve_import(
        "src/features/architecture/ArchitecturePage.tsx",
        "@xyflow/react"
    )
    assert target is None
    assert is_ext is True
