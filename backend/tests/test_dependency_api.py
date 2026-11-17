import io
import zipfile
import pytest
from httpx import AsyncClient


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
async def test_dependency_api_endpoints_end_to_end(client: AsyncClient):
    token = await get_auth_token(client, "dep_tester@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a repository with a circular dependency (A <-> B) and third-party import
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            "# Test Repo\n",
        )
        zf.writestr(
            "app/module_a.py",
            """from .module_b import func_b
import requests

def func_a():
    return func_b()
""",
        )
        zf.writestr(
            "app/module_b.py",
            """from .module_a import func_a

def func_b():
    return func_a()
""",
        )
        zf.writestr(
            "app/standalone.py",
            """import math
def compute():
    return math.sqrt(16)
""",
        )
    zip_buffer.seek(0)

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=auth_headers,
        files={"file": ("dep_repo.zip", zip_buffer.getvalue(), "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Trigger static analysis first so CodeImportExport records are populated
    analysis_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=auth_headers,
    )
    assert analysis_res.status_code == 200

    # 3. GET /dependencies/graph
    graph_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/graph",
        headers=auth_headers,
    )
    assert graph_res.status_code == 200
    graph_data = graph_res.json()

    assert "repositoryId" in graph_data
    assert "nodes" in graph_data
    assert "relationships" in graph_data
    assert "cycles" in graph_data
    assert graph_data["circularCount"] >= 1
    assert graph_data["externalCount"] >= 1  # requests

    # 4. GET /dependencies/cycles
    cycles_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/cycles",
        headers=auth_headers,
    )
    assert cycles_res.status_code == 200
    cycles = cycles_res.json()
    assert len(cycles) >= 1
    assert any("module_a" in str(c["cyclePath"]) and "module_b" in str(c["cyclePath"]) for c in cycles)

    # 5. GET /dependencies/direct
    direct_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/direct",
        params={"file_path": "app/module_a.py", "direction": "both"},
        headers=auth_headers,
    )
    assert direct_res.status_code == 200
    direct_data = direct_res.json()
    assert direct_data["count"] >= 1

    # 6. GET /dependencies/transitive
    trans_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/transitive",
        params={"file_path": "app/module_a.py", "max_depth": 3},
        headers=auth_headers,
    )
    assert trans_res.status_code == 200
    trans_data = trans_res.json()
    assert "reachableNodes" in trans_data

    # 7. GET /dependencies/packages
    pkg_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/packages",
        headers=auth_headers,
    )
    assert pkg_res.status_code == 200
    pkg_data = pkg_res.json()
    assert "packages" in pkg_data

    # 8. POST /dependencies/analyze (force refresh)
    reanalyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/dependencies/analyze",
        headers=auth_headers,
    )
    assert reanalyze_res.status_code == 200
    assert reanalyze_res.json()["circularCount"] >= 1

    # 9. Verify repository isolation
    other_token = await get_auth_token(client, "other_dep_user@repomind.ai")
    other_headers = {"Authorization": f"Bearer {other_token}"}
    forbidden_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/graph",
        headers=other_headers,
    )
    assert forbidden_res.status_code == 403
