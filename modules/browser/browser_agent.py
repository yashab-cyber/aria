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

    @aria_tool(name="browser_navigate", description="Navigates the browser to a URL.")
    async def navigate(self, url: str) -> str:
        await self._ensure_started()
        try:
            if not url.startswith("http"):
                url = "https://" + url
            await self.page.goto(url)
            title = await self.page.title()
            return f"Navigated to {url}. Title: {title}"
        except Exception as e:
            return f"Failed to navigate: {str(e)}"

    @aria_tool(name="browser_extract_text", description="Extracts all visible text from the current page.")
    async def extract_text(self) -> str:
        await self._ensure_started()
        try:
            text = await self.page.evaluate("document.body.innerText")
            return text[:4000] # truncate to avoid huge context
        except Exception as e:
            return f"Failed to extract text: {str(e)}"

    async def shutdown(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

browser_agent = BrowserAgent()
