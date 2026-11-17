import json
import pytest
from unittest.mock import AsyncMock, patch

from app.services.ai_change_summary_service import AIChangeSummaryService
from app.services.impact_analysis_service import ImpactAnalysisService
from app.services.symbol_diff_service import SymbolDiffService
from app.services.update_detection_service import UpdateDetectionService


class TestUpdateDetectionService:
    def test_file_categorization(self):
        assert UpdateDetectionService.categorize_file("package.json") == "manifest"
        assert UpdateDetectionService.categorize_file("requirements.txt") == "manifest"
        assert UpdateDetectionService.categorize_file("pyproject.toml") == "manifest"
        assert UpdateDetectionService.categorize_file(".env.example") == "config"
        assert UpdateDetectionService.categorize_file("docker-compose.yml") == "config"
        assert UpdateDetectionService.categorize_file("tsconfig.json") == "config"
        assert UpdateDetectionService.categorize_file("README.md") == "documentation"
        assert UpdateDetectionService.categorize_file("docs/index.md") == "documentation"
        assert UpdateDetectionService.categorize_file("src/main.py") == "source"
        assert UpdateDetectionService.categorize_file("src/app.tsx") == "source"
        assert UpdateDetectionService.categorize_file("logo.png") == "other"

    def test_compute_unified_diff(self):
        old_text = "def hello():\n    print('hi')\n"
        new_text = "def hello():\n    print('hello world')\n    return True\n"
        adds, dels, patch = UpdateDetectionService.compute_unified_diff(old_text, new_text, "test.py")
        assert adds == 2
        assert dels == 1
        assert "hello world" in patch
        assert "--- a/test.py" in patch

    def test_detect_file_changes_added_modified_deleted(self):
        base_files = {
            "src/a.py": "def a(): pass\n",
            "src/b.py": "def b(): pass\n",
            "docs/readme.md": "# Readme\n",
        }
        target_files = {
            "src/a.py": "def a(): pass\n",  # Unchanged
            "src/b.py": "def b():\n    return 42\n",  # Modified
            "src/c.py": "def c(): pass\n",  # Added
        }
        changes = UpdateDetectionService.detect_file_changes(base_files, target_files)
        types = {c["path"]: c["change_type"] for c in changes}
        assert types["src/c.py"] == "added"
        assert types["src/b.py"] == "modified"
        assert types["docs/readme.md"] == "deleted"
        assert "src/a.py" not in types  # Unchanged files are omitted

    def test_detect_file_changes_renamed(self):
        content = "class Greeter:\n    def greet(self): return 'hi'\n"
        base_files = {"src/old_greeter.py": content}
        target_files = {"src/new_greeter.py": content}
        changes = UpdateDetectionService.detect_file_changes(base_files, target_files)
        assert len(changes) == 1
        assert changes[0]["change_type"] == "renamed"
        assert changes[0]["old_path"] == "src/old_greeter.py"
        assert changes[0]["path"] == "src/new_greeter.py"


class TestSymbolDiffService:
    def test_line_shift_invariance(self):
        """Moving a function down by 20 lines without modifying content must NOT label it as modified."""
        base_code = """
def unchanged_func(x: int) -> int:
    return x * 2
"""
        target_code = """
# Adding 10 blank lines above
# to simulate shifting line numbers










def unchanged_func(x: int) -> int:
    return x * 2
"""
        diffs = SymbolDiffService.diff_file_symbols(base_code, target_code, "test.py")
        # Since signature, params, and body are identical, it must NOT be reported as modified
        modified_names = [d["symbol_name"] for d in diffs if d["change_type"] == "modified"]
        assert "unchanged_func" not in modified_names

    def test_detect_function_signature_and_body_change(self):
        base_code = "def process(item: str) -> None:\n    pass\n"
        target_code = "def process(item: str, validate: bool = True) -> bool:\n    return bool(item)\n"
        diffs = SymbolDiffService.diff_file_symbols(base_code, target_code, "test.py")
        assert len(diffs) >= 1
        mod = next(d for d in diffs if d["symbol_name"] == "process")
        assert mod["change_type"] == "modified"
        assert "parameters_changed" in str(mod["evidence"]) or "return_type_changed" in str(mod["evidence"])

    def test_detect_added_and_deleted_symbols(self):
        base_code = "def old_helper(): pass\n"
        target_code = "def new_helper(): pass\n"
        diffs = SymbolDiffService.diff_file_symbols(base_code, target_code, "test.py")
        added = [d["symbol_name"] for d in diffs if d["change_type"] == "added"]
        deleted = [d["symbol_name"] for d in diffs if d["change_type"] == "deleted"]
        assert "new_helper" in added or "old_helper" in deleted


class TestAIChangeSummaryService:
    @pytest.mark.asyncio
    async def test_secret_redaction_before_prompt(self):
        svc = AIChangeSummaryService()
        raw = 'api_key = "sk_live_1234567890abcdef" and db = "postgresql://user:secretpass@db.example.com/db"'
        sanitized = svc._sanitize_text(raw)
        assert "sk_live_1234567890abcdef" not in sanitized
        assert "secretpass" not in sanitized
        assert "[REDACTED_SECRET]" in sanitized

    @pytest.mark.asyncio
    async def test_summary_grounding_fallback(self):
        svc = AIChangeSummaryService()
        # Mock provider failure to trigger grounded fallback
        with patch.object(svc.provider_manager, "generate_chat", new_callable=AsyncMock, side_effect=Exception("Provider down")):
            res = await svc.generate_change_summary(
                repository_name="test-repo",
                base_ref="commit:123",
                target_ref="commit:456",
                file_changes=[{"path": "a.py", "change_type": "modified", "additions": 5, "deletions": 2}],
                symbol_changes=[{"symbol_name": "calc", "symbol_type": "function", "change_type": "modified"}],
                impact_metrics={"directly_changed": 2, "directly_affected": 3, "indirectly_affected": 1},
            )
            assert "**Files Changed:** 1" in res["ai_summary_markdown"]
            assert "commit:123 → commit:456" in res["ai_summary_markdown"]
            assert res["provider_used"] == "deterministic_fallback"
