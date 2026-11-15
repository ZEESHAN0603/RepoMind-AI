import secrets
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.crypto import encrypt_secret
from app.core.exceptions import BadRequestException
from app.db.session import get_db
from app.models.user import User
from app.repositories.github_connection_repository import GitHubConnectionRepository
from app.schemas.repository import GitHubConnectUrlResponse, GitHubStatusResponse
from app.schemas.token import MessageResponse
from app.services.github_service import GitHubService

router = APIRouter()


@router.get(
    "/connect",
    response_model=GitHubConnectUrlResponse,
    summary="Get GitHub OAuth authorization URL",
    description="Generates an OAuth authorization link to connect a GitHub account for private repository access.",
)
async def get_github_connect_url(
    current_user: User = Depends(get_current_user),
) -> GitHubConnectUrlResponse:
    state = f"{current_user.id}:{secrets.token_urlsafe(16)}"
    auth_url = GitHubService.get_oauth_authorization_url(state)
    return GitHubConnectUrlResponse(authorization_url=auth_url)


@router.get(
    "/callback",
    response_model=GitHubStatusResponse,
    summary="GitHub OAuth callback",
    description="Receives code from GitHub OAuth redirect, securely exchanges and encrypts access token.",
)
async def github_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitHubStatusResponse:
    # Validate state prefix matches current user
    if not state.startswith(f"{current_user.id}:"):
        raise BadRequestException("Invalid or forged OAuth state parameter")

    # Exchange code for access token
    token_data = await GitHubService.exchange_oauth_code(code)
    access_token = token_data.get("access_token")
    if not access_token:
        raise BadRequestException("No access token returned by GitHub")

    scope = token_data.get("scope", "")

    # Fetch GitHub user profile
    gh_user = await GitHubService.get_authenticated_user(access_token)
    gh_username = gh_user.get("login")
    gh_user_id = str(gh_user.get("id"))

    # Encrypt token at rest
    encrypted_token = encrypt_secret(access_token)

    # Save to database
    conn_repo = GitHubConnectionRepository(db)
    conn = await conn_repo.upsert(
        user_id=current_user.id,
        github_user_id=gh_user_id,
        github_username=gh_username,
        encrypted_token=encrypted_token,
        scope=scope,
    )

    return GitHubStatusResponse(
        is_connected=True,
        github_username=conn.github_username,
        scope=conn.scope,
        connected_at=conn.updated_at,
    )


@router.get(
    "/status",
    response_model=GitHubStatusResponse,
    summary="Check GitHub connection status",
    description="Returns whether the authenticated user has an active connected GitHub account.",
)
async def get_github_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GitHubStatusResponse:
    conn_repo = GitHubConnectionRepository(db)
    conn = await conn_repo.get_by_user_id(current_user.id)
    if not conn or not conn.encrypted_access_token:
        return GitHubStatusResponse(is_connected=False)

    return GitHubStatusResponse(
        is_connected=True,
        github_username=conn.github_username,
        scope=conn.scope,
        connected_at=conn.updated_at,
    )


@router.delete(
    "/disconnect",
    response_model=MessageResponse,
    summary="Disconnect GitHub account",
    description="Revokes stored GitHub connection and deletes credentials for the current user.",
)
async def disconnect_github(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    conn_repo = GitHubConnectionRepository(db)
    deleted = await conn_repo.delete_by_user_id(current_user.id)
    if not deleted:
        return MessageResponse(message="No active GitHub connection to disconnect")
    return MessageResponse(message="GitHub account successfully disconnected")

