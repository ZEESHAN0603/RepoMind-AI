import pytest
from unittest.mock import AsyncMock, MagicMock

from app.ai.base import BaseLLMProvider
from app.ai.benchmarks import BENCHMARK_TASKS, ModelBenchmarkRunner
from app.ai.schemas import GenerationResult, TokenUsage


@pytest.mark.asyncio
async def test_benchmark_runner_all_tasks_pass():
    """Verifies benchmark runner evaluates tasks against compliant responses."""
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.provider_name = "ollama"
    mock_provider._generation_model = "qwen3.5:4b"

    def dynamic_reply(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt_text = messages[0].content if messages else ""

        if "calculate_hash" in prompt_text:
            content = "The function uses hashlib.sha256 with a salt to compute a secure digest."
        elif "ConfidenceBadge" in prompt_text:
            content = "ConfidenceBadge renders the confidence level and sets color to green for verified."
        elif "GET /repositories" in prompt_text:
            content = "It requires depends on get_current_user to authenticate the user."
        elif "IngestionService" in prompt_text:
            content = "IngestionService calls ZipService.validate_and_extract with the zip_path."
        elif "decode_token" in prompt_text:
            content = "The function get_current_user invokes decode_token."
        elif "StaticAnalysisService" in prompt_text:
            content = "It is imported from app.services.static_analysis_service."
        elif "database password" in prompt_text:
            content = "The repository does not contain this information. Database password is unknown."
        else:
            content = "Found in base.py on line 6."

        return GenerationResult(
            content=content,
            provider="ollama",
            model="qwen3.5:4b",
            usage=TokenUsage(prompt_tokens=40, completion_tokens=20, total_tokens=60),
            duration_seconds=0.1,
        )

    mock_provider.generate_chat = AsyncMock(side_effect=dynamic_reply)

    runner = ModelBenchmarkRunner(mock_provider)
    summary = await runner.run_benchmark(model="qwen3.5:4b")

    assert summary.total_tasks == 8
    assert summary.passed_tasks == 8
    assert summary.pass_rate == 100.0
    assert summary.avg_latency_seconds > 0
    assert summary.model == "qwen3.5:4b"
    assert len(summary.task_results) == 8


@pytest.mark.asyncio
async def test_benchmark_runner_handles_task_failure():
    """Verifies failed task keyword matching is caught in summary."""
    mock_provider = MagicMock(spec=BaseLLMProvider)
    mock_provider.provider_name = "ollama"
    mock_provider._generation_model = "qwen3.5:4b"

    # Return irrelevant response for everything
    mock_provider.generate_chat = AsyncMock(
        return_value=GenerationResult(
            content="I am a random model with completely unrelated output.",
            provider="ollama",
            model="qwen3.5:4b",
            usage=TokenUsage(prompt_tokens=10, completion_tokens=10, total_tokens=20),
        )
    )

    runner = ModelBenchmarkRunner(mock_provider)
    summary = await runner.run_benchmark(model="qwen3.5:4b")

    assert summary.total_tasks == 8
    assert summary.passed_tasks < 8
    assert summary.pass_rate < 50.0
