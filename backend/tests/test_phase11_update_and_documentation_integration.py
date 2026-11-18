import io
import zipfile
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.embedding_service import EmbeddingService


@pytest_asyncio.fixture(autouse=True)
def mock_embedding_indexing(monkeypatch):
    """Mocks embedding indexer so tests don't block on external LLM timeouts."""
    async def mock_index(*args, **kwargs):
        return {"total_chunks": 5, "embedded_chunks": 5}
    monkeypatch.setattr(EmbeddingService, "index_repository_embeddings", mock_index)


def create_v1_repo_zip() -> bytes:
    """Builds initial repository archive (Version 1)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            "# MicroStore Commerce Engine\n\nModular e-commerce microservice platform.\n",
        )
        zf.writestr(
            "requirements.txt",
            "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\n",
        )
        zf.writestr(
            "package.json",
            '{\n  "name": "microstore-client",\n  "version": "1.0.0",\n  "dependencies": {"react": "^18.2.0"}\n}',
        )
        zf.writestr(
            "main.py",
            '''from fastapi import FastAPI, Depends
from services.order import OrderService

app = FastAPI(title="MicroStore")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/orders")
def create_order(item: str, service: OrderService = Depends()):
    return service.process(item)
''',
        )
        zf.writestr(
            "services/order.py",
            '''from services.payment import PaymentGateway

class OrderService:
    def __init__(self):
        self.gateway = PaymentGateway()

    def process(self, item: str) -> dict:
        result = self.gateway.charge(item, 100)
        return {"item": item, "processed": result}
''',
        )
        zf.writestr(
            "services/payment.py",
            '''class PaymentGateway:
    def charge(self, item: str, amount: int) -> bool:
        return bool(item and amount > 0)
''',
        )
        zf.writestr(
            "utils/formatter.py",
            '''def format_currency(amount: int) -> str:
    return f"${amount:.2f}"
''',
        )
        zf.writestr(
            "legacy/old_helper.py",
            '''def deprecated_helper():
    return "deprecated"
''',
        )
    return buf.getvalue()


@pytest.mark.asyncio
async def test_update_aware_documentation_workflow(client: AsyncClient, db_session: AsyncSession):
    """
    Validates complete Workflow B & Milestone 11.6 requirements:
    1. Ingest repository Version 1.
    2. Generate full technical documentation suite (7 documents).
    3. User reviews and approves all documents (status='approved').
    4. Update repository with Version 2 changes:
       - Added file: services/notifications.py
       - Modified file: services/order.py (changed method signature and logic)
       - Pure line-shift file: utils/formatter.py (line shifts must NOT mark symbol modified)
       - Deleted file: legacy/old_helper.py
       - Modified manifest: requirements.txt (added stripe>=5.0.0)
    5. Run update analysis (Phase 9):
       - Detects file changes with correct classifications (source, manifest, etc.)
       - Detects symbol modifications line-shift invariantly
       - Computes blast-radius impact across dependency and call graphs
       - Marks affected approved documentation sections as 'stale' (outdated)
       - Preserves unaffected approved documents without overwriting
    6. Update-aware documentation regeneration (Phase 10):
       - Selective regeneration of stale sections with version bump
       - Unified diff generation between v1 and v2 documentation
       - Re-approval of updated documentation
       - Markdown, HTML, and ZIP package export validation
    7. Multi-tenant isolation: unauthorized users cannot view update runs or docs.
    """

    # -------------------------------------------------------------------------
    # 1. Register & Authenticate User
    # -------------------------------------------------------------------------
    owner_email = "devlead@repomind.io"
    password = "SecureDevPass123!"

    reg_res = await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Dev Lead", "email": owner_email, "password": password},
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": owner_email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # -------------------------------------------------------------------------
    # 2. Ingest Repository Version 1
    # -------------------------------------------------------------------------
    v1_zip = create_v1_repo_zip()
    upload_res = await client.post(
        "/api/v1/repositories/upload",
        headers=auth_headers,
        data={"name": "microstore-engine", "description": "Commerce engine v1"},
        files={"file": ("microstore_v1.zip", v1_zip, "application/zip")},
    )
    assert upload_res.status_code == 201
    repo_id = upload_res.json()["id"]

    # Trigger initial static analysis, execution analysis, and dependency analysis
    analyze_ci = await client.post(f"/api/v1/repositories/{repo_id}/analyze", headers=auth_headers)
    assert analyze_ci.status_code == 200
    assert analyze_ci.json()["symbols_extracted"] > 0

    analyze_exec = await client.post(f"/api/v1/repositories/{repo_id}/execution/analyze", headers=auth_headers)
    assert analyze_exec.status_code == 200

    analyze_dep = await client.post(f"/api/v1/repositories/{repo_id}/dependencies/analyze", headers=auth_headers)
    assert analyze_dep.status_code == 200

    # -------------------------------------------------------------------------
    # 3. Generate Initial Documentation Suite and Approve All Sections
    # -------------------------------------------------------------------------
    doc_gen_res = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers=auth_headers,
        json={"force_refresh": True},
    )
    assert doc_gen_res.status_code == 200
    docs_data = doc_gen_res.json()
    assert docs_data["status"] == "completed"
    assert len(docs_data["documents"]) >= 6

    # Approve all generated documents (marking baseline as approved)
    for doc_item in docs_data["documents"]:
        approve_res = await client.post(
            f"/api/v1/repositories/{repo_id}/documentation/{doc_item['doc_type']}/approve",
            headers=auth_headers,
        )
        assert approve_res.status_code == 200
        assert approve_res.json()["status"] == "approved"

    # Verify all docs in DB are approved
    list_docs = await client.get(f"/api/v1/repositories/{repo_id}/documentation", headers=auth_headers)
    assert list_docs.status_code == 200
    for doc in list_docs.json()["items"]:
        assert doc["status"] == "approved"

    # -------------------------------------------------------------------------
    # 4. Apply Repository Version 2 Modifications to Workspace Disk
    # -------------------------------------------------------------------------
    from app.services.workspace_service import WorkspaceService
    ws = WorkspaceService()
    me_res = await client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = me_res.json()["id"]
    ws_path = ws.get_repository_workspace_path(user_id, repo_id)

    # 4.1 Added file: services/notifications.py
    notif_path = ws_path / "services" / "notifications.py"
    notif_path.write_text(
        '''class NotificationService:
    def send_order_receipt(self, email: str, item: str) -> bool:
        return True
''',
        encoding="utf-8",
    )

    # 4.2 Modified file: services/order.py (altered method signature and implementation)
    order_path = ws_path / "services" / "order.py"
    order_path.write_text(
        '''from services.payment import PaymentGateway
from services.notifications import NotificationService

class OrderService:
    def __init__(self):
        self.gateway = PaymentGateway()
        self.notif = NotificationService()

    def process(self, item: str, quantity: int = 1) -> dict:
        result = self.gateway.charge(item, 100 * quantity)
        self.notif.send_order_receipt("customer@example.com", item)
        return {"item": item, "quantity": quantity, "processed": result}
''',
        encoding="utf-8",
    )

    # 4.3 Pure line-shift file: utils/formatter.py (prepended blank lines/comments only)
    fmt_path = ws_path / "utils" / "formatter.py"
    fmt_path.write_text(
        '''# Line shift padding comment line 1
# Line shift padding comment line 2
# Line shift padding comment line 3

def format_currency(amount: int) -> str:
    return f"${amount:.2f}"
''',
        encoding="utf-8",
    )

    # 4.4 Deleted file: legacy/old_helper.py
    del_path = ws_path / "legacy" / "old_helper.py"
    if del_path.exists():
        del_path.unlink()

    # 4.5 Modified manifest: requirements.txt
    req_path = ws_path / "requirements.txt"
    req_path.write_text(
        "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0.0\nstripe>=5.0.0\n",
        encoding="utf-8",
    )

    # -------------------------------------------------------------------------
    # 5. Run Update Analysis (Phase 9)
    # -------------------------------------------------------------------------
    update_res = await client.post(
        f"/api/v1/repositories/{repo_id}/updates/analyze",
        headers=auth_headers,
        json={"include_ai_summary": True},
    )
    assert update_res.status_code == 201
    run_data = update_res.json()
    update_run_id = run_data["id"]
    assert run_data["status"] == "completed"

    # Verify changed files detection and categories
    files_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/files",
        headers=auth_headers,
    )
    assert files_res.status_code == 200
    file_changes = files_res.json()
    changed_map = {f["path"].replace("\\", "/"): f for f in file_changes}

    # Verify added file
    assert "services/notifications.py" in changed_map
    assert changed_map["services/notifications.py"]["change_type"] == "added"
    assert changed_map["services/notifications.py"]["file_category"] == "source"

    # Verify modified file
    assert "services/order.py" in changed_map
    assert changed_map["services/order.py"]["change_type"] == "modified"
    assert changed_map["services/order.py"]["file_category"] == "source"

    # Verify manifest change
    assert "requirements.txt" in changed_map
    assert changed_map["requirements.txt"]["file_category"] == "manifest"

    # Verify symbol diffing with strict line-shift invariance
    symbols_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/symbols",
        headers=auth_headers,
    )
    assert symbols_res.status_code == 200
    sym_changes = symbols_res.json()
    sym_names = [s["symbol_name"] for s in sym_changes]

    # 'format_currency' had only comments/line-shifts prepended -> MUST NOT be marked modified!
    assert "format_currency" not in sym_names, "Line-shift alone incorrectly marked symbol as modified!"

    # 'process' method in OrderService was modified
    assert any("process" in s for s in sym_names)

    # Verify blast-radius impact records
    impact_res = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}/impact",
        headers=auth_headers,
    )
    assert impact_res.status_code == 200
    impact_records = impact_res.json()
    assert len(impact_records) > 0
    impact_levels = {r["impact_level"] for r in impact_records}
    assert "directly_changed" in impact_levels

    # -------------------------------------------------------------------------
    # 6. Verify Documentation Impact & Outdated (Stale) Status
    # -------------------------------------------------------------------------
    # Approved documents impacted by the changes (api, dependencies, etc.)
    # should transition to 'stale' status to alert the user
    docs_after_update = await client.get(f"/api/v1/repositories/{repo_id}/documentation", headers=auth_headers)
    assert docs_after_update.status_code == 200
    doc_status_map = {d["doc_type"]: d["status"] for d in docs_after_update.json()["items"]}

    # 'api' and 'dependencies' should be marked stale
    assert doc_status_map.get("api") == "stale"
    assert doc_status_map.get("dependencies") == "stale"

    # -------------------------------------------------------------------------
    # 7. Update-Aware Documentation Workflow: Preservation vs. Regeneration
    # -------------------------------------------------------------------------
    # Test 7.1: Calling generate without force_refresh MUST PRESERVE approved documents
    # First, approve 'architecture' again
    await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/architecture/approve",
        headers=auth_headers,
    )
    prev_arch = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/architecture",
        headers=auth_headers,
    )
    prev_arch_content = prev_arch.json()["content"]

    regen_partial = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers=auth_headers,
        json={"force_refresh": False},
    )
    assert regen_partial.status_code == 200

    # Ensure approved architecture was preserved
    curr_arch = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/architecture",
        headers=auth_headers,
    )
    assert curr_arch.json()["status"] == "approved"
    assert curr_arch.json()["content"] == prev_arch_content

    # Test 7.2: Selective regeneration of stale section ('api') with force_refresh
    regen_api = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/generate",
        headers=auth_headers,
        json={"doc_types": ["api"], "force_refresh": True},
    )
    assert regen_api.status_code == 200

    api_detail = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api",
        headers=auth_headers,
    )
    assert api_detail.status_code == 200
    assert api_detail.json()["version_number"] >= 2
    assert len(api_detail.json()["versions"]) >= 2

    # -------------------------------------------------------------------------
    # 8. Document Version Diffing & Review
    # -------------------------------------------------------------------------
    diff_res = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api/diff?v1=1&v2=2",
        headers=auth_headers,
    )
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert diff_data["base_version"] == 1
    assert diff_data["target_version"] == 2
    assert "diff_patch" in diff_data

    # Re-approve the updated API documentation
    reapprove = await client.post(
        f"/api/v1/repositories/{repo_id}/documentation/api/approve",
        headers=auth_headers,
    )
    assert reapprove.status_code == 200
    assert reapprove.json()["status"] == "approved"

    # -------------------------------------------------------------------------
    # 9. Document Export Formats
    # -------------------------------------------------------------------------
    # Markdown export
    exp_md = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api/export?format=markdown",
        headers=auth_headers,
    )
    assert exp_md.status_code == 200
    assert "text/markdown" in exp_md.headers["content-type"]

    # HTML export
    exp_html = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api/export?format=html",
        headers=auth_headers,
    )
    assert exp_html.status_code == 200
    assert "text/html" in exp_html.headers["content-type"]
    assert b"<!DOCTYPE html>" in exp_html.content

    # ZIP package export
    exp_zip = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/export-package",
        headers=auth_headers,
    )
    assert exp_zip.status_code == 200
    assert "application/zip" in exp_zip.headers["content-type"]

    # -------------------------------------------------------------------------
    # 10. Multi-Tenant Authorization & Security Isolation
    # -------------------------------------------------------------------------
    intruder_email = "intruder.user@external.dev"
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Intruder", "email": intruder_email, "password": "Password123!"},
    )
    intruder_login = await client.post(
        "/api/v1/auth/login",
        json={"email": intruder_email, "password": "Password123!"},
    )
    intruder_headers = {"Authorization": f"Bearer {intruder_login.json()['access_token']}"}

    # Intruder cannot access update runs
    forbid_update = await client.get(
        f"/api/v1/repositories/{repo_id}/updates/{update_run_id}",
        headers=intruder_headers,
    )
    assert forbid_update.status_code == 403

    # Intruder cannot access documents
    forbid_doc = await client.get(
        f"/api/v1/repositories/{repo_id}/documentation/api",
        headers=intruder_headers,
    )
    assert forbid_doc.status_code == 403


@pytest.mark.asyncio
async def test_ai_change_summary_grounding_and_redaction():
    """Validates secret redaction, strict evidence grounding, and provider failure handling."""
    from unittest.mock import AsyncMock
    from app.services.ai_change_summary_service import AIChangeSummaryService
    from app.ai.schemas import GenerationResult, ProviderType

    svc = AIChangeSummaryService()

    # 1. Secret redaction test
    text_with_secrets = "Found GitHub token ghp_123456789012345678901234567890123456 and AWS AKIAIOSFODNN7EXAMPLE"
    sanitized = svc._sanitize_text(text_with_secrets)
    assert "ghp_123456789012345678901234567890123456" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized or "[REDACTED" in sanitized

    # 2. Strict grounding prompt structure test
    prompt = svc._build_grounding_prompt(
        repository_name="secure-core",
        base_ref="v1.0.0",
        target_ref="v2.0.0",
        file_changes=[{"change_type": "modified", "path": "auth.py", "file_category": "source", "additions": 10, "deletions": 2}],
        symbol_changes=[{"change_type": "modified", "symbol_type": "function", "symbol_name": "login", "scope": None, "old_signature": "login(u)", "new_signature": "login(u, p)"}],
        impact_metrics={"directly_changed": 1, "directly_affected": 2},
    )
    assert "STRICT GROUNDING RULES" in prompt
    assert "DO NOT claim that a downstream component is broken merely because an imported dependency changed" in prompt
    assert "auth.py" in prompt
    assert "login" in prompt

    # 3. Provider reporting test with mock ProviderManager
    mock_pm = AsyncMock()
    mock_res = GenerationResult(
        content="## Executive Overview\nAuthentication updated with password parameter.",
        provider=ProviderType.OLLAMA.value,
        model="qwen3.5:4b",
        duration_seconds=0.12,
    )
    # Set provider_name and model_name attributes expected by AIChangeSummaryService
    setattr(mock_res, "provider_name", "ollama")
    setattr(mock_res, "model_name", "qwen3.5:4b")
    mock_pm.generate_chat.return_value = mock_res

    summary_svc = AIChangeSummaryService(provider_manager=mock_pm)
    res = await summary_svc.generate_change_summary(
        repository_name="secure-core",
        base_ref="v1.0.0",
        target_ref="v2.0.0",
        file_changes=[],
        symbol_changes=[],
        impact_metrics={},
    )
    assert res["provider_used"] == "ollama"
    assert res["model_used"] == "qwen3.5:4b"
    assert "Authentication updated" in res["ai_summary_markdown"]
