from typing import Any, Dict, List, Optional, Tuple

from app.ai.provider_manager import ProviderManager
from app.ai.schemas import ChatMessage
from app.core.logging import logger


class ExecutionExplainerService:
    """
    Generates grounded AI explanations of execution flow paths using RepoMind's
    Ollama (qwen3.5:4b) and Gemini fallback provider infrastructure.
    """

    SYSTEM_PROMPT = """You are RepoMind's Execution Flow Intelligence Engine.
Your task is to explain a static execution trace through a software repository based strictly on the provided trace evidence.

GROUNDING & TRUTHFULNESS INVARIANTS:
1. Rely EXCLUSIVELY on the provided <execution_trace> data. Do NOT invent missing functions, parameters, or behavior.
2. Clearly distinguish VERIFIED STATIC CALLS from UNCERTAINTIES (such as dynamic dispatch, external third-party calls, reflection, or unresolvable callbacks).
3. If information is ambiguous or absent from the source code, explicitly state: "Static source analysis cannot determine this runtime behavior."
4. Include exact file names and line numbers when referencing execution steps.

Output format should follow this structure:
### Summary
[Brief 2-3 sentence overview of how the operation moves from entry point to downstream services]

### Verified Execution Path
- Step 1: [Caller -> Callee at file:line] - [Purpose based on evidence]
...

### Dynamic Points & Uncertainties
- [List any dynamic calls, external boundaries, or runtime dependencies where static analysis ends]
"""

    def __init__(self, provider_manager: Optional[ProviderManager] = None) -> None:
        self.provider_manager = provider_manager or ProviderManager()

    async def explain_flow(
        self,
        repository_name: str,
        flow_title: str,
        entry_point: str,
        steps: List[Dict[str, Any]],
        nodes: List[Dict[str, Any]],
        focus_question: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Assembles grounded context from static trace steps and invokes the LLM.
        """
        # Format trace into XML evidence
        step_lines = []
        citations: List[Dict[str, Any]] = []

        for idx, s in enumerate(steps[:20]):
            caller = s.get("caller", "caller")
            callee = s.get("callee", "callee")
            data_passed = s.get("dataPassed", "")
            desc = s.get("description", "")
            status = s.get("status", "verified")

            step_lines.append(
                f"  <step order=\"{idx + 1}\" status=\"{status}\">\n"
                f"    <caller>{caller}</caller>\n"
                f"    <callee>{callee}</callee>\n"
                f"    <data_passed>{data_passed}</data_passed>\n"
                f"    <evidence>{desc}</evidence>\n"
                f"  </step>"
            )

        for n in nodes[:15]:
            fp = n.get("filePath")
            line = n.get("lineNumber", 1)
            if fp:
                citations.append({
                    "filePath": fp,
                    "startLine": line,
                    "endLine": line + 15,
                })

        context_xml = (
            f"<execution_trace repository=\"{repository_name}\" entry_point=\"{entry_point}\" title=\"{flow_title}\">\n"
            + "\n".join(step_lines)
            + "\n</execution_trace>"
        )

        user_content = (
            f"Please explain the execution flow for '{flow_title}' ({entry_point}).\n\n"
            f"{context_xml}\n\n"
        )
        if focus_question:
            user_content += f"Focus specifically on answering this question: {focus_question}\n"

        messages = [
            ChatMessage(role="system", content=self.SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_content),
        ]

        provider_used = "ollama"
        summary = ""
        verified_steps: List[str] = []
        uncertainties: List[str] = []

        try:
            gen_res = await self.provider_manager.generate_chat_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=1000,
            )
            provider_used = gen_res.provider_name
            full_text = gen_res.content

            # Parse structured sections
            summary, verified_steps, uncertainties = self._parse_llm_response(full_text, steps)
        except Exception as e:
            logger.warning("AI provider failed for execution explanation: %s", e)
            provider_used = "fallback_heuristic"
            summary = f"Execution begins at `{entry_point}` and executes {len(steps)} discovered function calls."
            verified_steps = [
                f"Step {s.get('stepOrder', idx+1)}: `{s.get('caller')}` calls `{s.get('callee')}`"
                for idx, s in enumerate(steps[:10])
            ]
            uncertainties = [
                "AI generation temporarily unavailable; displaying static AST trace summary."
            ]

        return {
            "flowId": None,
            "summary": summary,
            "verifiedSteps": verified_steps,
            "uncertainties": uncertainties,
            "citations": citations[:10],
            "providerUsed": provider_used,
        }

    def _parse_llm_response(
        self,
        text: str,
        fallback_steps: List[Dict[str, Any]],
    ) -> Tuple[str, List[str], List[str]]:
        summary = ""
        verified: List[str] = []
        uncertainties: List[str] = []

        sections = text.split("###")
        for sec in sections:
            stripped = sec.strip()
            if stripped.lower().startswith("summary"):
                summary = stripped[len("summary"):].strip()
            elif "verified" in stripped.lower():
                lines = stripped.splitlines()
                for line in lines[1:]:
                    line_s = line.strip().lstrip("-* ").strip()
                    if line_s:
                        verified.append(line_s)
            elif "uncertaint" in stripped.lower() or "dynamic" in stripped.lower():
                lines = stripped.splitlines()
                for line in lines[1:]:
                    line_s = line.strip().lstrip("-* ").strip()
                    if line_s:
                        uncertainties.append(line_s)

        if not summary:
            summary = text.split("\n\n")[0] if "\n\n" in text else text[:250]

        if not verified and fallback_steps:
            verified = [
                f"Step {s.get('stepOrder', idx+1)}: `{s.get('caller')}` invokes `{s.get('callee')}`"
                for idx, s in enumerate(fallback_steps[:8])
            ]

        if not uncertainties:
            uncertainties = ["External library boundaries and runtime dynamic imports."]

        return summary, verified, uncertainties
