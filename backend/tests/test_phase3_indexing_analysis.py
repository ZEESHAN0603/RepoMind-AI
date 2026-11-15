import io
import json
from pathlib import Path
import pytest
from httpx import AsyncClient

from app.models.repository_file import RepositoryFile
from app.services.detection_service import TechnologyDetectionService
from app.services.discovery_service import DiscoveryService


def test_discovery_and_exclusions(tmp_path: Path):
    # Setup test workspace structure
    workspace = tmp_path / "repo_test"
    workspace.mkdir()
    (workspace / "src").mkdir()
    (workspace / "node_modules").mkdir()
    (workspace / ".git").mkdir()
    (workspace / "__pycache__").mkdir()

    # Valid files
    (workspace / "src" / "index.ts").write_text("console.log('hi');", encoding="utf-8")
    (workspace / "src" / "styles.css").write_text("body { color: red; }", encoding="utf-8")
    (workspace / "README.md").write_text("# Doc", encoding="utf-8")

    # Files that should be ignored
    (workspace / "node_modules" / "bad.js").write_text("bad", encoding="utf-8")
    (workspace / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    (workspace / "__pycache__" / "cached.pyc").write_bytes(b"\x00\x01\x02")

    # Binary file with null bytes
    (workspace / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    entities, file_count, folder_count, total_bytes = DiscoveryService.discover_repository(
        workspace_dir=workspace,
        repository_id="dummy-repo-id",
    )

    paths = [e.path for e in entities]

    # Verify exclusions worked
    assert not any("node_modules" in p for p in paths)
    assert not any(".git" in p for p in paths)
    assert not any("__pycache__" in p for p in paths)

    # Verify discovered files
    assert "src/index.ts" in paths
    assert "src/styles.css" in paths
    assert "README.md" in paths
    assert "logo.png" in paths

    # Verify binary classification
    png_file = next(e for e in entities if e.path == "logo.png")
    assert png_file.is_binary is True

    ts_file = next(e for e in entities if e.path == "src/index.ts")
    assert ts_file.is_binary is False
    assert ts_file.language == "TypeScript"


def test_technology_and_framework_detection(tmp_path: Path):
    workspace = tmp_path / "detect_test"
    workspace.mkdir()

    # Write package.json with React and Tailwind
    package_json = {
        "name": "frontend-app",
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
        },
        "devDependencies": {
            "tailwindcss": "^3.0.0",
            "vite": "^5.0.0",
        },
    }
    (workspace / "package.json").write_text(json.dumps(package_json), encoding="utf-8")

    # Write requirements.txt with FastAPI and SQLAlchemy
    reqs = "fastapi>=0.110.0\nsqlalchemy>=2.0.0\nuvicorn\n"
    (workspace / "requirements.txt").write_text(reqs, encoding="utf-8")

    manifests = TechnologyDetectionService.detect_manifests(workspace, "dummy-id")
    assert len(manifests) == 2

    # Verify package.json frameworks
    pkg_manifest = next(m for m in manifests if m.manifest_type == "package.json")
    fw_list = json.loads(pkg_manifest.detected_frameworks)
    assert "React" in fw_list
    assert "Tailwind CSS" in fw_list
    assert "Vite" in fw_list

    # Verify requirements.txt frameworks
    py_manifest = next(m for m in manifests if m.manifest_type == "requirements.txt")
    py_fw = json.loads(py_manifest.detected_frameworks)
    assert "FastAPI" in py_fw
    assert "SQLAlchemy" in py_fw


def test_language_distribution_calculation():
    files = [
        RepositoryFile(repository_id="1", path="a.py", name="a.py", file_type="file", size_bytes=700, is_binary=False, language="Python"),
        RepositoryFile(repository_id="1", path="b.ts", name="b.ts", file_type="file", size_bytes=300, is_binary=False, language="TypeScript"),
        RepositoryFile(repository_id="1", path="img.png", name="img.png", file_type="file", size_bytes=5000, is_binary=True, language=None),
    ]

    dist = TechnologyDetectionService.calculate_language_distribution(files, "1")
    assert len(dist) == 2
    assert dist[0].language == "Python"
    assert dist[0].percentage == 70.0
    assert dist[1].language == "TypeScript"
    assert dist[1].percentage == 30.0


@pytest.mark.asyncio
async def test_full_ingestion_api_flow(client: AsyncClient):
    # Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Ingest Tester", "email": "ingest@repomind.ai", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "ingest@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Connect repo (triggers background pipeline)
    create_res = await client.post(
        "/api/v1/repositories",
        json={"repository_url": "https://github.com/mock-org/sample-app"},
        headers=headers,
    )
    assert create_res.status_code == 201
    repo_id = create_res.json()["id"]

    # 2. Check jobs endpoint
    jobs_res = await client.get(f"/api/v1/repositories/{repo_id}/jobs", headers=headers)
    assert jobs_res.status_code == 200
    jobs = jobs_res.json()
    assert len(jobs) >= 1
    job_id = jobs[0]["id"]

    # 3. Check individual job
    job_res = await client.get(f"/api/v1/repositories/{repo_id}/jobs/{job_id}", headers=headers)
    assert job_res.status_code == 200
    assert job_res.json()["id"] == job_id

    # 4. Check file tree endpoint
    files_res = await client.get(f"/api/v1/repositories/{repo_id}/files", headers=headers)
    assert files_res.status_code == 200
    files_tree = files_res.json()
    assert isinstance(files_tree, list)

    # 5. Check branches endpoint
    branches_res = await client.get(f"/api/v1/repositories/{repo_id}/branches", headers=headers)
    assert branches_res.status_code == 200
    branches = branches_res.json()
    assert len(branches) >= 1

    # 6. Check repository overview endpoint
    overview_res = await client.get(f"/api/v1/repositories/{repo_id}/overview", headers=headers)
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert "repository" in overview
    assert "languages" in overview
    assert "manifests" in overview

    # 7. Test re-sync endpoint
    sync_res = await client.post(f"/api/v1/repositories/{repo_id}/sync", headers=headers)
    assert sync_res.status_code == 200
    sync_job = sync_res.json()
    assert sync_job["repository_id"] == repo_id

