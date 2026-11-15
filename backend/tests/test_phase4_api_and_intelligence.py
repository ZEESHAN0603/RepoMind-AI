import io
import json
import zipfile
from pathlib import Path
import pytest
from httpx import AsyncClient

from app.analysis.python_parser import PythonAstParser
from app.analysis.schemas import ParseStatus, SymbolType
from app.models.repository import Repository
from app.models.repository_file import RepositoryFile
from app.services.static_analysis_service import StaticAnalysisService
from app.services.workspace_service import WorkspaceService


async def get_auth_token(client: AsyncClient, email: str, name: str = "Test User") -> str:
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": name, "email": email, "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    return login_res.json()["access_token"]


@pytest.mark.asyncio
async def test_static_analysis_end_to_end_flow(
    client: AsyncClient,
    tmp_path: Path,
):
    token = await get_auth_token(client, "analyst@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}
    # 1. Create a zip archive with multi-language code and API routes
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Python source with FastAPI routes, classes, methods
        zf.writestr(
            "app/routes/user.py",
            """
import os
from typing import Optional
from fastapi import APIRouter

router = APIRouter()

class UserProfile:
    '''User profile model.'''
    def __init__(self, username: str):
        self.username = username

    def get_display_name(self) -> str:
        return self.username.title()

@router.get("/users/{user_id}")
async def get_user_by_id(user_id: int) -> dict:
    '''Retrieve user by primary key.'''
    return {"id": user_id}

@router.post("/users")
async def create_new_user(data: dict):
    return data
""",
        )
        # TypeScript / Express source
        zf.writestr(
            "src/server.ts",
            """
import express from 'express';

const app = express();

export interface ServerConfig {
    port: number;
}

export class AppServer {
    start() {
        console.log('starting');
    }
}

app.get('/health', (req, res) => res.json({ status: 'ok' }));
app.delete('/items/:id', (req, res) => res.sendStatus(204));
""",
        )
        # Empty file
        zf.writestr("empty.py", "")
        # Malformed Python file (should fail parsing gracefully without stopping others)
        zf.writestr("malformed.py", "def broken_code(:\n  return {")

    zip_buffer.seek(0)

    # 2. Upload zip repository
    files = {"file": ("code_intel_test.zip", zip_buffer.getvalue(), "application/zip")}
    create_res = await client.post(
        "/api/v1/repositories/upload",
        files=files,
        data={"name": "code-intelligence-repo"},
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    repo_data = create_res.json()
    repo_id = repo_data["id"]

    # 3. Explicitly trigger static analysis endpoint
    analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=auth_headers,
    )
    assert analyze_res.status_code == 200
    summary = analyze_res.json()
    assert summary["repository_id"] == repo_id
    assert summary["symbols_extracted"] > 0
    assert summary["endpoints_extracted"] >= 2
    assert summary["files_failed"] >= 1  # malformed.py was safely counted

    # 4. Test GET /analysis overview endpoint
    overview_res = await client.get(
        f"/api/v1/repositories/{repo_id}/analysis",
        headers=auth_headers,
    )
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert overview["total_symbols"] > 0
    assert overview["total_endpoints"] >= 2
    assert "class" in overview["symbols_by_type"]
    assert "function" in overview["symbols_by_type"]
    assert "method" in overview["symbols_by_type"]

    # 5. Test GET /symbols endpoint (with pagination and search)
    symbols_res = await client.get(
        f"/api/v1/repositories/{repo_id}/symbols?limit=100",
        headers=auth_headers,
    )
    assert symbols_res.status_code == 200
    symbols_data = symbols_res.json()
    assert symbols_data["total"] > 0
    names = [s["name"] for s in symbols_data["items"]]
    assert "UserProfile" in names
    assert "get_user_by_id" in names
    assert "get_display_name" in names
    assert "AppServer" in names

    # Filter by symbol_type=class
    classes_res = await client.get(
        f"/api/v1/repositories/{repo_id}/symbols?symbol_type=class",
        headers=auth_headers,
    )
    assert classes_res.status_code == 200
    for item in classes_res.json()["items"]:
        assert item["symbol_type"] == "class"

    # Search symbol by name
    search_res = await client.get(
        f"/api/v1/repositories/{repo_id}/symbols?search=get_user",
        headers=auth_headers,
    )
    assert search_res.status_code == 200
    search_items = search_res.json()["items"]
    assert len(search_items) >= 1
    target_sym = search_items[0]
    assert "get_user_by_id" in target_sym["name"]
    assert target_sym["start_line"] > 0

    # 6. Test GET /symbols/{symbol_id}
    sym_id = target_sym["id"]
    detail_res = await client.get(
        f"/api/v1/repositories/{repo_id}/symbols/{sym_id}",
        headers=auth_headers,
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["name"] == "get_user_by_id"
    assert detail["is_async"] is True
    assert "user_id" in str(detail["parameters"])

    # 7. Test GET /endpoints
    endpoints_res = await client.get(
        f"/api/v1/repositories/{repo_id}/endpoints",
        headers=auth_headers,
    )
    assert endpoints_res.status_code == 200
    endpoints = endpoints_res.json()
    paths = [ep["path"] for ep in endpoints]
    assert "/users/{user_id}" in paths
    assert "/users" in paths

    # Filter endpoints by framework
    fastapi_eps = await client.get(
        f"/api/v1/repositories/{repo_id}/endpoints?framework=FastAPI",
        headers=auth_headers,
    )
    assert fastapi_eps.status_code == 200
    for ep in fastapi_eps.json():
        assert ep["framework"] == "FastAPI"

    # 8. Test Re-Analysis (Duplicate Prevention)
    # Re-running analysis must not double the symbol count
    first_count = overview["total_symbols"]
    reanalyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=auth_headers,
    )
    assert reanalyze_res.status_code == 200
    overview_again = (
        await client.get(
            f"/api/v1/repositories/{repo_id}/analysis",
            headers=auth_headers,
        )
    ).json()
    assert overview_again["total_symbols"] == first_count


@pytest.mark.asyncio
async def test_security_and_isolation(
    client: AsyncClient,
):
    token = await get_auth_token(client, "isolation_user@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Unauthenticated access
    res = await client.get("/api/v1/repositories/non-existent-id/symbols")
    assert res.status_code == 401

    # Non-existent repository
    res_auth = await client.get(
        "/api/v1/repositories/00000000-0000-0000-0000-000000000000/symbols",
        headers=auth_headers,
    )
    assert res_auth.status_code == 404

    # Non-existent symbol
    res_sym = await client.get(
        "/api/v1/repositories/00000000-0000-0000-0000-000000000000/symbols/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert res_sym.status_code == 404


def test_parser_edge_cases_and_false_positives():
    parser = PythonAstParser()

    # Route in a comment or string literal must NOT be detected as an API endpoint
    code_with_comment = """
# @app.get("/fake/endpoint")
fake_var = "router.post('/also/fake')"

def real_function():
    return True
"""
    res = parser.parse_source(code_with_comment)
    assert res.status == ParseStatus.SUCCESS
    assert len(res.endpoints) == 0
    assert len(res.symbols) == 1
    assert res.symbols[0].name == "real_function"

    # Circular import statements as static facts
    circular_code = """
from module_a import func_a
from module_b import func_b
"""
    res_circ = parser.parse_source(circular_code)
    assert res_circ.status == ParseStatus.SUCCESS
    assert len(res_circ.imports_exports) == 2


def test_large_source_file_handling():
    parser = PythonAstParser()
    # Generate 500 functions
    lines = []
    for i in range(500):
        lines.append(f"def func_{i}(x: int = {i}) -> int:\n    return x + {i}\n")
    huge_source = "\n".join(lines)

    res = parser.parse_source(huge_source)
    assert res.status == ParseStatus.SUCCESS
    assert len(res.symbols) == 500
    assert res.symbols[0].name == "func_0"
    assert res.symbols[499].name == "func_499"
