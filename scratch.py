import json
from core.tool_registry import registry
import modules.system.shell  # load shell tool

for s in registry.get_all_schemas():
    if s["function"]["name"] == "execute_shell":
        print(json.dumps(s, indent=2))
