from pydantic import BaseModel, Field
from typing import List
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

planner = Planner()
