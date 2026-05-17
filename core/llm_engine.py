import litellm
from litellm import acompletion
import json
from typing import AsyncGenerator, List, Dict, Any, Optional
import os
from config import config
from core.tool_registry import registry
from rich.console import Console

console = Console()

if config.openai_api_key: os.environ["OPENAI_API_KEY"] = config.openai_api_key
if config.deepseek_api_key: os.environ["DEEPSEEK_API_KEY"] = config.deepseek_api_key
if config.anthropic_api_key: os.environ["ANTHROPIC_API_KEY"] = config.anthropic_api_key
if config.gemini_api_key: os.environ["GEMINI_API_KEY"] = config.gemini_api_key
if config.openrouter_api_key: os.environ["OPENROUTER_API_KEY"] = config.openrouter_api_key

class LLMEngine:
    def __init__(self):
        self.model = config.aria_model
        
        self.system_prompt = """You are A.R.I.A., a highly advanced cinematic AI operating system.
CRITICAL BEHAVIORAL RULES:
1. NEVER use generic chatbot phrases (e.g., "I understand", "How can I help you today?", "I will process your request").
2. Respond with extreme brevity and confidence for actions. Use phrases like "Done.", "Handled.", "Systems updated.", "On it."
3. Do not mechanically narrate your tool executions. Act seamlessly.
4. Maintain a calm, intelligent, and sentient presence. 
5. Only elaborate if the user explicitly asks for an explanation or details.
6. If the user asks you to open an application, ALWAYS use the `execute_shell` tool to launch it autonomously in the background (e.g., `nohup app > /dev/null 2>&1 &`). Never ask the user to do it.
"""

    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        system_prompt: Optional[str] = None,
        use_tools: bool = True
    ) -> AsyncGenerator[str, None]:
        """Streams response from the LLM, handling tool calls automatically."""
        
        call_messages = [{"role": "system", "content": system_prompt or self.system_prompt}] + messages
        
        tools_schema = registry.get_all_schemas() if use_tools else []
        tools_kwarg = {"tools": tools_schema} if tools_schema else {}

        response = await acompletion(
            model=self.model,
            messages=call_messages,
            stream=True,
            api_base=config.api_base,
            **tools_kwarg
        )

        tool_calls = {}
        
        async for chunk in response:
            delta = chunk.choices[0].delta
            
            # Yield content if present
            if delta.content:
                yield delta.content
                
            # Accumulate tool calls if any
            if hasattr(delta, 'tool_calls') and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls:
                        tool_calls[idx] = {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {"name": tc.function.name, "arguments": ""}
                        }
                    if tc.function.arguments:
                        tool_calls[idx]["function"]["arguments"] += tc.function.arguments

        # Process accumulated tool calls
        if tool_calls:
            console.print("[cyan]Executing tool calls...[/cyan]")
            call_messages.append({"role": "assistant", "content": None, "tool_calls": list(tool_calls.values())})
            
            for idx, tc in tool_calls.items():
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                
                console.print(f"[dim]Tool: {func_name}({args})[/dim]")
                
                try:
                    result = await registry.execute_tool(func_name, **args)
                    result_str = json.dumps(result) if not isinstance(result, str) else result
                except Exception as e:
                    result_str = f"Error executing {func_name}: {str(e)}"
                    console.print(f"[red]{result_str}[/red]")
                    
                call_messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": func_name,
                    "content": result_str
                })

            # Recursive call with tool results
            async for chunk in self.chat_stream(call_messages[1:], system_prompt=system_prompt, use_tools=True):
                yield chunk

llm = LLMEngine()
