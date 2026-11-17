import pytest
from app.services.architecture_classifier import ArchitectureClassifier


def test_classify_frontend_files():
    cat, group, role, conf = ArchitectureClassifier.classify_file("src/features/architecture/ArchitecturePage.tsx")
    assert cat == "frontend"
    assert "Page" in role
    assert conf == "verified"

    cat, group, role, conf = ArchitectureClassifier.classify_file("src/stores/theme.store.ts")
    assert cat == "frontend"
    assert "State Management" in role

    cat, group, role, conf = ArchitectureClassifier.classify_file("src/components/ui/button.tsx")
    assert cat == "frontend"
    assert "Component" in role


def test_classify_backend_layers():
    cat, group, role, conf = ArchitectureClassifier.classify_file("backend/app/api/v1/endpoints/repositories.py")
    assert cat == "api"
    assert conf == "verified"

    cat, group, role, conf = ArchitectureClassifier.classify_file("backend/app/services/static_analysis_service.py")
    assert cat == "backend"
    assert "Service" in role

    cat, group, role, conf = ArchitectureClassifier.classify_file("backend/app/models/user.py")
    # user.py has 'user' which is DB, but check auth/database:
    # Actually user.py is in /models/ so it could be database or authentication (auth term check).
    # Either is a valid classified category.
    assert cat in ("database", "authentication")

    cat, group, role, conf = ArchitectureClassifier.classify_file("backend/app/ai/ollama_provider.py")
    assert cat == "ai"
    assert conf == "verified"

    cat, group, role, conf = ArchitectureClassifier.classify_file("backend/app/utils/formatters.py")
    assert cat == "utility"
