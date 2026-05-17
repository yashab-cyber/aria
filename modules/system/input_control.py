import pyautogui
from core.tool_registry import aria_tool

class InputControl:
    def __init__(self):
        # Failsafe: moving mouse to 0,0 aborts pyautogui
        pyautogui.FAILSAFE = True
        
    @aria_tool(name="type_text", description="Types text using the keyboard.")
    async def type_text(self, text: str, interval: float = 0.05) -> str:
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: pyautogui.write(text, interval=interval))
            return f"Typed: {text}"
        except Exception as e:
            return f"Failed to type: {str(e)}"
            
    @aria_tool(name="press_key", description="Presses a specific keyboard key (e.g., 'enter', 'esc', 'ctrl+c').")
    async def press_key(self, key_combination: str) -> str:
        try:
            keys = key_combination.split('+')
            if len(keys) > 1:
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(keys[0])
            return f"Pressed: {key_combination}"
        except Exception as e:
            return f"Failed to press key: {str(e)}"

    @aria_tool(name="mouse_click", description="Clicks the mouse at current position or specified coordinates.")
    async def mouse_click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> str:
        try:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            pos_str = f"at ({x},{y})" if x is not None and y is not None else "at current position"
            return f"Clicked {button} {clicks} times {pos_str}"
        except Exception as e:
            return f"Failed to click: {str(e)}"

input_control = InputControl()
