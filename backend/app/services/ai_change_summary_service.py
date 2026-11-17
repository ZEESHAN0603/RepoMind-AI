from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from app.ai.provider_manager import REDACTION_RULES, ProviderManager
from app.ai.schemas import ChatMessage
from app.core.logging import logger


class AIChangeSummaryService:
    """
    Synthesizes evidence-grounded AI change summaries and risk assessments
    using ProviderManager (Ollama qwen3.5:4b primary, Gemini free tier fallback).
    """

    def __init__(self, provider_manager: Optional[ProviderManager] = None) -> None:
        self.provider_manager = provider_manager or ProviderManager()

    def _sanitize_text(self, text: str) -> str:
        """Applies REDACTION_RULES to sanitize any secrets before AI dispatch."""
        sanitized = text
        for pattern, replacement in REDACTION_RULES:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    def _build_grounding_prompt(
        self,
        repository_name: str,
        base_ref: str,
        target_ref: str,
        file_changes: List[Dict[str, Any]],
        symbol_changes: List[Dict[str, Any]],
        impact_metrics: Dict[str, Any],
        focus: Optional[str] = None,
    ) -> str:
        """Constructs a strict, hallucination-resistant evidence prompt."""
        # Summarize files
        files_summary = []
        for f in file_changes[:40]:  # Cap to top 40 files
            files_summary.append(
                f"- {f.get('change_type', 'modified').upper()}: `{f.get('path')}` "
                f"({f.get('file_category', 'source')}, +{f.get('additions', 0)}/-{f.get('deletions', 0)})"
            )
        if len(file_changes) > 40:
            files_summary.append(f"- ... and {len(file_changes) - 40} more files changed.")

        # Summarize symbols
        symbols_summary = []
        for s in symbol_changes[:50]:  # Cap to top 50 symbols
            sig_diff = ""
            if s.get("old_signature") and s.get("new_signature"):
                sig_diff = f": `{s['old_signature']}` -> `{s['new_signature']}`"
            elif s.get("new_signature"):
                sig_diff = f": `{s['new_signature']}`"
            symbols_summary.append(
                f"- {s.get('change_type', 'modified').upper()} {s.get('symbol_type', 'symbol')}: "
                f"`{s.get('symbol_name')}` in scope `{s.get('scope') or 'module'}`{sig_diff}"
            )
        if len(symbol_changes) > 50:
            symbols_summary.append(f"- ... and {len(symbol_changes) - 50} more symbols changed.")

        prompt = f"""You are RepoMind's Repository Update Intelligence Analyst.
Analyze the following verified changes for repository `{repository_name}` between base `{base_ref}` and target `{target_ref}`.

### STRICT GROUNDING RULES:
1. Base your explanation ONLY on the verified evidence supplied below.
2. DO NOT hallucinate that tests passed or failed unless test execution results are explicitly listed.
3. DO NOT claim that a downstream component is broken merely because an imported dependency changed.
4. Clearly distinguish between "Verified Changes" (what was modified) and "Inferred Blast Radius" (what might be affected).
5. If the focus is specified as '{focus}', prioritize that aspect.

### VERIFIED EVIDENCE:

**Impact Blast Radius Metrics:**
- Directly Changed Elements: {impact_metrics.get('directly_changed', 0)}
- Directly Affected Dependents / Callers: {impact_metrics.get('directly_affected', 0)}
- Indirect Transitive Dependents: {impact_metrics.get('indirectly_affected', 0)}
- Potential Dynamic Impacts: {impact_metrics.get('potentially_affected', 0)}

**Changed Files ({len(file_changes)} total):**
{chr(10).join(files_summary) if files_summary else "No file changes recorded."}

**Changed Code Symbols & Endpoints ({len(symbol_changes)} total):**
{chr(10).join(symbols_summary) if symbols_summary else "No code symbol changes extracted."}

### REQUIRED REPORT STRUCTURE:
Please produce a concise GitHub Flavored Markdown report with these sections:
1. **Executive Overview**: High-level summary of the update and its intent.
2. **Key Code & Symbol Changes**: Notable function, method, class, or endpoint updates.
3. **Blast Radius & Downstream Ripple**: Which services, modules, or callers are directly or transitively affected.
4. **Architectural & API Contract Assessment**: Any breaking signature changes, new parameters, or modified HTTP routes.
5. **Risks & Verification Advice**: Potential side effects and recommended areas to inspect or test.
"""
        return self._sanitize_text(prompt)

    async def generate_change_summary(
        self,
        repository_name: str,
        base_ref: str,
        target_ref: str,
        file_changes: List[Dict[str, Any]],
        symbol_changes: List[Dict[str, Any]],
        impact_metrics: Dict[str, Any],
        focus: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates grounded markdown update summary with Ollama primary / Gemini fallback."""
        prompt = self._build_grounding_prompt(
            repository_name=repository_name,
            base_ref=base_ref,
            target_ref=target_ref,
            file_changes=file_changes,
            symbol_changes=symbol_changes,
            impact_metrics=impact_metrics,
            focus=focus,
        )

        messages = [
            ChatMessage(role="system", content="You are an expert software architect analyzing code changes."),
            ChatMessage(role="user", content=prompt),
        ]

        try:
            gen_res = await self.provider_manager.generate_chat(
                messages=messages,
                temperature=0.2,
                max_tokens=1500,
            )
            return {
                "ai_summary_markdown": gen_res.content,
                "provider_used": gen_res.provider_name,
                "model_used": gen_res.model_name,
                "generated_at": datetime.now(timezone.utc),
            }
        except Exception as e:
            logger.warning("AI change summary generation encountered failure: %s", e)
            # Provide deterministic grounded fallback summary
            fallback_md = (
                f"### Repository Update Summary ({base_ref} → {target_ref})\n\n"
                f"- **Files Changed:** {len(file_changes)}\n"
                f"- **Symbols Modified/Added/Deleted:** {len(symbol_changes)}\n"
                f"- **Directly Affected Dependents:** {impact_metrics.get('directly_affected', 0)}\n"
                f"- **Transitive Dependents:** {impact_metrics.get('indirectly_affected', 0)}\n\n"
                f"*Automated AI provider synthesis was temporarily unavailable. "
                f"Please review the verified Changed Files and Changed Symbols tabs directly.*"
            )
            return {
                "ai_summary_markdown": fallback_md,
                "provider_used": "deterministic_fallback",
                "model_used": "rules_engine",
                "generated_at": datetime.now(timezone.utc),
            }
