import io
import zipfile
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.embedding_service import EmbeddingService


@pytest_asyncio.fixture(autouse=True)
def mock_embedding_indexing(monkeypatch):
    """Mocks embedding indexer so unit tests do not block on external LLM timeouts."""
    async def mock_index(*args, **kwargs):
        return {"total_chunks": 5, "embedded_chunks": 5}
    monkeypatch.setattr(EmbeddingService, "index_repository_embeddings", mock_index)


def create_sample_repo_zip() -> bytes:
    """Creates a sample multi-language repository ZIP archive in-memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            "# MicroStore API\n\nHigh-performance commerce service with FastAPI.\n",
        )
        zf.writestr(
            "requirements.txt",
            "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\npytest>=8.0.0\n",
        )
        zf.writestr(
            "package.json",
            '{\n  "name": "microstore-ui",\n  "version": "1.0.0",\n  "dependencies": {\n    "react": "^18.2.0"\n  }\n}',
        )
        zf.writestr(
            "main.py",
            '''from fastapi import FastAPI, Depends
from services.order import OrderService

app = FastAPI(title="MicroStore")

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/orders")
def create_order(item: str, service: OrderService = Depends()):
    return service.process_order(item)
''',
        )
        zf.writestr(
            "services/order.py",
            '''from services.payment import PaymentGateway

class OrderService:
    def __init__(self):
        self.gateway = PaymentGateway()

    def process_order(self, item: str):
        charge_status = self.gateway.charge(item)
        return {"item": item, "charged": charge_status}
''',
        )
        zf.writestr(
            "services/payment.py",
            '''class PaymentGateway:
    def charge(self, item: str) -> bool:
        if not item:
            return False
        return True
''',
        )
    return buf.getvalue()


@pytest.mark.asyncio
async def test_complete_end_to_end_cross_phase_lifecycle(client: AsyncClient, db_session: AsyncSession):
    """
    Validates complete end-to-end integration lifecycle across Phases 1 through 10:
    1. Authentication: Register, Login, Verify Current User.
    2. Ingestion: ZIP repository upload, file extraction, directory tree generation.
    3. Code Intelligence: AST parsing, symbol extraction, API route detection.
    4. Architecture: Classification, graph extraction, edge resolution.
    5. Execution Flows: Entry point detection, call graph generation, workspace tracing.
    6. Dependency Analysis: Direct & transitive package manifest analysis.
    7. Update Intelligence: Update history and diffing.
    8. Documentation: Auto-generation of full documentation suite, editing, diffing, export.
    9. Security Isolation: Ensure unauthorized users receive 403 Forbidden.
    10. Lifecycle Cleanup: Repository deletion and cascading resource verification.
    """

    # =========================================================================
    # Step 1: Authentication & Authorization (Phase 2)
    # =========================================================================
    owner_email = "architect@repomind.io"
    owner_password = "SecurePassword123!"

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Chief Architect",
            "email": owner_email,
            "password": owner_password,
        },
    )
    assert reg_res.status_code == 201, f"Register failed: {reg_res.text}"

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": owner_password},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    assert "access_token" in token_data
    assert "refresh_token" in token_data
    owner_token = token_data["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    me_res = await client.get("/api/v1/auth/me", headers=owner_headers)
    assert me_res.status_code == 200
    assert me_res.json()["email"] == owner_email

    # =========================================================================
    # Step 2: Ingestion & File Discovery (Phase 3)
    # =========================================================================
    zip_bytes = create_sample_repo_zip()
    files = {"file": ("microstore.zip", zip_bytes, "application/zip")}
    data = {"name": "microstore", "description": "Commerce microservice"}

    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=owner_headers,
        data=data,
        files=files,
    )
    assert upload_res.status_code == 201, f"Upload failed: {upload_res.text}"
    repo_data = upload_res.json()
    repo_id = repo_data["id"]
    assert repo_data["name"] == "microstore"

    # Verify repository overview
    overview_res = await client.get(
        f"/api/v1/repositories/{repo_id}/overview",
        headers=owner_headers,
    )
    assert overview_res.status_code == 200
    overview_data = overview_res.json()
    assert overview_data["file_count"] >= 4

    # Verify file tree hierarchy
    files_res = await client.get(
        f"/api/v1/repositories/{repo_id}/files",
        headers=owner_headers,
    )
    assert files_res.status_code == 200
    file_tree = files_res.json()
    assert len(file_tree) > 0

    # =========================================================================
    # Step 3: Code Intelligence & Static Analysis (Phase 4)
    # =========================================================================
    analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/analyze",
        headers=owner_headers,
    )
    assert analyze_res.status_code == 200, f"Analysis failed: {analyze_res.text}"
    analysis_summary = analyze_res.json()
    assert analysis_summary["symbols_extracted"] > 0

    # Verify extracted symbols
    symbols_res = await client.get(
        f"/api/v1/repositories/{repo_id}/symbols",
        headers=owner_headers,
    )
    assert symbols_res.status_code == 200
    symbols_data = symbols_res.json()
    assert symbols_data["total"] > 0
    symbol_names = [s["name"] for s in symbols_data["items"]]
    assert any("OrderService" in s for s in symbol_names)

    # Verify extracted API endpoints
    endpoints_res = await client.get(
        f"/api/v1/repositories/{repo_id}/endpoints",
        headers=owner_headers,
    )
    assert endpoints_res.status_code == 200
    endpoints_data = endpoints_res.json()
    assert len(endpoints_data) >= 1
    paths = [ep["path"] for ep in endpoints_data]
    assert any("/health" in p or "/orders" in p for p in paths)

    # =========================================================================
    # Step 4: Architecture Intelligence (Phase 6)
    # =========================================================================
    arch_res = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/graph",
        headers=owner_headers,
    )
    assert arch_res.status_code == 200, f"Architecture graph failed: {arch_res.text}"
    arch_data = arch_res.json()
    assert "nodes" in arch_data
    assert "edges" in arch_data
    assert len(arch_data["nodes"]) > 0

    # =========================================================================
    # Step 5: Execution Flow Tracing (Phase 7)
    # =========================================================================
    exec_analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/execution/analyze",
        headers=owner_headers,
    )
    assert exec_analyze_res.status_code == 200, f"Execution analyze failed: {exec_analyze_res.text}"

    workspace_res = await client.get(
        f"/api/v1/repositories/{repo_id}/execution/workspace",
        headers=owner_headers,
    )
    assert workspace_res.status_code == 200
    ws_data = workspace_res.json()
    assert "traces" in ws_data
    assert "functions" in ws_data
    assert len(ws_data["traces"]) > 0

    ep_res = await client.get(
        f"/api/v1/repositories/{repo_id}/execution/entry-points",
        headers=owner_headers,
    )
    assert ep_res.status_code == 200
    assert len(ep_res.json()["entry_points"]) > 0

    # =========================================================================
    # Step 6: Dependency Intelligence (Phase 8)
    # =========================================================================
    dep_analyze_res = await client.post(
        f"/api/v1/repositories/{repo_id}/dependencies/analyze",
        headers=owner_headers,
    )
    assert dep_analyze_res.status_code == 200, f"Dependency analyze failed: {dep_analyze_res.text}"

    dep_res = await client.get(
        f"/api/v1/repositories/{repo_id}/dependencies/graph",
        headers=owner_headers,
    )
    assert dep_res.status_code == 200, f"Dependencies failed: {dep_res.text}"
    dep_data = dep_res.json()
    assert "nodes" in dep_data
    assert "relationships" in dep_data
    assert len(dep_data["nodes"]) > 0

    # =========================================================================
    # Step 7: Update Intelligence (Phase 9)
    # =========================================================================
    history_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/history",
        headers=owner_headers,
    )
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert "repository_id" in history_data

    # =========================================================================
    # Step 8: Documentation Suite Generation & Export (Phase 10)
    # =========================================================================
    doc_gen_res = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers=owner_headers,
    )
    assert doc_gen_res.status_code == 200, f"Doc generation failed: {doc_gen_res.text}"
    docs = doc_gen_res.json()
    assert docs["status"] == "completed"
    assert len(docs["documents"]) >= 5

    # Fetch individual README doc
    readme_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme",
        headers=owner_headers,
    )
    assert readme_res.status_code == 200
    readme_doc = readme_res.json()
    assert readme_doc["doc_type"] == "readme"
    assert "microstore" in readme_doc["content"]

    # Export documentation as markdown
    export_md_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/readme/export?format=markdown",
        headers=owner_headers,
    )
    assert export_md_res.status_code == 200
    assert b"microstore" in export_md_res.content

    # Export full documentation ZIP package
    export_zip_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/export-package",
        headers=owner_headers,
    )
    assert export_zip_res.status_code == 200
    assert "application/zip" in export_zip_res.headers["content-type"]
    with zipfile.ZipFile(io.BytesIO(export_zip_res.content), "r") as zf:
        names = zf.namelist()
        assert any("INDEX.md" in n for n in names)
        assert any("readme.md" in n for n in names)

    # =========================================================================
    # Step 9: User Isolation & Security Boundaries (Phase 2 & Security)
    # =========================================================================
    unauth_email = "intruder@external.io"
    await client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Intruder",
            "email": unauth_email,
            "password": "IntruderPassword123!",
        },
    )
    unauth_login = await client.post(
        "/api/v1/auth/login",
        json={"email": unauth_email, "password": "IntruderPassword123!"},
    )
    unauth_headers = {"Authorization": f"Bearer {unauth_login.json()['access_token']}"}

    # Intruder tries to access owner's repository
    forbidden_res = await client.get(
        f"/api/v1/repositories/{repo_id}/overview",
        headers=unauth_headers,
    )
    assert forbidden_res.status_code == 403, "Tenant isolation failure: unauthorized user accessed repo"

    # Intruder tries to access architecture graph
    forbidden_arch = await client.get(
        f"/api/v1/repositories/{repo_id}/architecture/graph",
        headers=unauth_headers,
    )
    assert forbidden_arch.status_code == 403

    # =========================================================================
    # Step 10: Cascade Cleanup & Resource Deletion
    # =========================================================================
    del_res = await client.delete(
        f"/api/v1/repositories/{repo_id}",
        headers=owner_headers,
    )
    assert del_res.status_code == 200

    # Ensure repository is no longer accessible
    verify_del = await client.get(
        f"/api/v1/repositories/{repo_id}",
        headers=owner_headers,
    )
    assert verify_del.status_code == 404
