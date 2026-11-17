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
async def test_architecture_api_endpoints_end_to_end(client: AsyncClient):
    token = await get_auth_token(client, "arch_tester@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload a repository with multiple layers
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "src/features/auth/LoginPage.tsx",
            """import React from 'react';
import { authService } from '../../services/authService';
export function LoginPage() {
    return <div>Login</div>;
}
""",
        )
        zf.writestr(
            "src/services/authService.ts",
            """export const authService = {
    login: async () => fetch('/api/v1/auth/login')
};
""",
        )
        zf.writestr(
            "backend/app/api/auth.py",
            """from fastapi import APIRouter
from app.services.auth_service import AuthService
router = APIRouter()
@router.post('/login')
def login_endpoint():
    return AuthService().authenticate()
""",
        )
        zf.writestr(
            "backend/app/services/auth_service.py",
            """from app.models.user import User
class AuthService:
    def authenticate(self):
        return True
""",
        )
        zf.writestr(
            "backend/app/models/user.py",
            """class User:
    id: int
    email: str
""",
        )

    zip_buffer.seek(0)
    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=auth_headers,
        files={"file": ("project.zip", zip_buffer.getvalue(), "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Trigger static analysis
    analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=auth_headers,
    )
    assert analyze_res.status_code == 200

    # 3. Retrieve architecture graph
    graph_res = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/graph",
        headers=auth_headers,
    )
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert graph_data["repositoryId"] == repo_id
    assert len(graph_data["nodes"]) >= 5
    assert len(graph_data["edges"]) >= 2

    # Check 6 canonical view modes
    views = graph_data["views"]
    for vm in ("system", "frontend", "backend", "api", "database", "modules"):
        assert vm in views
        assert views[vm]["viewMode"] == vm
        assert "nodes" in views[vm]
        assert "edges" in views[vm]

    # 4. Retrieve specific view slice
    fe_res = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/views/frontend",
        headers=auth_headers,
    )
    assert fe_res.status_code == 200
    fe_data = fe_res.json()
    assert fe_data["viewMode"] == "frontend"
    assert any("LoginPage" in n["label"] for n in fe_data["nodes"])

    # 5. Retrieve node details
    sample_node_id = graph_data["nodes"][0]["id"]
    node_res = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/nodes/{sample_node_id}",
        headers=auth_headers,
    )
    assert node_res.status_code == 200
    node_detail = node_res.json()
    assert node_detail["node"]["id"] == sample_node_id
    assert "incomingRelationships" in node_detail
    assert "outgoingRelationships" in node_detail


@pytest.mark.asyncio
async def test_architecture_unauthorized_access(client: AsyncClient):
    token1 = await get_auth_token(client, "user1@repomind.ai")
    token2 = await get_auth_token(client, "user2@repomind.ai")

    # User 1 uploads
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("main.py", "print('hello')")
    zip_buffer.seek(0)

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers={"Authorization": f"Bearer {token1}"},
        files={"file": ("project.zip", zip_buffer.getvalue(), "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # User 2 tries to access User 1's architecture graph
    forbidden_res = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/graph",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert forbidden_res.status_code == 403
