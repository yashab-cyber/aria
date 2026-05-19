import json
import asyncio
import uuid
from typing import Dict, Any, Callable
from core.tool_registry import aria_tool

class DeviceManager:
    def __init__(self):
        # Maps device_name -> WebSocket
        self.connected_devices: Dict[str, Any] = {}
        # Maps device_name -> Capabilities List
        self.device_capabilities: Dict[str, list] = {}
        # Maps command_id -> asyncio.Future
        self.pending_commands: Dict[str, asyncio.Future] = {}

    async def register_device(self, websocket: Any, payload: dict):
        device_name = payload.get("name", "Unknown Device")
        self.connected_devices[device_name] = websocket
        self.device_capabilities[device_name] = payload.get("capabilities", [])
        print(f"[DeviceManager] Registered device: {device_name} (Platform: {payload.get('platform')})")
        return device_name

    def remove_device(self, device_name: str):
        if device_name in self.connected_devices:
            del self.connected_devices[device_name]
        if device_name in self.device_capabilities:
            del self.device_capabilities[device_name]
        print(f"[DeviceManager] Device disconnected: {device_name}")

    async def handle_response(self, payload: dict):
        command_id = payload.get("command_id")
        if command_id in self.pending_commands:
            future = self.pending_commands.pop(command_id)
            if not future.done():
                future.set_result(payload)

    async def execute_command(self, device_name: str, command_type: str, **kwargs) -> dict:
        if device_name not in self.connected_devices:
            return {"status": "error", "message": f"Device {device_name} is not connected."}
            
        ws = self.connected_devices[device_name]
        command_id = str(uuid.uuid4())
        
        payload = {
            "command_id": command_id,
            "type": command_type,
            **kwargs
        }
        
        future = asyncio.get_event_loop().create_future()
        self.pending_commands[command_id] = future
        
        try:
            await ws.send_json(payload)
            # Wait up to 15 seconds for a response
            response = await asyncio.wait_for(future, timeout=15.0)
            return response.get("data", response)
        except asyncio.TimeoutError:
            if command_id in self.pending_commands:
                del self.pending_commands[command_id]
            return {"status": "error", "message": "Command timed out waiting for device response."}
        except Exception as e:
            if command_id in self.pending_commands:
                del self.pending_commands[command_id]
            return {"status": "error", "message": str(e)}

    @aria_tool(
        name="list_connected_devices",
        description="Lists all Android phones/devices currently connected to ARIA via the ARIA Agent app."
    )
    def tool_list_devices(self) -> str:
        if not self.connected_devices:
            return "No devices currently connected."
        
        lines = []
        for name, caps in self.device_capabilities.items():
            lines.append(f"- {name} (Capabilities: {len(caps)} available)")
        return "\n".join(lines)
        
    @aria_tool(
        name="android_run_command",
        description="Executes a command on a connected Android device (e.g. screenshot, send_whatsapp, open_app, tap). Use list_connected_devices first to get the device_name."
    )
    async def android_run_command(self, device_name: str, command_type: str, params: str = "{}") -> str:
        parsed_params = {}
        if params:
            try:
                parsed_params = json.loads(params)
            except:
                pass
                
        try:
            result = await self.execute_command(device_name, command_type, **parsed_params)
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Failed to execute on device: {str(e)}"

device_manager = DeviceManager()

# We need to capture the main event loop when server starts so tools can use it
main_loop = None
def set_main_loop(loop):
    global main_loop
    main_loop = loop
