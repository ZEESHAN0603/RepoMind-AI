import io
import zipfile
import pytest
from httpx import AsyncClient


async def get_auth_token(client: AsyncClient, email: str, name: str = "Update Tester") -> str:
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
async def test_update_intelligence_endpoints_end_to_end(client: AsyncClient):
    token = await get_auth_token(client, "updater@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a test repository
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", "# Test Update Repo\n")
        zf.writestr(
            "app/service.py",
            """def calculate(a: int, b: int) -> int:
    return a + b
""",
        )
    zip_buffer.seek(0)

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=auth_headers,
        files={"file": ("update_test_repo.zip", zip_buffer.getvalue(), "application/zip")},
        data={"name": "Update Test Repo"},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Query empty update history
    hist_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/history",
        headers=auth_headers,
    )
    assert hist_res.status_code == 200
    hist_data = hist_res.json()
    assert hist_data["repository_id"] == repo_id
    assert hist_data["total_runs"] == 0

    # 3. Trigger update analysis
    analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/updates/analyze",
        headers=auth_headers,
        json={"include_ai_summary": True},
    )
    assert analyze_res.status_code == 201
    run_data = analyze_res.json()
    assert "id" in run_data
    update_run_id = run_data["id"]

    # 4. Fetch update run details
    detail_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}",
        headers=auth_headers,
    )
    assert detail_res.status_code == 200
    detail_data = detail_res.json()
    assert detail_data["id"] == update_run_id
    assert "stats" in detail_data
    assert "impact_metrics" in detail_data

    # 5. Fetch changed files
    files_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/files",
        headers=auth_headers,
    )
    assert files_res.status_code == 200
    assert isinstance(files_res.json(), list)

    # 6. Fetch changed symbols
    symbols_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/symbols",
        headers=auth_headers,
    )
    assert symbols_res.status_code == 200
    assert isinstance(symbols_res.json(), list)

    # 7. Fetch impact records
    impact_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/impact",
        headers=auth_headers,
    )
    assert impact_res.status_code == 200
    assert isinstance(impact_res.json(), list)

    # 8. Fetch impact graph
    graph_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/graph",
        headers=auth_headers,
    )
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data

    # 9. Test ad-hoc compare endpoint
    compare_res = await client.post(
        f"/api/v1/repositories/{repo_id}/updates/compare",
        headers=auth_headers,
        json={"target_commit_sha": "a1b2c3d", "include_ai_summary": False},
    )
    assert compare_res.status_code == 200
    comp_data = compare_res.json()
    assert comp_data["target_commit_sha"] == "a1b2c3d"

    # 10. Authorization check: other user cannot access repo update history
    other_token = await get_auth_token(client, "intruder@repomind.ai", "Intruder")
    forbidden_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/history",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert forbidden_res.status_code == 403
