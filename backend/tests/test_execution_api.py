import io
import json
import zipfile
import pytest
from httpx import AsyncClient


def create_sample_zip() -> io.BytesIO:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        auth_code = """
import logging

def verify_token(token: str) -> bool:
    return len(token) > 5

class AuthService:
    def login(self, username: str, password: str):
        if not self.validate_password(password):
            return None
        return self.create_token(username)

    def validate_password(self, password: str) -> bool:
        return len(password) >= 8

    def create_token(self, username: str) -> str:
        return "tok_" + username
"""
        z.writestr("app/services/auth.py", auth_code)

        api_code = """
from app.services.auth import AuthService

def login_endpoint(user: str, pwd: str):
    service = AuthService()
    return service.login(user, pwd)
"""
        z.writestr("app/api/auth.py", api_code)
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_execution_api_full_workflow(client: AsyncClient):
    # 1. Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Exec Tester", "email": "exec@repomind.ai", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "exec@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload repository ZIP
    zip_buf = create_sample_zip()
    upload_res = await client.post(
        "/api/v1/repositories/upload",
        files={"file": ("test_exec.zip", zip_buf, "application/zip")},
        headers=headers,
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 3. Trigger static code intelligence analysis first
    ci_res = await client.post(f"/api/v1/repositories/{repo_id}/analyze", headers=headers)
    assert ci_res.status_code == 200

    # 4. Trigger execution flow analysis
    exec_res = await client.post(f"/api/v1/repositories/{repo_id}/execution/analyze", headers=headers)
    assert exec_res.status_code == 200
    summary = exec_res.json()
    assert summary["repository_id"] == repo_id
    assert summary["calls_extracted"] >= 1
    assert summary["traces_generated"] >= 1

    # 5. Fetch execution workspace
    ws_res = await client.get(f"/api/v1/repositories/{repo_id}/execution/workspace", headers=headers)
    assert ws_res.status_code == 200
    ws_data = ws_res.json()
    assert ws_data["repositoryId"] == repo_id
    assert len(ws_data["functions"]) >= 3
    assert len(ws_data["traces"]) >= 1

    first_trace = ws_data["traces"][0]
    assert "flow" in first_trace
    assert "nodes" in first_trace
    assert "edges" in first_trace
    assert len(first_trace["nodes"]) >= 1

    # 6. List entry points
    eps_res = await client.get(f"/api/v1/repositories/{repo_id}/execution/entry-points", headers=headers)
    assert eps_res.status_code == 200
    eps_data = eps_res.json()
    assert eps_data["total_count"] >= 1

    # 7. Get node calls for a function symbol
    sample_sym = ws_data["functions"][0]
    node_calls_res = await client.get(
        f"/api/v1/repositories/{repo_id}/execution/nodes/{sample_sym['id']}/calls",
        headers=headers,
    )
    assert node_calls_res.status_code == 200
    calls_data = node_calls_res.json()
    assert calls_data["symbol_id"] == sample_sym["id"]
    assert "incoming" in calls_data
    assert "outgoing" in calls_data

    # 8. Test execution path trace
    if len(ws_data["functions"]) >= 2:
        src_id = ws_data["functions"][0]["id"]
        tgt_id = ws_data["functions"][1]["id"]
        path_res = await client.get(
            f"/api/v1/repositories/{repo_id}/execution/trace-path?source_symbol_id={src_id}&target_symbol_id={tgt_id}",
            headers=headers,
        )
        assert path_res.status_code == 200
        path_data = path_res.json()
        assert "path_found" in path_data

    # 9. Test AI explanation endpoint
    explain_res = await client.post(
        f"/api/v1/repositories/{repo_id}/execution/explain",
        json={"flowId": first_trace["flow"]["id"], "focusQuestion": "How does login authenticate?"},
        headers=headers,
    )
    assert explain_res.status_code == 200
    explain_data = explain_res.json()
    assert "summary" in explain_data
    assert "verifiedSteps" in explain_data
    assert "uncertainties" in explain_data
    assert "providerUsed" in explain_data


@pytest.mark.asyncio
async def test_execution_api_security_isolation(client: AsyncClient):
    # Register user 1
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User 1", "email": "user1@repomind.ai", "password": "Password123!"},
    )
    u1_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user1@repomind.ai", "password": "Password123!"},
    )
    token1 = u1_login.json()["access_token"]

    # Register user 2
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User 2", "email": "user2@repomind.ai", "password": "Password123!"},
    )
    u2_login = await client.post(
        "/api/v1/auth/login",
        json={"email": "user2@repomind.ai", "password": "Password123!"},
    )
    token2 = u2_login.json()["access_token"]

    # User 1 uploads repo
    zip_buf = create_sample_zip()
    upload_res = await client.post(
        "/api/v1/repositories/upload",
        files={"file": ("u1_repo.zip", zip_buf, "application/zip")},
        headers={"Authorization": f"Bearer {token1}"},
    )
    repo_id = upload_res.json()["id"]

    # User 2 tries to access User 1's execution workspace -> 403 Forbidden
    forbidden_res = await client.get(
        f"/api/v1/repositories/{repo_id}/execution/workspace",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert forbidden_res.status_code == 403

    # Non-existent repo -> 404
    notfound_res = await client.get(
        "/api/v1/repositories/00000000-0000-0000-0000-000000000000/execution/workspace",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert notfound_res.status_code == 404
