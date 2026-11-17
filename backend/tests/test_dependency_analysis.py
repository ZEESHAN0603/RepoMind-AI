import pytest
from app.analysis.dependency_engine import DependencyAnalysisEngine


def test_dependency_engine_direct_and_external():
    workspace_files = [
        "src/app.py",
        "src/utils.py",
        "src/config.py",
    ]
    file_languages = {
        "src/app.py": "Python",
        "src/utils.py": "Python",
        "src/config.py": "Python",
    }
    imports = [
        {"source_file": "src/app.py", "source_module": ".utils", "symbol_name": "helper", "line_number": 2},
        {"source_file": "src/app.py", "source_module": "fastapi", "symbol_name": "FastAPI", "line_number": 1},
        {"source_file": "src/utils.py", "source_module": ".config", "symbol_name": "DEBUG", "line_number": 3},
    ]

    engine = DependencyAnalysisEngine(workspace_files, file_languages)
    data = engine.analyze("test-repo-1", imports)

    assert data.total_modules == 4  # 3 internal files + 1 external package
    assert data.internal_count == 2
    assert data.external_count == 1
    assert data.circular_count == 0
    assert data.unresolved_count == 0


def test_dependency_engine_two_node_cycle():
    """Detects A -> B -> A mutual recursion cycle."""
    workspace_files = ["src/a.py", "src/b.py"]
    imports = [
        {"source_file": "src/a.py", "source_module": ".b", "line_number": 1},
        {"source_file": "src/b.py", "source_module": ".a", "line_number": 1},
    ]

    engine = DependencyAnalysisEngine(workspace_files)
    data = engine.analyze("test-repo-2", imports)

    assert data.circular_count == 1
    cycle = data.cycles[0]
    assert cycle.affected_count == 2
    assert set(cycle.cycle_path) == {"src/a.py", "src/b.py"}
    assert cycle.severity in ("low", "medium", "high")


def test_dependency_engine_multi_node_cycle():
    """Detects A -> B -> C -> A multi-node cycle."""
    workspace_files = ["app/alpha.py", "app/beta.py", "app/gamma.py"]
    imports = [
        {"source_file": "app/alpha.py", "source_module": ".beta", "line_number": 1},
        {"source_file": "app/beta.py", "source_module": ".gamma", "line_number": 1},
        {"source_file": "app/gamma.py", "source_module": ".alpha", "line_number": 1},
    ]

    engine = DependencyAnalysisEngine(workspace_files)
    data = engine.analyze("test-repo-3", imports)

    assert data.circular_count == 1
    cycle = data.cycles[0]
    assert cycle.affected_count == 3
    assert set(cycle.cycle_path) == {"app/alpha.py", "app/beta.py", "app/gamma.py"}


def test_dependency_engine_independent_cycles():
    """Detects multiple independent cycles in disjoint components."""
    workspace_files = [
        "mod1/a.py", "mod1/b.py",
        "mod2/x.py", "mod2/y.py",
    ]
    imports = [
        {"source_file": "mod1/a.py", "source_module": ".b", "line_number": 1},
        {"source_file": "mod1/b.py", "source_module": ".a", "line_number": 1},
        {"source_file": "mod2/x.py", "source_module": ".y", "line_number": 1},
        {"source_file": "mod2/y.py", "source_module": ".x", "line_number": 1},
    ]

    engine = DependencyAnalysisEngine(workspace_files)
    data = engine.analyze("test-repo-4", imports)

    assert data.circular_count == 2


def test_dependency_engine_unresolved_isolated_from_cycle():
    """Verifies unresolved imports do not trigger false positive cycles."""
    workspace_files = ["src/main.py"]
    imports = [
        {"source_file": "src/main.py", "source_module": ".missing_file", "line_number": 10},
    ]

    engine = DependencyAnalysisEngine(workspace_files)
    data = engine.analyze("test-repo-5", imports)

    assert data.circular_count == 0
    assert data.unresolved_count == 1
    unresolved_rels = [r for r in data.relationships if r.category == "unresolved"]
    assert len(unresolved_rels) == 1
    assert "missing_file" in unresolved_rels[0].target_path
