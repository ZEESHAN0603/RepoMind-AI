import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

from app.core.config import settings
from app.core.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
)
from app.core.logging import logger


class GitHubService:
    """Handles communication with the GitHub REST API and repository retrieval."""

    GITHUB_API_BASE = "https://api.github.com"
    URL_REGEX = re.compile(
        r"^(?:https?://)?(?:www\.)?github\.com/(?P<owner>[a-zA-Z0-9_\-\.]+)/(?P<repo>[a-zA-Z0-9_\-\.]+?)(?:\.git)?/?$"
    )
    SSH_REGEX = re.compile(
        r"^git@github\.com:(?P<owner>[a-zA-Z0-9_\-\.]+)/(?P<repo>[a-zA-Z0-9_\-\.]+?)(?:\.git)?$"
    )

    @classmethod
    def parse_github_url(cls, url: str) -> Tuple[str, str]:
        """
        Parses and validates a GitHub URL.
        Returns: (owner, repository_name)
        Raises: BadRequestException if format is invalid.
        """
        if not url:
            raise BadRequestException("Repository URL cannot be empty")

        url_clean = url.strip()
        match = cls.URL_REGEX.match(url_clean) or cls.SSH_REGEX.match(url_clean)
        if not match:
            raise BadRequestException(
                "Invalid GitHub repository URL. Expected format: https://github.com/owner/repository"
            )

        owner = match.group("owner")
        repo = match.group("repo")
        if repo.endswith(".git"):
            repo = repo[:-4]

        return owner, repo

    @classmethod
    def _get_headers(cls, access_token: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "RepoMind-Ingestion-Platform",
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        return headers

    @classmethod
    async def get_repository_metadata(
        cls,
        owner: str,
        repo: str,
        access_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetches repository metadata from the GitHub REST API."""
        url = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}"
        headers = cls._get_headers(access_token)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=headers)
        except httpx.RequestError as e:
            logger.error("GitHub API network failure: %s", e)
            raise BadRequestException(f"Network error while connecting to GitHub: {str(e)}")

        if res.status_code == 200:
            data = res.json()
            return {
                "name": data.get("name", repo),
                "owner": data.get("owner", {}).get("login", owner),
                "full_name": data.get("full_name", f"{owner}/{repo}"),
                "default_branch": data.get("default_branch", "main"),
                "visibility": "private" if data.get("private") else "public",
                "is_private": data.get("private", False),
                "is_archived": data.get("archived", False),
                "description": data.get("description"),
                "size_kb": data.get("size", 0),
                "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
            }
        elif res.status_code == 404:
            if not access_token:
                raise NotFoundException(
                    f"GitHub repository '{owner}/{repo}' was not found. If this is a private repository, please connect your GitHub account."
                )
            raise NotFoundException(f"GitHub repository '{owner}/{repo}' not found or you lack permission.")
        elif res.status_code in (401, 403):
            # Check rate limiting
            remaining = res.headers.get("x-ratelimit-remaining")
            if remaining == "0":
                raise BadRequestException("GitHub API rate limit exceeded. Please try again later.")
            raise ForbiddenException("Access to this GitHub repository is unauthorized. Please check permissions.")
        else:
            raise BadRequestException(f"GitHub API error: status {res.status_code}")

    @classmethod
    async def get_repository_branches(
        cls,
        owner: str,
        repo: str,
        access_token: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves list of branches for a repository."""
        url = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}/branches?per_page=100"
        headers = cls._get_headers(access_token)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=headers)
        except httpx.RequestError as e:
            logger.error("GitHub branches network error: %s", e)
            return []

        if res.status_code != 200:
            return []

        branches = []
        for b in res.json():
            branches.append({
                "name": b.get("name"),
                "commit_sha": b.get("commit", {}).get("sha"),
            })
        return branches

    @classmethod
    async def get_latest_commit_sha(
        cls,
        owner: str,
        repo: str,
        branch: str,
        access_token: Optional[str] = None,
    ) -> Optional[str]:
        """Retrieves latest commit SHA for a specific branch."""
        url = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}/commits/{branch}"
        headers = cls._get_headers(access_token)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.json().get("sha")
        except Exception as e:
            logger.warning("Failed to fetch commit SHA: %s", e)
        return None

    @classmethod
    async def download_archive(
        cls,
        owner: str,
        repo: str,
        branch: str,
        destination_zip_path: Path,
        access_token: Optional[str] = None,
    ) -> Path:
        """
        Streams repository zipball archive to a file.
        Enforces maximum download size limit to avoid infinite stream attacks.
        """
        url = f"{cls.GITHUB_API_BASE}/repos/{owner}/{repo}/zipball/{branch}"
        headers = cls._get_headers(access_token)
        headers["Accept"] = "application/vnd.github.v3+json"

        max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
        downloaded = 0

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 404:
                        raise NotFoundException(f"Branch '{branch}' or repository '{owner}/{repo}' not found.")
                    if response.status_code in (401, 403):
                        raise ForbiddenException("Unauthorized to download repository contents.")
                    if response.status_code != 200:
                        raise BadRequestException(f"Failed to download repository: HTTP {response.status_code}")

                    destination_zip_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(destination_zip_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            downloaded += len(chunk)
                            if downloaded > max_bytes:
                                raise BadRequestException(
                                    f"Repository archive exceeds maximum download limit of {max_bytes // (1024 * 1024)} MB"
                                )
                            f.write(chunk)
            return destination_zip_path
        except Exception as e:
            if destination_zip_path.exists():
                destination_zip_path.unlink(missing_ok=True)
            if isinstance(e, (BadRequestException, ForbiddenException, NotFoundException)):
                raise
            raise BadRequestException(f"Failed to download GitHub repository archive: {e}")

    # GitHub OAuth support
    @classmethod
    def get_oauth_authorization_url(cls, state: str) -> str:
        """Constructs GitHub OAuth2 authorization URL with minimum required scopes."""
        client_id = settings.GITHUB_CLIENT_ID
        if not client_id:
            # Fallback for development if client id is not configured
            client_id = "repomind-dev-client"
        return (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={client_id}"
            f"&scope=repo,read:user"
            f"&state={state}"
        )

    @classmethod
    async def exchange_oauth_code(cls, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for GitHub access token."""
        url = "https://github.com/login/oauth/access_token"
        payload = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "client_secret": settings.GITHUB_CLIENT_SECRET,
            "code": code,
        }
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code != 200:
                raise BadRequestException("Failed to exchange OAuth code with GitHub")
            data = res.json()
            if "error" in data:
                raise BadRequestException(f"GitHub OAuth error: {data.get('error_description') or data['error']}")
            return data

    @classmethod
    async def get_authenticated_user(cls, access_token: str) -> Dict[str, Any]:
        """Fetches profile of the authenticated GitHub user."""
        url = f"{cls.GITHUB_API_BASE}/user"
        headers = cls._get_headers(access_token)

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                raise UnauthorizedException("Invalid or revoked GitHub access token")
            return res.json()

