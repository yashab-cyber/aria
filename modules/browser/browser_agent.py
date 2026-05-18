"""
A.R.I.A. Browser Agent — Full headless browser automation.

Navigate, screenshot, click, fill forms, execute JS, and wait for elements.
Powered by Playwright (Chromium).
"""

import os
import base64
import asyncio
from playwright.async_api import async_playwright
from core.tool_registry import aria_tool


class BrowserAgent:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None

    async def _ensure_started(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.page = await self.browser.new_page()
            await self.page.set_viewport_size({"width": 1920, "height": 1080})

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

    @aria_tool(name="browser_screenshot", description="Captures a screenshot of the current browser page. Returns the file path. Optionally saves to a custom path.")
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
                # Click by visible text using multiple strategies
                for tag in ["button", "a", "input[type=submit]", "span", "div"]:
                    try:
                        loc = self.page.locator(f"{tag}:has-text('{text}')").first
                        if await loc.count() > 0:
                            await loc.click(timeout=5000)
                            return f"Clicked element with text: '{text}'"
                    except Exception:
                        continue
                # Fallback: try exact text match
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

    @aria_tool(name="browser_fill", description="Fills a form input field. Use selector (CSS) or label text. Example: selector='#email' value='user@test.com' OR label='Email' value='user@test.com'.")
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

    @aria_tool(name="browser_execute_js", description="Executes arbitrary JavaScript code on the current browser page and returns the result.")
    async def execute_js(self, code: str) -> str:
        await self._ensure_started()
        try:
            result = await self.page.evaluate(code)
            return f"JS Result: {str(result)[:2000]}"
        except Exception as e:
            return f"JS execution failed: {str(e)}"

    # ── Wait For Element ─────────────────────────────────────────────

    @aria_tool(name="browser_wait_for", description="Waits for an element to appear on the page. Use CSS selector or text. timeout in milliseconds (default 10000).")
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
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()


browser_agent = BrowserAgent()
