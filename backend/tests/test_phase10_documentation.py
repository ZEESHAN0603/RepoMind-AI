import io
import zipfile
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository
from app.models.repository_document import RepositoryDocument
from app.repositories.documentation_repository import DocumentationRepository
from app.services.documentation_export_service import DocumentationExportService
from app.services.documentation_generation_service import DocumentationGenerationService


async def get_auth_token(client: AsyncClient, email: str, name: str = "Doc Tester") -> str:
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
async def test_documentation_export_service():
    """Validates markdown, html, and zip package export utilities."""
    doc = RepositoryDocument(
        id="test-doc-1",
        repository_id="test-repo-1",
        doc_type="readme",
        title="README Overview",
        description="Project description",
        content="# Test Repository\n\nWelcome to test documentation.",
        status="approved",
        confidence="verified",
        version_number=1,
    )
    repo = Repository(
        id="test-repo-1",
        name="Test Gateway",
        owner="test-owner",
        repository_url="https://github.com/test/gateway",
    )

    # 1. Markdown export
    md_bytes, md_filename = DocumentationExportService.export_as_markdown(doc)
    assert md_filename == "readme.md"
    assert b"# Test Repository" in md_bytes

    # 2. HTML export
    html_bytes, html_filename = DocumentationExportService.export_as_html(doc, repo)
    assert html_filename == "readme.html"
    assert b"<!DOCTYPE html>" in html_bytes
    assert b"mermaid" in html_bytes

    # 3. ZIP package export
    zip_bytes, zip_filename = DocumentationExportService.export_as_zip_package(repo, [doc])
    assert zip_filename == "test-gateway-documentation.zip"
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        namelist = zf.namelist()
        assert any("readme.md" in n for n in namelist)
        assert any("INDEX.md" in n for n in namelist)


@pytest.mark.asyncio
async def test_documentation_repository_operations(db_session: AsyncSession):
    """Validates document persistence, versioning, and approval workflows."""
    doc_repo = DocumentationRepository(db_session)
    repo_id = "repo-unit-test-123"

    # 1. Save new document
    saved = await doc_repo.save_or_update_document(
        repository_id=repo_id,
        doc_type="architecture",
        title="System Architecture",
        description="Architecture specification",
        content="# Architecture\n\nService layer description.",
        status="draft",
        confidence="verified",
        change_summary="Initial architecture generation",
    )
    await db_session.commit()

    assert saved.id is not None
    assert saved.doc_type == "architecture"
    assert saved.version_number == 1
    assert saved.status == "draft"

    # 2. Update content (bumping version)
    updated = await doc_repo.update_document_content(
        doc_id=saved.id,
        content="# Architecture v2\n\nUpdated service layer description.",
        change_summary="Manual edit",
    )
    await db_session.commit()

    assert updated.version_number == 2
    assert "v2" in updated.content

    # 3. Retrieve version history
    versions = await doc_repo.list_versions(saved.id)
    assert len(versions) == 2
    assert versions[0].version_number == 2
    assert versions[1].version_number == 1

    # 4. Approve document
    approved = await doc_repo.approve_document(saved.id, user_id="user-approver-1")
    await db_session.commit()
    assert approved.status == "approved"
    assert approved.approved_by == "user-approver-1"
    assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_documentation_api_end_to_end(client: AsyncClient):
    """Tests full documentation generation, listing, editing, diffing, approving, and exporting via API."""
    token = await get_auth_token(client, "doc_tester@repomind.ai")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 1. Ingest a sample codebase ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README.md", "# Sample FastApi App\n")
        zf.writestr(
            "package.json",
            '{"name": "fastapi-companion", "scripts": {"dev": "vite", "build": "vite build"}}',
        )
        zf.writestr(
            ".env.example",
            "PORT=8000\nDATABASE_URL=postgresql://localhost/db\nAPI_KEY=sample\n",
        )
        zf.writestr(
            "main.py",
            """from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/items")
def create_item(name: str):
    return {"item": name}
""",
        )
    zip_buffer.seek(0)

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=auth_headers,
        files={"file": ("docs_test_repo.zip", zip_buffer.getvalue(), "application/zip")},
        data={"name": "Docs Test Repo"},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # 2. Trigger static analysis to populate symbols & endpoints
    analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=auth_headers,
    )
    assert analyze_res.status_code == 200

    # 3. Generate documentation suite
    gen_res = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers=auth_headers,
        json={"force_refresh": True},
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["status"] == "completed"
    assert gen_data["generated_count"] >= 5
    assert any(d["doc_type"] == "readme" for d in gen_data["documents"])

    # 4. List generated documents
    list_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation",
        headers=auth_headers,
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["total"] >= 5

    # 5. Get README detail and verify evidence grounding
    readme_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme",
        headers=auth_headers,
    )
    assert readme_res.status_code == 200
    readme_data = readme_res.json()
    assert readme_data["doc_type"] == "readme"
    assert "DATABASE_URL" in readme_data["content"]
    assert "npm run dev" in readme_data["content"]
    assert readme_data["version_number"] == 1
    assert readme_data["status"] == "draft"

    # 6. Get API documentation detail
    api_doc_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api",
        headers=auth_headers,
    )
    assert api_doc_res.status_code == 200
    api_doc_data = api_doc_res.json()
    assert "/health" in api_doc_data["content"] or "API" in api_doc_data["title"]

    # 7. Edit document
    update_res = await client.put(
        f"/api/v1/repositories/{repo_id}/documentation/readme",
        headers=auth_headers,
        json={
            "content": "# Updated Custom README\n\nManual edits applied by user.",
            "change_summary": "Added custom intro",
        },
    )
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["version_number"] == 2
    assert "Manual edits" in updated_data["content"]

    # 8. Compare versions (diff)
    diff_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme/diff?v1=1&v2=2",
        headers=auth_headers,
    )
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert diff_data["base_version"] == 1
    assert diff_data["target_version"] == 2
    assert len(diff_data["diff_patch"]) > 0

    # 9. Approve document
    approve_res = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/readme/approve",
        headers=auth_headers,
    )
    assert approve_res.status_code == 200
    approve_data = approve_res.json()
    assert approve_data["status"] == "approved"
    assert approve_data["approved_at"] is not None

    # 10. Export single document as Markdown
    exp_md_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme/export?format=markdown",
        headers=auth_headers,
    )
    assert exp_md_res.status_code == 200
    assert "text/markdown" in exp_md_res.headers["content-type"]
    assert b"Manual edits" in exp_md_res.content

    # 11. Export single document as HTML
    exp_html_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme/export?format=html",
        headers=auth_headers,
    )
    assert exp_html_res.status_code == 200
    assert "text/html" in exp_html_res.headers["content-type"]
    assert b"<!DOCTYPE html>" in exp_html_res.content

    # 12. Export complete package as ZIP
    exp_zip_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/export-package",
        headers=auth_headers,
    )
    assert exp_zip_res.status_code == 200
    assert "application/zip" in exp_zip_res.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(exp_zip_res.content), "r") as zf:
        assert any("readme.md" in n for n in zf.namelist())
        assert any("INDEX.md" in n for n in zf.namelist())


@pytest.mark.asyncio
async def test_documentation_security_and_multi_tenant_isolation(client: AsyncClient):
    """Ensures unauthorized users cannot access or modify another user's documentation."""
    user1_token = await get_auth_token(client, "tenant1@repomind.ai")
    user2_token = await get_auth_token(client, "tenant2@repomind.ai")

    # User 1 creates a repository
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zf:
        zf.writestr("test.py", "x = 1\n")
    zip_buffer.seek(0)

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers={"Authorization": f"Bearer {user1_token}"},
        files={"file": ("tenant_repo.zip", zip_buffer.getvalue(), "application/zip")},
        data={"name": "Tenant Repo"},
    )
    repo_id = upload_res.json()["id"]

    # User 1 generates documentation
    await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers={"Authorization": f"Bearer {user1_token}"},
    )

    # User 2 attempts to read User 1's documentation -> 403 Forbidden
    res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation",
        headers={"Authorization": f"Bearer {user2_token}"},
    )
    assert res.status_code == 403

    # User 2 attempts to update User 1's documentation -> 403 Forbidden
    res_update = await client.put(
        f"/api/v1/repositories/{repo_id}/documentation/readme",
        headers={"Authorization": f"Bearer {user2_token}"},
        json={"content": "Malicious override"},
    )
    assert res_update.status_code == 403

    # User 2 attempts to export User 1's package -> 403 Forbidden
    res_exp = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/export-package",
        headers={"Authorization": f"Bearer {user2_token}"},
    )
    assert res_exp.status_code == 403
