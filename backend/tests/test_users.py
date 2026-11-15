import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Profile User",
            "email": "profile@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "profile@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "profile@repomind.ai"
    assert data["full_name"] == "Profile User"


@pytest.mark.asyncio
async def test_update_user_profile(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Before Update",
            "email": "update@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "update@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    # Update name
    patch_res = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "After Update"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["full_name"] == "After Update"


@pytest.mark.asyncio
async def test_update_email_duplicate_conflict(client: AsyncClient):
    # Register user 1
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User One", "email": "user1@repomind.ai", "password": "Password123!"},
    )
    # Register user 2
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "User Two", "email": "user2@repomind.ai", "password": "Password123!"},
    )
    login2 = await client.post(
        "/api/v1/auth/login",
        json={"email": "user2@repomind.ai", "password": "Password123!"},
    )
    token2 = login2.json()["access_token"]

    # Try to update user 2's email to user 1's email
    patch_res = await client.patch(
        "/api/v1/users/me",
        json={"email": "user1@repomind.ai"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_delete_user_account(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Delete Me",
            "email": "delete@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "delete@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    # Delete account
    del_res = await client.delete(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["message"] == "Account successfully deleted"

    # Profile should no longer be accessible
    get_res = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_res.status_code == 401

