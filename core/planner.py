from pydantic import BaseModel, Field
from typing import List, Tuple
import json
from core.llm_engine import llm
from config import config
import litellm
from litellm import acompletion
from core.tool_registry import registry
from rich.console import Console

console = Console()

class PlanStep(BaseModel):
    step_id: int
    description: str = Field(description="Description of what this step does")
    tool_name: str = Field(description="Name of the tool to execute")
    tool_args: dict = Field(default_factory=dict, description="Arguments for the tool")
    dependencies: List[int] = Field(default_factory=list, description="List of step_ids that must complete before this one")

class Plan(BaseModel):
    steps: List[PlanStep]

class Planner:
    async def create_plan(self, objective: str) -> Plan:
        """Decomposes a complex objective into a structured plan."""
        tools_info = []
        for schema in registry.get_all_schemas():
            tools_info.append(f"- {schema['function']['name']}: {schema['function']['description']}")
            
        tools_str = "\n".join(tools_info)
        
        prompt = f"""You are A.R.I.A.'s planning engine. Break down the following objective into a sequence of executable tool steps.
Objective: "{objective}"

Available tools:
{tools_str}

Create a logical step-by-step plan. Ensure dependencies are correct.
"""
        response = await acompletion(
            model=llm.model,
            messages=[{"role": "user", "content": prompt}],
            functions=[{
                "name": "submit_plan",
                "description": "Submit the generated execution plan",
                "parameters": Plan.model_json_schema()
            }],
            function_call={"name": "submit_plan"},
            temperature=0.2,
            api_base=config.api_base
        )
        
        args = response.choices[0].message.function_call.arguments
        return Plan(**json.loads(args))

    async def execute_plan(self, plan: Plan):
        """Executes a plan step by step, respecting dependencies."""
        results = {}
        
        for step in sorted(plan.steps, key=lambda x: x.step_id):
            # Check dependencies
            for dep in step.dependencies:
                if dep not in results:
                    console.print(f"[red]Warning: Dependency {dep} not met for step {step.step_id}[/red]")
            
            console.print(f"[cyan]Executing Step {step.step_id}: {step.description}[/cyan]")
            try:
                # Naive dynamic argument resolution
                args = step.tool_args.copy()
                for k, v in args.items():
                    if isinstance(v, str) and "{{" in v and "}}" in v:
                        # Very simple templating for passing results between steps
                        pass
                        
                res = await registry.execute_tool(step.tool_name, **args)
                results[step.step_id] = res
                console.print(f"[green]Step {step.step_id} Complete[/green]")
            except Exception as e:
                console.print(f"[red]Step {step.step_id} Failed: {str(e)}[/red]")
                results[step.step_id] = f"Error: {str(e)}"
                break # Stop on failure for now
                
        return results

    # ── Reflection-Aware Methods ─────────────────────────────────────────

    async def create_plan_with_reflection(self, objective: str) -> Tuple[Plan, list]:
        """
        Generate a plan with iterative self-reflection.

        Loop: generate → reflect → revise (up to max revisions).
        Returns the final approved plan and a list of reflection verdicts.
        """
        from core.reflection import reflection_engine

        max_revisions = config.reflection_max_plan_revisions
        threshold = config.reflection_plan_threshold
        reflections = []
        previous_critique = None

        for iteration in range(1, max_revisions + 1):
            console.print(f"\n[bold cyan]🔍 Plan Generation — Iteration {iteration}/{max_revisions}[/bold cyan]")

            # Generate or revise
            if previous_critique is None:
                plan = await self.create_plan(objective)
            else:
                plan = await self._revise_plan(objective, plan, previous_critique)

            # Reflect
            verdict = await reflection_engine.reflect_on_plan(objective, plan.steps)
            reflections.append(verdict)

            if verdict.approved and verdict.score >= threshold:
                console.print(f"[bold green]✅ Plan approved on iteration {iteration} (score: {verdict.score:.2f})[/bold green]")
                return plan, reflections

            # Plan rejected — prepare critique for next revision
            previous_critique = self._format_critique(verdict)
            console.print(f"[yellow]⚠️  Plan revision needed (score: {verdict.score:.2f}). Revising...[/yellow]")

        # Exhausted revisions — force-accept the last plan
        console.print(f"[bold yellow]⚠️  Max revisions reached. Proceeding with best-effort plan (score: {verdict.score:.2f})[/bold yellow]")
        return plan, reflections

    async def execute_plan_with_reflection(
        self, plan: Plan, objective: str
    ) -> Tuple[dict, list]:
        """
        Execute a plan with post-execution reflection and retry.

        Loop: execute → reflect on results → re-plan if needed (up to max retries).
        Returns the final results and a list of reflection verdicts.
        """
        from core.reflection import reflection_engine

        max_retries = config.reflection_max_execution_retries
        threshold = config.reflection_result_threshold
        reflections = []
        current_plan = plan

        for attempt in range(1, max_retries + 1):
            console.print(f"\n[bold cyan]⚡ Execution Attempt {attempt}/{max_retries}[/bold cyan]")

            results = await self.execute_plan(current_plan)

            # Reflect on results
            verdict = await reflection_engine.reflect_on_results(
                objective, current_plan.steps, results
            )
            reflections.append(verdict)

            if verdict.approved and verdict.score >= threshold:
                console.print(f"[bold green]✅ Execution results accepted (score: {verdict.score:.2f})[/bold green]")
                return results, reflections

            if attempt < max_retries:
                console.print(f"[yellow]🔄 Results insufficient (score: {verdict.score:.2f}). Re-planning...[/yellow]")
                # Re-plan incorporating failure context
                current_plan = await self._replan_after_failure(
                    objective, current_plan, results, verdict
                )
            else:
                console.print(f"[bold yellow]⚠️  Max retries reached. Returning best-effort results.[/bold yellow]")

        return results, reflections

    # ── Private Helpers ──────────────────────────────────────────────────

    async def _revise_plan(self, objective: str, previous_plan: Plan, critique: str) -> Plan:
        """Generate a revised plan incorporating reflection feedback."""
        tools_info = []
        for schema in registry.get_all_schemas():
            tools_info.append(f"- {schema['function']['name']}: {schema['function']['description']}")
        tools_str = "\n".join(tools_info)

        prev_steps = "\n".join(
            f"  Step {s.step_id}: [{s.tool_name}] {s.description}"
            for s in previous_plan.steps
        )

        prompt = f"""You are A.R.I.A.'s planning engine. Your previous plan was REJECTED by the reflection system.

OBJECTIVE: "{objective}"

PREVIOUS PLAN (REJECTED):
{prev_steps}

REFLECTION FEEDBACK:
{critique}

Available tools:
{tools_str}

Generate a REVISED plan that addresses ALL of the feedback above. Ensure dependencies are correct.
"""
        response = await acompletion(
            model=llm.model,
            messages=[{"role": "user", "content": prompt}],
            functions=[{
                "name": "submit_plan",
                "description": "Submit the revised execution plan",
                "parameters": Plan.model_json_schema()
            }],
            function_call={"name": "submit_plan"},
            temperature=0.3,  # Slightly higher temp for creative revision
            api_base=config.api_base
        )

        args = response.choices[0].message.function_call.arguments
        return Plan(**json.loads(args))

    async def _replan_after_failure(
        self, objective: str, failed_plan: Plan, results: dict, verdict
    ) -> Plan:
        """Generate a new plan after execution failure, informed by what went wrong."""
        tools_info = []
        for schema in registry.get_all_schemas():
            tools_info.append(f"- {schema['function']['name']}: {schema['function']['description']}")
        tools_str = "\n".join(tools_info)

        failed_steps = "\n".join(
            f"  Step {s.step_id}: [{s.tool_name}] {s.description} → Result: {str(results.get(s.step_id, 'NOT EXECUTED'))[:200]}"
            for s in failed_plan.steps
        )

        prompt = f"""You are A.R.I.A.'s planning engine. The previous plan was EXECUTED but the results were UNSATISFACTORY.

OBJECTIVE: "{objective}"

PREVIOUS PLAN + RESULTS:
{failed_steps}

REFLECTION FEEDBACK:
Critique: {verdict.critique}
Suggestions: {'; '.join(verdict.suggestions)}

Available tools:
{tools_str}

Generate a NEW plan that takes a different approach to achieve the objective. Learn from the failures above.
Ensure dependencies are correct.
"""
        response = await acompletion(
            model=llm.model,
            messages=[{"role": "user", "content": prompt}],
            functions=[{
                "name": "submit_plan",
                "description": "Submit the new execution plan",
                "parameters": Plan.model_json_schema()
            }],
            function_call={"name": "submit_plan"},
            temperature=0.4,  # Higher temp to explore different approaches
            api_base=config.api_base
        )

        args = response.choices[0].message.function_call.arguments
        return Plan(**json.loads(args))

    @staticmethod
    def _format_critique(verdict) -> str:
        """Format a reflection verdict into a critique string for the LLM."""
        parts = [f"Score: {verdict.score:.2f}", f"Critique: {verdict.critique}"]
        if verdict.suggestions:
            parts.append("Required improvements:")
            for i, s in enumerate(verdict.suggestions, 1):
                parts.append(f"  {i}. {s}")
        return "\n".join(parts)

planner = Planner()
