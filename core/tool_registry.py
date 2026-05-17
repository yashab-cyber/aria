import inspect
from typing import Callable, Dict, Any, List, Optional
from pydantic import BaseModel, create_model

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Callable] = {}
        self.tool_schemas: List[Dict[str, Any]] = []

    def register(self, name: Optional[str] = None, description: Optional[str] = None):
        """
        Decorator to register a function as an A.R.I.A tool.
        Extracts type hints and docstrings to build OpenAI function schemas.
        """
        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_desc = description or inspect.getdoc(func) or f"Tool: {tool_name}"
            
            self.tools[tool_name] = func
            
            # Generate JSON schema from function signature using Pydantic
            sig = inspect.signature(func)
            fields = {}
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                annotation = param.annotation if param.annotation != inspect.Parameter.empty else str
                default = param.default if param.default != inspect.Parameter.empty else ...
                fields[param_name] = (annotation, default)
            
            # Create a dynamic Pydantic model for the parameters
            if fields:
                param_model = create_model(f"{tool_name}Params", **fields)
                parameters = param_model.model_json_schema()
                # Remove title properties added by pydantic
                parameters.pop("title", None)
            else:
                parameters = {"type": "object", "properties": {}}
                
            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_desc,
                    "parameters": parameters
                }
            }
            self.tool_schemas.append(schema)
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self.tools.get(name)

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        return self.tool_schemas

    async def execute_tool(self, name: str, **kwargs) -> Any:
        func = self.get_tool(name)
        if not func:
            raise ValueError(f"Tool {name} not found")
            
        # Magic to find the instance for unbound class methods
        sig = inspect.signature(func)
        if "self" in sig.parameters and "self" not in kwargs:
            mod = inspect.getmodule(func)
            if mod and '.' in func.__qualname__:
                class_name = func.__qualname__.split('.')[0]
                for var_name, obj in vars(mod).items():
                    if type(obj).__name__ == class_name:
                        kwargs["self"] = obj
                        break
        
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        else:
            return func(**kwargs)

# Global registry instance
registry = ToolRegistry()

# Alias for the decorator
aria_tool = registry.register
