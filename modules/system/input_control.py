"""
A.R.I.A. Desktop Input & Control — God-level system control.

Provides full desktop automation: mouse, keyboard, drag, scroll,
window management, clipboard, screenshots, and app launching.
"""

import pyautogui
import asyncio
import subprocess
import os
from core.tool_registry import aria_tool

# Safety: moving mouse to corner (0,0) aborts pyautogui
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1


class InputControl:

    # ── Mouse ────────────────────────────────────────────────────────

    @aria_tool(name="mouse_click", description="Clicks at coordinates (x,y) or current position. button: 'left','right','middle'. clicks: 1-3.")
    async def mouse_click(self, x: int = -1, y: int = -1, button: str = "left", clicks: int = 1) -> str:
        try:
            kw = {"button": button, "clicks": clicks}
            if x >= 0 and y >= 0:
                kw["x"], kw["y"] = x, y
            await asyncio.get_event_loop().run_in_executor(None, lambda: pyautogui.click(**kw))
            pos = f"({x},{y})" if x >= 0 else "current position"
            return f"Clicked {button} {clicks}x at {pos}."
        except Exception as e:
            return f"Click failed: {e}"

    @aria_tool(name="mouse_move", description="Moves the mouse cursor to exact pixel coordinates (x, y).")
    async def mouse_move(self, x: int, y: int, duration: float = 0.3) -> str:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.moveTo(x, y, duration=duration)
            )
            return f"Mouse moved to ({x}, {y})."
        except Exception as e:
            return f"Move failed: {e}"

    @aria_tool(name="mouse_drag", description="Click-and-drag from (start_x, start_y) to (end_x, end_y).")
    async def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5, button: str = "left") -> str:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: (
                    pyautogui.moveTo(start_x, start_y, duration=0.15),
                    pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
                )
            )
            return f"Dragged from ({start_x},{start_y}) to ({end_x},{end_y})."
        except Exception as e:
            return f"Drag failed: {e}"

    @aria_tool(name="mouse_scroll", description="Scrolls the mouse wheel. Positive = up, negative = down. Use amount for scroll distance.")
    async def mouse_scroll(self, amount: int = -3, x: int = -1, y: int = -1) -> str:
        try:
            kw = {}
            if x >= 0 and y >= 0:
                kw["x"], kw["y"] = x, y
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: pyautogui.scroll(amount, **kw)
            )
            direction = "up" if amount > 0 else "down"
            return f"Scrolled {direction} by {abs(amount)} clicks."
        except Exception as e:
            return f"Scroll failed: {e}"

    # ── Keyboard ─────────────────────────────────────────────────────

    def _needs_clipboard_paste(self, text: str) -> bool:
        """Detect if text contains characters that pyautogui.write() cannot handle."""
        # pyautogui.write() only supports characters typeable with a single keystroke
        # It silently fails on newlines, tabs, and many special characters
        special_chars = set('(){}[]<>:;@#$%^&*~`|\\/"\'!?\n\t')
        return bool(set(text) & special_chars) or len(text) > 100

    async def _clipboard_paste(self, text: str) -> bool:
        """Copy text to clipboard via xclip, then Ctrl+V to paste. Returns True on success."""
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            proc.communicate(text.encode("utf-8"))
            if proc.returncode != 0:
                return False
            await asyncio.sleep(0.15)  # Let clipboard settle
            pyautogui.hotkey("ctrl", "v")
            await asyncio.sleep(0.3)  # Let paste complete
            return True
        except FileNotFoundError:
            # Fallback: try xsel
            try:
                proc = subprocess.Popen(
                    ["xsel", "--clipboard", "--input"],
                    stdin=subprocess.PIPE
                )
                proc.communicate(text.encode("utf-8"))
                if proc.returncode != 0:
                    return False
                await asyncio.sleep(0.15)
                pyautogui.hotkey("ctrl", "v")
                await asyncio.sleep(0.3)
                return True
            except Exception:
                return False
        except Exception:
            return False

    @aria_tool(name="type_text", description="Types text into the currently focused window. For simple text uses keyboard input; for code or multi-line text with special characters, uses clipboard paste automatically.")
    async def type_text(self, text: str, interval: float = 0.04) -> str:
        try:
            if self._needs_clipboard_paste(text):
                # Use clipboard approach for complex text (code, special chars, etc.)
                success = await self._clipboard_paste(text)
                if success:
                    preview = text[:100].replace('\n', '\\n')
                    return f"Typed (via paste): {preview}"
                else:
                    return "Type failed: clipboard tools (xclip/xsel) not available. Install: sudo apt install xclip"
            else:
                # Simple text — use key-by-key typing
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: pyautogui.write(text, interval=interval)
                )
                return f"Typed: {text[:100]}"
        except Exception as e:
            return f"Type failed: {e}"

    @aria_tool(name="write_to_focused_window", description="Writes multi-line text or code into the currently focused window (e.g. Mousepad, gedit, terminal). Uses clipboard paste to handle all characters including brackets, newlines, indentation. Use this for writing code into editors.")
    async def write_to_focused_window(self, text: str) -> str:
        """Reliably writes any text (including code) into the currently focused application."""
        try:
            # 1. Verify a window is focused
            proc = await asyncio.create_subprocess_shell(
                "xdotool getactivewindow getwindowname",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            window_name = stdout.decode().strip()
            if not window_name:
                return "No focused window detected. Please open or focus an application first."

            # 2. Small delay to ensure window is ready for input
            await asyncio.sleep(0.3)

            # 3. Click in the window to ensure text cursor is active
            pyautogui.click()
            await asyncio.sleep(0.2)

            # 4. Paste via clipboard
            success = await self._clipboard_paste(text)
            if success:
                line_count = text.count('\n') + 1
                preview = text[:80].replace('\n', '\\n')
                return f"Written {line_count} lines to '{window_name}': {preview}..."
            else:
                return "Write failed: clipboard tools (xclip/xsel) not available. Install: sudo apt install xclip"
        except Exception as e:
            return f"Write to window failed: {e}"

    @aria_tool(name="press_key", description="Presses a key or combo (e.g. 'enter', 'ctrl+c', 'alt+f4', 'super').")
    async def press_key(self, key_combination: str) -> str:
        try:
            keys = [k.strip() for k in key_combination.split('+')]
            if len(keys) > 1:
                pyautogui.hotkey(*keys)
            else:
                pyautogui.press(keys[0])
            return f"Pressed: {key_combination}"
        except Exception as e:
            return f"Key press failed: {e}"

    # ── Screenshot ───────────────────────────────────────────────────

    @aria_tool(name="take_screenshot_to_file", description="Saves a screenshot to a file. Returns the file path. Default: ~/screenshot.png")
    async def take_screenshot_to_file(self, filepath: str = "") -> str:
        try:
            if not filepath:
                filepath = os.path.expanduser("~/screenshot.png")
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            screenshot = pyautogui.screenshot()
            screenshot.save(filepath)
            return f"Screenshot saved to: {filepath}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    # ── Window Management ────────────────────────────────────────────

    @aria_tool(name="get_active_window", description="Gets the title, position, and size of the currently focused window.")
    async def get_active_window(self) -> str:
        try:
            # Use xdotool on Linux
            proc = await asyncio.create_subprocess_shell(
                "xdotool getactivewindow getwindowname && xdotool getactivewindow getwindowgeometry",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode().strip()
            if output:
                return f"Active window:\n{output}"
            return "Could not detect active window."
        except Exception as e:
            return f"Window detection failed: {e}"

    @aria_tool(name="manage_window", description="Control a window by title. action: 'minimize','maximize','restore','close','focus','resize'. For resize pass width and height.")
    async def manage_window(self, title: str, action: str = "focus", width: int = 0, height: int = 0) -> str:
        try:
            # Find window ID by title
            find_cmd = f'xdotool search --name "{title}" | head -1'
            proc = await asyncio.create_subprocess_shell(
                find_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            wid = stdout.decode().strip()
            if not wid:
                return f"No window found matching: '{title}'"

            cmds = {
                "focus": f"xdotool windowactivate {wid}",
                "minimize": f"xdotool windowminimize {wid}",
                "maximize": f"wmctrl -i -r {wid} -b add,maximized_vert,maximized_horz 2>/dev/null || xdotool windowsize {wid} 100% 100%",
                "restore": f"wmctrl -i -r {wid} -b remove,maximized_vert,maximized_horz 2>/dev/null || true",
                "close": f"xdotool windowclose {wid}",
                "resize": f"xdotool windowsize {wid} {width} {height}" if width and height else "echo 'Need width and height'",
            }
            cmd = cmds.get(action.lower())
            if not cmd:
                return f"Unknown action: '{action}'. Use: minimize, maximize, restore, close, focus, resize."

            proc2 = await asyncio.create_subprocess_shell(
                cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            await proc2.communicate()
            return f"Window '{title}' → {action}."
        except Exception as e:
            return f"Window management failed: {e}"

    # ── Clipboard ────────────────────────────────────────────────────

    @aria_tool(name="clipboard_copy", description="Copies text to the system clipboard.")
    async def clipboard_copy(self, text: str) -> str:
        try:
            import subprocess
            proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
            proc.communicate(text.encode("utf-8"))
            return f"Copied to clipboard: {text[:100]}"
        except FileNotFoundError:
            # Fallback: try xsel
            try:
                proc = subprocess.Popen(["xsel", "--clipboard", "--input"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"))
                return f"Copied to clipboard: {text[:100]}"
            except Exception:
                return "Clipboard tools (xclip/xsel) not found. Install: sudo apt install xclip"
        except Exception as e:
            return f"Clipboard copy failed: {e}"

    @aria_tool(name="clipboard_paste", description="Reads and returns the current content of the system clipboard.")
    async def clipboard_paste(self) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                "xclip -selection clipboard -o 2>/dev/null || xsel --clipboard --output 2>/dev/null",
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            content = stdout.decode().strip()
            return content if content else "Clipboard is empty."
        except Exception as e:
            return f"Clipboard paste failed: {e}"

    # ── Application Launcher ─────────────────────────────────────────

    @aria_tool(name="launch_application", description="Launches an application by name silently in the background (e.g. 'firefox', 'terminal', 'nautilus').")
    async def launch_application(self, app_name: str) -> str:
        try:
            # Common aliases
            aliases = {
                "terminal": "x-terminal-emulator",
                "files": "nautilus",
                "file manager": "nautilus",
                "text editor": "gedit",
                "calculator": "gnome-calculator",
                "settings": "gnome-control-center",
                "browser": "xdg-open http://",
            }
            cmd = aliases.get(app_name.lower(), app_name)
            await asyncio.create_subprocess_shell(
                f"nohup {cmd} > /dev/null 2>&1 &",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.sleep(2.0)  # Give the app time to open before the next step
            return f"Launched: {app_name}"
        except Exception as e:
            return f"Launch failed: {e}"

    @aria_tool(name="wait", description="Pauses execution for a specified number of seconds. Useful to wait for applications to load or UI elements to appear.")
    async def wait(self, seconds: float = 2.0) -> str:
        try:
            await asyncio.sleep(seconds)
            return f"Waited for {seconds} seconds."
        except Exception as e:
            return f"Wait failed: {e}"

input_control = InputControl()
