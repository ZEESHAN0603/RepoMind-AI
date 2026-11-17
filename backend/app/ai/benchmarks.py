import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.base import BaseLLMProvider
from app.ai.schemas import ChatMessage, GenerationResult
from app.core.logging import logger


@dataclass
class BenchmarkTask:
    task_id: str
    category: str
    description: str
    prompt: str
    expected_keywords: List[str]
    context_code: str
    expects_unknown: bool = False


BENCHMARK_TASKS: List[BenchmarkTask] = [
    BenchmarkTask(
        task_id="task_1_explain_python_function",
        category="Python Function",
        description="Explain a Python function from repository context.",
        prompt="Explain what the function `calculate_hash` does based on the provided code.",
        context_code="def calculate_hash(data: str, salt: str = 'repomind') -> str:\n    import hashlib\n    return hashlib.sha256((data + salt).encode()).hexdigest()",
        expected_keywords=["hashlib", "sha256", "salt", "digest"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_2_explain_react_component",
        category="TypeScript React",
        description="Explain a TypeScript React component and its hooks.",
        prompt="Explain what the `ConfidenceBadge` component renders and what prop determines its color.",
        context_code="interface Props { confidence: 'verified' | 'inferred' | 'unknown' }\nexport function ConfidenceBadge({ confidence }: Props) {\n  const color = confidence === 'verified' ? 'green' : 'amber';\n  return <span className={color}>{confidence}</span>;\n}",
        expected_keywords=["confidence", "color", "verified"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_3_explain_api_route",
        category="FastAPI Route",
        description="Explain an API route and its authentication dependency.",
        prompt="What authorization is required for the route `GET /repositories`?",
        context_code="@router.get('/repositories')\nasync def list_repos(user: User = Depends(get_current_user)):\n    return await repo_service.list(user.id)",
        expected_keywords=["get_current_user", "depends", "user"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_4_multifile_reasoning",
        category="Cross-file Architecture",
        description="Answer question requiring information across two modules.",
        prompt="How does `IngestionService` interact with `ZipService`?",
        context_code="class IngestionService:\n    def process(self, path):\n        ZipService.validate_and_extract(path, '/workspaces')\n\nclass ZipService:\n    @staticmethod\n    def validate_and_extract(zip_path, target_dir):\n        # check zip slip\n        pass",
        expected_keywords=["validate_and_extract", "zip_path"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_5_identify_callers",
        category="Call Hierarchy",
        description="Identify which function calls `decode_token`.",
        prompt="Which function invokes `decode_token` in this module?",
        context_code="def decode_token(t): return jwt.decode(t)\n\ndef get_current_user(token):\n    payload = decode_token(token)\n    return payload['sub']",
        expected_keywords=["get_current_user"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_6_imported_dependency",
        category="Dependency Analysis",
        description="Explain an imported dependency and where it is imported from.",
        prompt="Where is `StaticAnalysisService` imported from?",
        context_code="from app.services.static_analysis_service import StaticAnalysisService\nservice = StaticAnalysisService()",
        expected_keywords=["app.services.static_analysis_service"],
        expects_unknown=False,
    ),
    BenchmarkTask(
        task_id="task_7_insufficient_evidence",
        category="Unknown / Grounding Guardrail",
        description="Verify model states unknown when evidence is missing.",
        prompt="What is the database password for the production PostgreSQL instance?",
        context_code="# Repository configuration\nAPP_NAME = 'RepoMind'\nDEBUG = True",
        expected_keywords=["not", "unknown", "insufficient", "does not contain", "cannot find", "no information"],
        expects_unknown=True,
    ),
    BenchmarkTask(
        task_id="task_8_citation_adherence",
        category="Citation Accuracy",
        description="Ensure model references actual provided file and line numbers rather than hallucinating.",
        prompt="State the file path and start line where `utc_now` is defined based on the evidence.",
        context_code="# File: app/db/base.py (Lines 6-8)\ndef utc_now() -> datetime:\n    return datetime.now(timezone.utc)",
        expected_keywords=["base.py"],
        expects_unknown=False,
    ),
]


@dataclass
class TaskBenchmarkResult:
    task_id: str
    category: str
    success: bool
    latency_seconds: float
    tokens_generated: int
    tokens_per_second: float
    output_preview: str
    matched_keywords: List[str]
    missing_keywords: List[str]


@dataclass
class ModelBenchmarkSummary:
    model: str
    provider: str
    total_tasks: int
    passed_tasks: int
    pass_rate: float
    avg_latency_seconds: float
    avg_tokens_per_second: float
    task_results: List[TaskBenchmarkResult] = field(default_factory=list)


class ModelBenchmarkRunner:
    """Executes representative code intelligence benchmark tasks against an AI provider."""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    async def run_task(self, task: BenchmarkTask, model: Optional[str] = None) -> TaskBenchmarkResult:
        system_prompt = (
            "You are RepoMind's repository analysis assistant. Answer strictly based on the provided repository code. "
            "If the code does not contain sufficient evidence, state clearly that the repository does not contain this information. "
            "Never invent file paths, line numbers, or passwords."
        )

        user_content = f"--- EVIDENCE CONTEXT ---\n{task.context_code}\n\n--- QUESTION ---\n{task.prompt}"
        messages = [ChatMessage(role="user", content=user_content)]

        start_time = time.perf_counter()
        try:
            res: GenerationResult = await self.provider.generate_chat(
                messages=messages,
                model=model,
                system_prompt=system_prompt,
                temperature=0.1,
            )
            duration = max(time.perf_counter() - start_time, 0.001)
            content = res.content
            output_lower = content.lower()

            tokens_count = res.usage.completion_tokens or len(content.split())
            tokens_per_sec = tokens_count / duration

            matched = [k for k in task.expected_keywords if k.lower() in output_lower]
            missing = [k for k in task.expected_keywords if k.lower() not in output_lower]

            # In "unknown" cases, at least one unknown indicator keyword must match
            if task.expects_unknown:
                success = len(matched) > 0
            else:
                success = len(matched) >= max(1, len(task.expected_keywords) // 2)

            return TaskBenchmarkResult(
                task_id=task.task_id,
                category=task.category,
                success=success,
                latency_seconds=round(duration, 3),
                tokens_generated=tokens_count,
                tokens_per_second=round(tokens_per_sec, 1),
                output_preview=content[:150],
                matched_keywords=matched,
                missing_keywords=missing,
            )
        except Exception as e:
            duration = max(time.perf_counter() - start_time, 0.001)
            return TaskBenchmarkResult(
                task_id=task.task_id,
                category=task.category,
                success=False,
                latency_seconds=round(duration, 3),
                tokens_generated=0,
                tokens_per_second=0.0,
                output_preview=f"FAILED: {e}",
                matched_keywords=[],
                missing_keywords=task.expected_keywords,
            )

    async def run_benchmark(self, model: Optional[str] = None) -> ModelBenchmarkSummary:
        results: List[TaskBenchmarkResult] = []
        for task in BENCHMARK_TASKS:
            r = await self.run_task(task, model=model)
            results.append(r)

        passed = sum(1 for r in results if r.success)
        total = len(results)
        total_lat = sum(r.latency_seconds for r in results)
        valid_tps = [r.tokens_per_second for r in results if r.tokens_per_second > 0]
        avg_tps = sum(valid_tps) / len(valid_tps) if valid_tps else 0.0

        return ModelBenchmarkSummary(
            model=model or getattr(self.provider, "_generation_model", "default"),
            provider=self.provider.provider_name,
            total_tasks=total,
            passed_tasks=passed,
            pass_rate=round((passed / total) * 100, 1),
            avg_latency_seconds=round(total_lat / total, 3),
            avg_tokens_per_second=round(avg_tps, 1),
            task_results=results,
        )
