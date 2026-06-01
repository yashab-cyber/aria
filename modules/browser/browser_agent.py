"""
A.R.I.A. Browser Agent — Full persistent browser automation.

Navigate, screenshot, click, fill forms, execute JS, manage tabs, persist sessions,
control scrolls, hover, and run in headed/headless mode.
Powered by Playwright (Chromium).
"""

import os
import base64
import shutil
import asyncio
from playwright.async_api import async_playwright
from core.tool_registry import aria_tool


class BrowserAgent:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.headless = True
        self.user_data_dir = os.path.expanduser("~/.aria_browser_profile")

    async def _ensure_started(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            
            # Using persistent context to remember logins, cookies, localStorage
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=self.user_data_dir,
                headless=self.headless,
                viewport={"width": 1920, "height": 1080},
                accept_downloads=True
            )
            
            # Set default page
            pages = self.context.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await self.context.new_page()

    # ── Configuration & Restarts ─────────────────────────────────────

    @aria_tool(name="browser_configure", description="Configures the browser settings. Use headless=False to open browser window on host desktop. Use clear_session=True to erase cookie/session history.")
    async def configure(self, headless: bool = None, clear_session: bool = False) -> str:
        try:
            # Shut down if running
            await self.shutdown()
            
            if clear_session:
                if os.path.exists(self.user_data_dir):
                    shutil.rmtree(self.user_data_dir, ignore_errors=True)
                
            if headless is not None:
                self.headless = headless
                
            # Restart
            await self._ensure_started()
            mode = "headless" if self.headless else "headed (visible window)"
            session_status = "session cleared" if clear_session else "session preserved"
            return f"Browser restarted in {mode} mode ({session_status})."
        except Exception as e:
            return f"Failed to configure browser: {e}"

    # ── Tab Management ───────────────────────────────────────────────

    @aria_tool(name="browser_tab_control", description="Manage browser tabs. action: 'list', 'new', 'switch', 'close'. index: 0-indexed tab index (for switch or close).")
    async def tab_control(self, action: str = "list", index: int = -1, url: str = "") -> str:
        await self._ensure_started()
        action = action.lower()
        try:
            pages = self.context.pages
            if action == "list":
                titles = []
                for i, p in enumerate(pages):
                    try:
                        title = await p.title()
                        titles.append(f"[{i}]: {title} ({p.url})")
                    except Exception:
                        titles.append(f"[{i}]: (Dead Page)")
                active_idx = pages.index(self.page) if self.page in pages else -1
                return f"Active Tab Index: {active_idx}\nOpen Tabs:\n" + "\n".join(titles)
            
            elif action == "new":
                new_p = await self.context.new_page()
                self.page = new_p
                if url:
                    if not url.startswith("http"):
                        url = "https://" + url
                    await new_p.goto(url, wait_until="domcontentloaded", timeout=15000)
                title = await new_p.title()
                return f"Opened new tab. Title: {title} | URL: {new_p.url}"
                
            elif action == "switch":
                if index < 0 or index >= len(pages):
                    return f"Invalid tab index {index}. Total tabs: {len(pages)}"
                self.page = pages[index]
                title = await self.page.title()
                return f"Switched focus to tab [{index}]: {title}."
                
            elif action == "close":
                if index < 0 or index >= len(pages):
                    return f"Invalid tab index {index}. Total tabs: {len(pages)}"
                target_p = pages[index]
                await target_p.close()
                # Update current active page if the active one got closed
                pages = self.context.pages
                if target_p == self.page or self.page not in pages:
                    self.page = pages[0] if pages else await self.context.new_page()
                return f"Closed tab [{index}]. Active page updated."
                
            else:
                return f"Unknown tab action: '{action}'. Use list, new, switch, close."
        except Exception as e:
            return f"Tab control action failed: {e}"

    # ── Scroll Control ────────────────────────────────────────────────

    @aria_tool(name="browser_scroll", description="Scrolls the page. direction: 'down' (default), 'up', 'top', 'bottom'. value: scroll amount in pixels (e.g. 500).")
    async def scroll(self, direction: str = "down", value: int = 500) -> str:
        await self._ensure_started()
        direction = direction.lower()
        try:
            if direction == "down":
                await self.page.evaluate(f"window.scrollBy(0, {value})")
                return f"Scrolled down by {value} pixels."
            elif direction == "up":
                await self.page.evaluate(f"window.scrollBy(0, -{value})")
                return f"Scrolled up by {value} pixels."
            elif direction == "top":
                await self.page.evaluate("window.scrollTo(0, 0)")
                return "Scrolled to top of the page."
            elif direction == "bottom":
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                return "Scrolled to bottom of the page."
            else:
                return f"Unknown scroll direction: {direction}."
        except Exception as e:
            return f"Scroll failed: {e}"

    # ── Navigation History ───────────────────────────────────────────

    @aria_tool(name="browser_history", description="Navigates history. action: 'back', 'forward', 'reload'.")
    async def history(self, action: str) -> str:
        await self._ensure_started()
        action = action.lower()
        try:
            if action == "back":
                await self.page.go_back(wait_until="domcontentloaded", timeout=10000)
                return f"Navigated back to: {self.page.url}"
            elif action == "forward":
                await self.page.go_forward(wait_until="domcontentloaded", timeout=10000)
                return f"Navigated forward to: {self.page.url}"
            elif action == "reload":
                await self.page.reload(wait_until="domcontentloaded", timeout=10000)
                return f"Reloaded page: {self.page.url}"
            else:
                return f"Unknown history action: {action}. Use back, forward, reload."
        except Exception as e:
            return f"History navigation failed: {e}"

    # ── Hover Element ─────────────────────────────────────────────────

    @aria_tool(name="browser_hover", description="Hovers the mouse over an element on the page. Use CSS selector or text.")
    async def hover(self, selector: str = "", text: str = "") -> str:
        await self._ensure_started()
        try:
            if text:
                loc = self.page.get_by_text(text, exact=False).first
                await loc.hover(timeout=5000)
                return f"Hovered over element with text: '{text}'"
            elif selector:
                await self.page.hover(selector, timeout=5000)
                return f"Hovered over selector: '{selector}'"
            else:
                return "Provide either selector or text."
        except Exception as e:
            return f"Hover failed: {str(e)}"

    # ── Direct Viewport Clicks ───────────────────────────────────────

    @aria_tool(name="browser_click_coords", description="Clicks at exact viewport coordinates (x, y) on the browser page.")
    async def click_coords(self, x: int, y: int, button: str = "left") -> str:
        await self._ensure_started()
        try:
            await self.page.mouse.click(x, y, button=button)
            return f"Clicked browser page at ({x}, {y}) using {button} button."
        except Exception as e:
            return f"Coordinate click failed: {e}"

    # ── Page HTML & Link Extraction ──────────────────────────────────

    @aria_tool(name="browser_extract_html", description="Extracts the raw HTML or structured link elements of the page. mode: 'links' (default) or 'html'.")
    async def extract_html(self, mode: str = "links") -> str:
        await self._ensure_started()
        mode = mode.lower()
        try:
            if mode == "html":
                html = await self.page.content()
                if len(html) > 5000:
                    html = html[:5000] + "\n...[truncated]..."
                return html
            else:
                # Links mode — extracts all visible links/buttons with text
                links = await self.page.evaluate("""() => {
                    let items = [];
                    document.querySelectorAll('a, button').forEach(el => {
                        let text = el.innerText.trim();
                        let href = el.getAttribute('href') || '';
                        if (text && el.getBoundingClientRect().width > 0) {
                            items.push(`${el.tagName.toLowerCase()}: "${text}" -> href="${href}"`);
                        }
                    });
                    return items.slice(0, 100).join('\\n');
                }""")
                return f"Page interactive elements:\n{links}"
        except Exception as e:
            return f"Extraction failed: {e}"

    # ── Navigation ───────────────────────────────────────────────────

    @aria_tool(name="browser_navigate", description="Navigates the browser to a URL and returns the page title.")
    async def navigate(self, url: str) -> str:
        await self._ensure_started()
        try:
            if not url.startswith("http"):
                url = "https://" + url
            await self.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await self.page.title()
            return f"Navigated to {url}. Title: {title}"
        except Exception as e:
            return f"Navigation failed: {str(e)}"

    # ── Content Extraction ───────────────────────────────────────────

    @aria_tool(name="browser_extract_text", description="Extracts all visible text from the current page.")
    async def extract_text(self) -> str:
        await self._ensure_started()
        try:
            text = await self.page.evaluate("document.body.innerText")
            if len(text) > 4000:
                text = text[:4000] + "\n...[truncated]..."
            return text
        except Exception as e:
            return f"Text extraction failed: {str(e)}"

    # ── Screenshot ───────────────────────────────────────────────────

    @aria_tool(name="browser_screenshot", description="Captures a screenshot of the current browser page. Returns the file path.")
    async def screenshot(self, filepath: str = "") -> str:
        await self._ensure_started()
        try:
            if not filepath:
                filepath = os.path.expanduser("~/browser_screenshot.png")
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            await self.page.screenshot(path=filepath, full_page=False)
            return f"Browser screenshot saved to: {filepath}"
        except Exception as e:
            return f"Screenshot failed: {str(e)}"

    # ── Click ────────────────────────────────────────────────────────

    @aria_tool(name="browser_click", description="Clicks an element on the page by CSS selector or by visible text content. Example: selector='#submit-btn' or text='Sign In'.")
    async def click(self, selector: str = "", text: str = "") -> str:
        await self._ensure_started()
        try:
            if text:
                for tag in ["button", "a", "input[type=submit]", "span", "div"]:
                    try:
                        loc = self.page.locator(f"{tag}:has-text('{text}')").first
                        if await loc.count() > 0:
                            await loc.click(timeout=5000)
                            return f"Clicked element with text: '{text}'"
                    except Exception:
                        continue
                loc = self.page.get_by_text(text, exact=False).first
                await loc.click(timeout=5000)
                return f"Clicked element with text: '{text}'"
            elif selector:
                await self.page.click(selector, timeout=5000)
                return f"Clicked: {selector}"
            else:
                return "Provide either 'selector' or 'text' to click."
        except Exception as e:
            return f"Click failed: {str(e)}"

    # ── Fill Form ────────────────────────────────────────────────────

    @aria_tool(name="browser_fill", description="Fills a form input field. Use selector (CSS) or label text.")
    async def fill(self, value: str, selector: str = "", label: str = "") -> str:
        await self._ensure_started()
        try:
            if label:
                loc = self.page.get_by_label(label).first
                await loc.fill(value, timeout=5000)
                return f"Filled '{label}' with: {value[:50]}"
            elif selector:
                await self.page.fill(selector, value, timeout=5000)
                return f"Filled {selector} with: {value[:50]}"
            else:
                return "Provide either 'selector' or 'label'."
        except Exception as e:
            return f"Fill failed: {str(e)}"

    # ── JavaScript Execution ─────────────────────────────────────────

    @aria_tool(name="browser_execute_js", description="Executes arbitrary JavaScript code on the current browser page.")
    async def execute_js(self, code: str) -> str:
        await self._ensure_started()
        try:
            result = await self.page.evaluate(code)
            return f"JS Result: {str(result)[:2000]}"
        except Exception as e:
            return f"JS execution failed: {str(e)}"

    # ── Wait For Element ─────────────────────────────────────────────

    @aria_tool(name="browser_wait_for", description="Waits for an element to appear on the page. Use CSS selector or text.")
    async def wait_for(self, selector: str = "", text: str = "", timeout: int = 10000) -> str:
        await self._ensure_started()
        try:
            if text:
                loc = self.page.get_by_text(text, exact=False).first
                await loc.wait_for(state="visible", timeout=timeout)
                return f"Element with text '{text}' appeared."
            elif selector:
                await self.page.wait_for_selector(selector, state="visible", timeout=timeout)
                return f"Element '{selector}' appeared."
            else:
                return "Provide 'selector' or 'text'."
        except Exception as e:
            return f"Wait failed (timeout or not found): {str(e)}"

    # ── Lifecycle ────────────────────────────────────────────────────

    async def shutdown(self):
        try:
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.context = None
        self.page = None
        self.playwright = None


browser_agent = BrowserAgent()
