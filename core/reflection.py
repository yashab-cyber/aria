"""
A.R.I.A. Reflection Engine — Self-evaluation for agentic planning loops.

Provides LLM-as-judge evaluation at two stages:
  1. Plan-quality reflection (pre-execution): Is the plan coherent, complete, and correct?
  2. Execution-result reflection (post-execution): Did the results satisfy the objective?
"""

from pydantic import BaseModel, Field
from typing import List, Optional
import json
from core.llm_engine import llm
from config import config
from litellm import acompletion
from rich.console import Console

console = Console()


# ── Structured Verdict ──────────────────────────────────────────────────────

class ReflectionVerdict(BaseModel):
    """Structured output from a reflection evaluation."""
    approved: bool = Field(description="Whether the artifact passes quality check")
    score: float = Field(description="Quality score between 0.0 and 1.0")
    critique: str = Field(description="Concise explanation of issues found, or 'No issues.' if approved")
    suggestions: List[str] = Field(
        default_factory=list,
        description="Specific, actionable improvements to apply on the next revision"
    )


# ── Reflection Engine ───────────────────────────────────────────────────────

class ReflectionEngine:
    """LLM-as-judge evaluator for ARIA's agentic planning loop."""

    # ── Plan Quality Reflection ──────────────────────────────────────────

    async def reflect_on_plan(self, objective: str, plan_steps: list) -> ReflectionVerdict:
        """
        Evaluate a generated plan BEFORE execution.

        Checks:
          - Are all steps logically ordered with correct dependencies?
          - Are the chosen tools appropriate for each step?
          - Is the plan complete — does it cover the full objective?
          - Are there redundant or missing steps?
        """
        steps_desc = "\n".join(
            f"  Step {s.step_id}: [{s.tool_name}] {s.description} "
            f"(deps: {s.dependencies}, args: {json.dumps(s.tool_args)})"
            for s in plan_steps
        )

        prompt = f"""You are A.R.I.A.'s self-reflection module — a ruthless quality gate.

OBJECTIVE the plan is supposed to achieve:
\"{objective}\"

GENERATED PLAN:
{steps_desc}

Evaluate this plan on these criteria:
1. **Completeness** — Does the plan fully address the objective? Any missing steps?
2. **Correctness** — Are tool names valid and arguments plausible?
3. **Dependencies** — Are step dependencies logically ordered? No circular or missing deps?
4. **Efficiency** — Any redundant or unnecessary steps?
5. **Robustness** — Does the plan handle likely failure points?

Be critical. A score of 1.0 means flawless. A score below 0.7 means the plan MUST be revised.
If approved, set critique to "No issues." and leave suggestions empty.
"""

        return await self._evaluate(prompt)

    # ── Execution Result Reflection ──────────────────────────────────────

    async def reflect_on_results(
        self,
        objective: str,
        plan_steps: list,
        results: dict,
    ) -> ReflectionVerdict:
        """
        Evaluate execution results AFTER a plan has run.

        Checks:
          - Did the results actually satisfy the original objective?
          - Were there step failures that need re-planning?
          - Is the output quality acceptable?
        """
        steps_desc = "\n".join(
            f"  Step {s.step_id}: [{s.tool_name}] {s.description}"
            for s in plan_steps
        )

        results_desc = "\n".join(
            f"  Step {sid}: {str(res)[:500]}"  # Truncate long results
            for sid, res in results.items()
        )

        prompt = f"""You are A.R.I.A.'s self-reflection module evaluating EXECUTION RESULTS.

ORIGINAL OBJECTIVE:
\"{objective}\"

PLAN THAT WAS EXECUTED:
{steps_desc}

EXECUTION RESULTS:
{results_desc}

Evaluate:
1. **Objective Satisfaction** — Do the results actually fulfill what the user asked for?
2. **Error Analysis** — Did any steps produce errors? Are those errors recoverable?
3. **Output Quality** — Is the output useful and complete, or partial/degraded?
4. **Retry Worthiness** — If the results are poor, would re-planning with different tools/args likely succeed?

A score of 1.0 means the objective is perfectly satisfied.
A score below 0.6 means the execution FAILED and a retry is warranted.
If approved, set critique to "No issues." and leave suggestions empty.
"""

        return await self._evaluate(prompt)

    # ── Private Evaluation Core ──────────────────────────────────────────

    async def _evaluate(self, prompt: str) -> ReflectionVerdict:
        """Run the LLM-as-judge and parse the structured verdict."""
        try:
            response = await acompletion(
                model=llm.model,
                messages=[{"role": "user", "content": prompt}],
                functions=[{
                    "name": "submit_reflection",
                    "description": "Submit the reflection verdict",
                    "parameters": ReflectionVerdict.model_json_schema()
                }],
                function_call={"name": "submit_reflection"},
                temperature=0.1,  # Low temp for consistent, deterministic judgments
                api_base=config.api_base,
            )

            args = response.choices[0].message.function_call.arguments
            verdict = ReflectionVerdict(**json.loads(args))

            # Log reflection result
            status = "✅ APPROVED" if verdict.approved else "❌ REJECTED"
            console.print(
                f"[bold {'green' if verdict.approved else 'red'}]"
                f"Reflection {status} (score: {verdict.score:.2f})[/bold {'green' if verdict.approved else 'red'}]"
            )
            if not verdict.approved:
                console.print(f"[yellow]Critique: {verdict.critique}[/yellow]")
                for i, s in enumerate(verdict.suggestions, 1):
                    console.print(f"[yellow]  {i}. {s}[/yellow]")

            return verdict

        except Exception as e:
            console.print(f"[red]Reflection engine error: {e} — defaulting to approved[/red]")
            # Fail-open: if reflection itself breaks, don't block the pipeline
            return ReflectionVerdict(
                approved=True,
                score=0.5,
                critique=f"Reflection failed: {str(e)}",
                suggestions=[]
            )


# Global instance
reflection_engine = ReflectionEngine()
