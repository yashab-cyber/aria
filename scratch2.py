import asyncio
from core.tool_registry import registry
import modules.devices.device_manager

async def test():
    try:
        res = await registry.execute_tool("android_run_command", device_name="motorola edge 60 fusion", command_type="open_app", params='{"app_name":"com.whatsapp"}')
        print(f"Result: {res}")
    except Exception as e:
        import traceback
        traceback.print_exc()

asyncio.run(test())
