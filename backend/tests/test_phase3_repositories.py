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
async def test_repository_registration_validation(client: AsyncClient):
    token = await get_auth_token(client, "user1@repomind.ai")
    headers = {"Authorization": f"Bearer {token}"}

    # Invalid URL format
    res = await client.post(
        "/api/v1/repositories",
        json={"repository_url": "https://notgithub.com/someone/repo"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "Invalid GitHub repository URL" in res.json()["error"]["message"]

    # Valid GitHub URL
    res = await client.post(
        "/api/v1/repositories",
        json={"repository_url": "https://github.com/psf/requests"},
        headers=headers,
    )
    assert res.status_code == 201
    repo = res.json()
    assert repo["name"] == "requests"
    assert repo["owner"] == "psf"
    assert repo["repository_url"] == "https://github.com/psf/requests"
    assert repo["source_type"] == "github_public"

    # Duplicate registration should return 409 Conflict
    dup_res = await client.post(
        "/api/v1/repositories",
        json={"repository_url": "https://github.com/psf/requests"},
        headers=headers,
    )
    assert dup_res.status_code == 409
    assert "already connected" in dup_res.json()["error"]["message"]


@pytest.mark.asyncio
async def test_repository_ownership_isolation(client: AsyncClient):
    token_a = await get_auth_token(client, "alice@repomind.ai", "Alice")
    token_b = await get_auth_token(client, "bob@repomind.ai", "Bob")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Alice creates a repo
    create_res = await client.post(
        "/api/v1/repositories",
        json={"repository_url": "https://github.com/alice/project-a"},
        headers=headers_a,
    )
    assert create_res.status_code == 201
    repo_id = create_res.json()["id"]

    # Bob tries to view Alice's repo -> 403 Forbidden
    get_res = await client.get(f"/api/v1/repositories/{repo_id}", headers=headers_b)
    assert get_res.status_code == 403

    # Bob tries to update Alice's repo -> 403 Forbidden
    patch_res = await client.patch(
        f"/api/v1/repositories/{repo_id}",
        json={"name": "hacked-name"},
        headers=headers_b,
    )
    assert patch_res.status_code == 403

    # Bob tries to delete Alice's repo -> 403 Forbidden
    del_res = await client.delete(f"/api/v1/repositories/{repo_id}", headers=headers_b)
    assert del_res.status_code == 403

    # Alice can update her repo
    update_res = await client.patch(
        f"/api/v1/repositories/{repo_id}",
        json={"description": "Updated description", "default_branch": "develop"},
        headers=headers_a,
    )
    assert update_res.status_code == 200
    assert update_res.json()["description"] == "Updated description"
    assert update_res.json()["default_branch"] == "develop"

    # Alice can delete her repo
    del_res_a = await client.delete(f"/api/v1/repositories/{repo_id}", headers=headers_a)
    assert del_res_a.status_code == 200
    assert del_res_a.json()["message"] == "Repository successfully deleted"


@pytest.mark.asyncio
async def test_unauthorized_requests(client: AsyncClient):
    # Without Bearer token -> 401
    res = await client.get("/api/v1/repositories")
    assert res.status_code == 401

