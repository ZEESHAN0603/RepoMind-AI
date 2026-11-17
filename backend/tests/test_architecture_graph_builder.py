import uuid
import pytest
from app.models.api_route_endpoint import ApiRouteEndpoint
from app.models.code_import_export import CodeImportExport
from app.models.code_symbol import CodeSymbol
from app.models.repository_file import RepositoryFile
from app.services.architecture_graph_builder import ArchitectureGraphBuilder


def test_architecture_graph_builder_end_to_end():
    repo_id = str(uuid.uuid4())
    file1_id = str(uuid.uuid4())
    file2_id = str(uuid.uuid4())
    file3_id = str(uuid.uuid4())

    files = [
        RepositoryFile(
            id=file1_id,
            repository_id=repo_id,
            path="src/features/architecture/ArchitecturePage.tsx",
            name="ArchitecturePage.tsx",
            file_type="file",
            is_binary=False,
            extension=".tsx",
        ),
        RepositoryFile(
            id=file2_id,
            repository_id=repo_id,
            path="backend/app/api/v1/endpoints/repositories.py",
            name="repositories.py",
            file_type="file",
            is_binary=False,
            extension=".py",
        ),
        RepositoryFile(
            id=file3_id,
            repository_id=repo_id,
            path="backend/app/models/repository.py",
            name="repository.py",
            file_type="file",
            is_binary=False,
            extension=".py",
        ),
    ]

    symbols = [
        CodeSymbol(
            id=str(uuid.uuid4()),
            repository_id=repo_id,
            file_id=file2_id,
            name="list_repositories",
            symbol_type="function",
            start_line=25,
            end_line=40,
            is_exported=True,
        ),
        CodeSymbol(
            id=str(uuid.uuid4()),
            repository_id=repo_id,
            file_id=file3_id,
            name="Repository",
            symbol_type="class",
            start_line=10,
            end_line=50,
            is_exported=True,
        ),
    ]

    imports = [
        CodeImportExport(
            id=str(uuid.uuid4()),
            repository_id=repo_id,
            file_id=file2_id,
            statement_type="import",
            source_module="app.models.repository",
            line_number=5,
        )
    ]

    endpoints = [
        ApiRouteEndpoint(
            id=str(uuid.uuid4()),
            repository_id=repo_id,
            file_id=file2_id,
            http_method="GET",
            path="/api/v1/repositories",
            handler_name="list_repositories",
            framework="FastAPI",
            start_line=25,
            end_line=40,
        )
    ]

    builder = ArchitectureGraphBuilder(
        repository_id=repo_id,
        files=files,
        symbols=symbols,
        imports_exports=imports,
        endpoints=endpoints,
    )

    graph = builder.build_graph()

    assert graph["repositoryId"] == repo_id
    assert len(graph["nodes"]) >= 3
    assert len(graph["edges"]) >= 1

    # Check views exist
    assert "system" in graph["views"]
    assert "frontend" in graph["views"]
    assert "backend" in graph["views"]
    assert "api" in graph["views"]
    assert "database" in graph["views"]
    assert "modules" in graph["views"]

    # Verify edge connects file2 to file3
    edge = [e for e in graph["edges"] if "node:backend/app/api/v1/endpoints/repositories.py" in e["source"]][0]
    assert edge["target"] == "node:backend/app/models/repository.py"
    assert edge["label"] == "imports"
    assert edge["confidence"] == "verified"
