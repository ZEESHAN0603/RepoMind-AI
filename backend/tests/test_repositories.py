import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_repository_crud(client: AsyncClient):
    # Register and login user
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Repo Owner",
            "email": "repoowner@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "repoowner@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Connect repository
    create_res = await client.post(
        "/api/v1/repositories",
        json={
            "name": "fastapi",
            "owner": "tiangolo",
            "repository_url": "https://github.com/tiangolo/fastapi",
            "source_type": "github_public",
            "default_branch": "master",
            "visibility": "public",
        },
        headers=auth_headers,
    )
    assert create_res.status_code == 201
    repo_data = create_res.json()
    assert repo_data["name"] == "fastapi"
    assert repo_data["status"] == "connected"
    repo_id = repo_data["id"]

    # 2. List repositories
    list_res = await client.get("/api/v1/repositories", headers=auth_headers)
    assert list_res.status_code == 200
    repos = list_res.json()
    assert len(repos) >= 1
    assert any(r["id"] == repo_id for r in repos)

    # 3. Get repository by ID
    get_res = await client.get(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "fastapi"

    # 4. Delete repository
    del_res = await client.delete(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Repository successfully deleted"

    # 5. Verify deletion
    verify_res = await client.get(f"/api/v1/repositories/{repo_id}", headers=auth_headers)
    assert verify_res.status_code == 404

