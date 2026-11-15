import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_user_registration_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test Engineer",
            "email": "engineer@repomind.ai",
            "password": "SecurePassword123!",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["full_name"] == "Test Engineer"
    assert data["email"] == "engineer@repomind.ai"
    assert data["is_active"] is True
    assert "password" not in data
    assert "password_hash" not in data


@pytest.mark.asyncio
async def test_user_registration_duplicate_email(client: AsyncClient):
    payload = {
        "full_name": "Duplicate User",
        "email": "duplicate@repomind.ai",
        "password": "Password123!",
    }
    # First registration
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration with same email
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409
    data = res2.json()
    assert data["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_user_registration_invalid_email(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Invalid Email",
            "email": "not-an-email",
            "password": "Password123!",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_user_registration_weak_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Weak Pwd",
            "email": "weak@repomind.ai",
            "password": "short",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_user_login_success(client: AsyncClient):
    # Register user first
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Login User",
            "email": "login@repomind.ai",
            "password": "StrongPassword123!",
        },
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@repomind.ai",
            "password": "StrongPassword123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_user_login_invalid_password(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Wrong Pwd User",
            "email": "wrongpwd@repomind.ai",
            "password": "StrongPassword123!",
        },
    )

    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "wrongpwd@repomind.ai",
            "password": "WrongPassword!",
        },
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_user_login_nonexistent_user(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "ghost@repomind.ai",
            "password": "SomePassword123!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_me_protected_endpoint(client: AsyncClient):
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Protected User",
            "email": "protected@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "protected@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]

    # Access /api/v1/auth/me with Bearer token
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == "protected@repomind.ai"
    assert data["full_name"] == "Protected User"


@pytest.mark.asyncio
async def test_auth_me_unauthorized_without_token(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_refresh_token_flow_and_rotation(client: AsyncClient):
    # Register and login
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Refresh User",
            "email": "refresh@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@repomind.ai", "password": "Password123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Refresh
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert "access_token" in new_tokens
    assert "refresh_token" in new_tokens
    assert new_tokens["refresh_token"] != refresh_token

    # Reusing the old refresh token must be rejected (Token Rotation)
    reuse_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_res.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(client: AsyncClient):
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Logout User",
            "email": "logout@repomind.ai",
            "password": "Password123!",
        },
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@repomind.ai", "password": "Password123!"},
    )
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Successfully logged out"

    # Attempting to refresh with the revoked token must fail
    fail_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert fail_res.status_code == 401

