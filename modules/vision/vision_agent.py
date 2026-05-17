import os
import base64
import pyautogui
import cv2
import numpy as np
import asyncio
import time
from io import BytesIO
from typing import Optional, List, Tuple
from core.tool_registry import aria_tool
from config import config
from PIL import Image, ImageDraw, ImageFont
import litellm
from litellm import acompletion
import aiohttp


class VisionAgent:
    """
    A.R.I.A's evolved Vision System — provides advanced screen analysis, 
    image understanding, OCR, visual element detection, change monitoring,
    and multi-frame temporal awareness.
    """

    def __init__(self):
        self._last_screenshot: Optional[Image.Image] = None
        self._screenshot_history: List[Tuple[float, str]] = []  # (timestamp, base64)
        self._max_history = 10
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None

    # ──────────────────────────────────────────────────
    #  Core Helpers
    # ──────────────────────────────────────────────────

    def _pil_to_base64(self, img: Image.Image, fmt: str = "PNG", max_dim: int = 1920) -> str:
        """Convert a PIL Image to a base64 string, with optional downscaling."""
        # Downscale if too large to save tokens / speed up API calls
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buffered = BytesIO()
        img.save(buffered, format=fmt)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _numpy_to_base64(self, arr: np.ndarray, fmt: str = "PNG") -> str:
        """Convert a NumPy/OpenCV array to base64."""
        img = Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB))
        return self._pil_to_base64(img, fmt)

    def _capture_screen(self) -> Image.Image:
        """Capture the current screen."""
        screenshot = pyautogui.screenshot()
        self._last_screenshot = screenshot
        return screenshot

    def _store_snapshot(self, b64: str):
        """Store a snapshot in the rolling history buffer."""
        self._screenshot_history.append((time.time(), b64))
        if len(self._screenshot_history) > self._max_history:
            self._screenshot_history.pop(0)

    async def _ask_vision(
        self,
        prompt: str,
        images: List[str],
        max_tokens: int = 500,
        detail: str = "auto",
    ) -> str:
        """Send one or more base64 images to the vision-capable LLM."""
        content = [{"type": "text", "text": prompt}]
        for img_b64 in images:
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{img_b64}",
                    "detail": detail,
                },
            })

        response = await acompletion(
            model=config.aria_model,
            messages=[{"role": "user", "content": content}],
            api_base=config.api_base,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # ──────────────────────────────────────────────────
    #  Tool 1 — Full Screen Analysis (enhanced)
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_screen",
        description="Captures the full screen and uses Vision AI to describe, analyze, or answer questions about what is currently visible.",
    )
    async def analyze_screen(self, prompt: str = "What is on my screen?") -> str:
        try:
            screenshot = self._capture_screen()
            img_b64 = self._pil_to_base64(screenshot)
            self._store_snapshot(img_b64)
            return await self._ask_vision(prompt, [img_b64], max_tokens=600)
        except Exception as e:
            return f"Error analyzing screen: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 2 — Region Capture & Analysis
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_screen_region",
        description="Captures a specific rectangular region of the screen and analyzes it. Coordinates are (x, y, width, height) in pixels.",
    )
    async def analyze_screen_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        prompt: str = "Describe what is in this region.",
    ) -> str:
        try:
            region = pyautogui.screenshot(region=(x, y, width, height))
            img_b64 = self._pil_to_base64(region)
            return await self._ask_vision(prompt, [img_b64], max_tokens=400)
        except Exception as e:
            return f"Error analyzing region: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 3 — Analyze Image from File
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_image_file",
        description="Reads an image from a local file path and uses Vision AI to describe or analyze it.",
    )
    async def analyze_image_file(
        self, file_path: str, prompt: str = "Describe this image in detail."
    ) -> str:
        try:
            if not os.path.exists(file_path):
                return f"File not found: {file_path}"

            img = Image.open(file_path).convert("RGB")
            img_b64 = self._pil_to_base64(img)
            return await self._ask_vision(prompt, [img_b64], max_tokens=600)
        except Exception as e:
            return f"Error analyzing image file: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 4 — Analyze Image from URL
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_image_url",
        description="Downloads an image from a URL and uses Vision AI to describe or analyze it.",
    )
    async def analyze_image_url(
        self, url: str, prompt: str = "Describe this image in detail."
    ) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return f"Failed to download image: HTTP {resp.status}"
                    data = await resp.read()

            img = Image.open(BytesIO(data)).convert("RGB")
            img_b64 = self._pil_to_base64(img)
            return await self._ask_vision(prompt, [img_b64], max_tokens=600)
        except Exception as e:
            return f"Error analyzing image from URL: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 5 — OCR / Text Extraction
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="read_screen_text",
        description="Captures the screen and extracts all readable text from it using Vision AI OCR.",
    )
    async def read_screen_text(self) -> str:
        try:
            screenshot = self._capture_screen()
            img_b64 = self._pil_to_base64(screenshot, max_dim=2560)  # higher res for OCR
            return await self._ask_vision(
                "Extract ALL readable text from this screenshot. Return the raw text exactly as it appears, preserving layout where possible. Do not summarize or interpret — just transcribe.",
                [img_b64],
                max_tokens=2000,
                detail="high",
            )
        except Exception as e:
            return f"Error reading screen text: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 6 — Find Visual Element on Screen
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="find_element_on_screen",
        description="Searches the screen for a described visual element (button, icon, text field, etc.) and returns its approximate pixel coordinates.",
    )
    async def find_element_on_screen(self, element_description: str) -> str:
        try:
            screenshot = self._capture_screen()
            w, h = screenshot.size
            img_b64 = self._pil_to_base64(screenshot)

            result = await self._ask_vision(
                f"""You are a precise UI element locator. Find the element described below on the screenshot.

Element to find: "{element_description}"

The screenshot dimensions are {w}x{h} pixels.

Respond ONLY in this exact JSON format:
{{"found": true, "x": <center_x>, "y": <center_y>, "confidence": <0.0-1.0>, "description": "<brief description of what you found>"}}

If the element is not visible, respond:
{{"found": false, "confidence": 0.0, "description": "Element not found on screen."}}""",
                [img_b64],
                max_tokens=200,
            )
            return result
        except Exception as e:
            return f"Error finding element: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 7 — Compare Screenshots (Change Detection)
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="detect_screen_changes",
        description="Takes a new screenshot and compares it against the previous one to identify what changed on screen.",
    )
    async def detect_screen_changes(self) -> str:
        try:
            if not self._screenshot_history:
                # Take a baseline
                screenshot = self._capture_screen()
                img_b64 = self._pil_to_base64(screenshot)
                self._store_snapshot(img_b64)
                return "Baseline screenshot captured. Run this tool again to detect changes."

            old_b64 = self._screenshot_history[-1][1]

            # Capture new
            screenshot = self._capture_screen()
            new_b64 = self._pil_to_base64(screenshot)
            self._store_snapshot(new_b64)

            # Use OpenCV to compute a visual diff highlight
            old_img = np.array(Image.open(BytesIO(base64.b64decode(old_b64))).convert("RGB"))
            new_img = np.array(Image.open(BytesIO(base64.b64decode(new_b64))).convert("RGB"))

            # Resize if dimensions differ
            if old_img.shape != new_img.shape:
                old_img = cv2.resize(old_img, (new_img.shape[1], new_img.shape[0]))

            diff = cv2.absdiff(old_img, new_img)
            gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
            _, thresh = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
            change_pct = (np.count_nonzero(thresh) / thresh.size) * 100

            if change_pct < 0.5:
                return f"No significant changes detected (pixel diff: {change_pct:.2f}%)."

            # Highlight changed regions on the new screenshot
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            highlighted = cv2.cvtColor(new_img, cv2.COLOR_RGB2BGR)
            for cnt in contours:
                if cv2.contourArea(cnt) > 500:
                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    cv2.rectangle(highlighted, (bx, by), (bx + bw, by + bh), (0, 0, 255), 2)

            highlighted_b64 = self._numpy_to_base64(highlighted)

            result = await self._ask_vision(
                f"The red rectangles highlight regions that changed between two screenshots ({change_pct:.1f}% of pixels changed). Describe what changed.",
                [highlighted_b64],
                max_tokens=500,
            )
            return result
        except Exception as e:
            return f"Error detecting changes: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 8 — Visual Diff Between Two Images
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="compare_images",
        description="Compares two image files side-by-side and describes the differences.",
    )
    async def compare_images(
        self,
        image_path_1: str,
        image_path_2: str,
        prompt: str = "Compare these two images and describe the differences.",
    ) -> str:
        try:
            for p in [image_path_1, image_path_2]:
                if not os.path.exists(p):
                    return f"File not found: {p}"

            img1 = Image.open(image_path_1).convert("RGB")
            img2 = Image.open(image_path_2).convert("RGB")
            b64_1 = self._pil_to_base64(img1)
            b64_2 = self._pil_to_base64(img2)

            return await self._ask_vision(prompt, [b64_1, b64_2], max_tokens=600)
        except Exception as e:
            return f"Error comparing images: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 9 — Color & UI Theme Analysis
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_ui_design",
        description="Captures the screen and provides a detailed UI/UX design analysis including colors, layout, typography, and accessibility feedback.",
    )
    async def analyze_ui_design(self) -> str:
        try:
            screenshot = self._capture_screen()
            img_b64 = self._pil_to_base64(screenshot)

            # Also extract dominant colors via OpenCV
            img_np = np.array(screenshot.convert("RGB"))
            img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            pixels = img_cv.reshape(-1, 3).astype(np.float32)

            # K-Means to find top 5 dominant colors
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            _, labels, centers = cv2.kmeans(pixels, 5, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
            centers = centers.astype(int)

            color_info = []
            for i, c in enumerate(centers):
                hex_color = "#{:02x}{:02x}{:02x}".format(c[2], c[1], c[0])  # BGR -> RGB
                pct = (np.count_nonzero(labels == i) / len(labels)) * 100
                color_info.append(f"  {hex_color} ({pct:.1f}%)")

            colors_str = "\n".join(color_info)

            return await self._ask_vision(
                f"""Analyze this UI screenshot as a professional UX designer. Cover:
1. **Layout** — Structure, spacing, visual hierarchy
2. **Colors** — Harmony, contrast, accessibility (dominant palette detected: \n{colors_str})
3. **Typography** — Font choices, readability, sizing
4. **Interactions** — Visible interactive elements, affordances
5. **Accessibility** — Potential WCAG issues (contrast, text size, etc.)
6. **Overall Score** — Rate 1-10 with specific improvement suggestions.""",
                [img_b64],
                max_tokens=800,
            )
        except Exception as e:
            return f"Error analyzing UI design: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 10 — Continuous Screen Monitoring
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="start_screen_monitor",
        description="Starts continuous screen monitoring that checks for visual changes every N seconds and reports them. Use stop_screen_monitor to stop.",
    )
    async def start_screen_monitor(self, interval_seconds: int = 5) -> str:
        if self._monitoring:
            return "Screen monitor is already running."

        self._monitoring = True

        async def _monitor_loop():
            # Capture initial baseline
            screenshot = self._capture_screen()
            prev_b64 = self._pil_to_base64(screenshot)
            self._store_snapshot(prev_b64)

            while self._monitoring:
                await asyncio.sleep(interval_seconds)
                if not self._monitoring:
                    break

                screenshot = self._capture_screen()
                curr_b64 = self._pil_to_base64(screenshot)

                # Quick pixel-level diff check
                old_np = np.array(Image.open(BytesIO(base64.b64decode(prev_b64))).convert("RGB"))
                new_np = np.array(screenshot.convert("RGB"))
                if old_np.shape != new_np.shape:
                    old_np = cv2.resize(old_np, (new_np.shape[1], new_np.shape[0]))

                diff = cv2.absdiff(old_np, new_np)
                gray = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
                change_pct = (np.count_nonzero(gray > 30) / gray.size) * 100

                if change_pct > 2.0:
                    self._store_snapshot(curr_b64)
                    print(f"[VISION MONITOR] Significant change detected: {change_pct:.1f}% pixels changed")

                prev_b64 = curr_b64

        self._monitor_task = asyncio.create_task(_monitor_loop())
        return f"Screen monitor started. Checking every {interval_seconds}s for visual changes."

    @aria_tool(
        name="stop_screen_monitor",
        description="Stops the continuous screen monitor.",
    )
    async def stop_screen_monitor(self) -> str:
        if not self._monitoring:
            return "Screen monitor is not running."

        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None
        
        snapshot_count = len(self._screenshot_history)
        return f"Screen monitor stopped. {snapshot_count} snapshots captured during session."

    # ──────────────────────────────────────────────────
    #  Tool 11 — Temporal Context (Multi-frame)
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="analyze_screen_history",
        description="Analyzes the last N captured screenshots to understand what happened over time on the screen.",
    )
    async def analyze_screen_history(
        self, prompt: str = "What has been happening on the screen over time?", last_n: int = 3
    ) -> str:
        try:
            if len(self._screenshot_history) < 2:
                return "Not enough screenshot history. Use analyze_screen or start_screen_monitor first to capture snapshots."

            snapshots = self._screenshot_history[-last_n:]
            images = [b64 for _, b64 in snapshots]
            timestamps = [ts for ts, _ in snapshots]

            time_labels = []
            for i, ts in enumerate(timestamps):
                elapsed = timestamps[-1] - ts
                time_labels.append(f"Image {i+1}: {elapsed:.0f}s ago")

            augmented_prompt = f"""{prompt}

These {len(images)} screenshots were captured at different times:
{chr(10).join(time_labels)}

Describe the progression — what changed, what actions were taken, and what the user appears to be doing."""

            return await self._ask_vision(augmented_prompt, images, max_tokens=800)
        except Exception as e:
            return f"Error analyzing screen history: {e}"

    # ──────────────────────────────────────────────────
    #  Tool 12 — Screenshot to Structured Data
    # ──────────────────────────────────────────────────

    @aria_tool(
        name="screen_to_json",
        description="Captures the screen and extracts structured data (tables, forms, lists) into JSON format.",
    )
    async def screen_to_json(
        self, data_description: str = "Extract any structured data visible on screen."
    ) -> str:
        try:
            screenshot = self._capture_screen()
            img_b64 = self._pil_to_base64(screenshot, max_dim=2560)
            self._store_snapshot(img_b64)

            return await self._ask_vision(
                f"""You are a precision data extractor. Look at this screenshot and extract structured data.

Task: {data_description}

Rules:
- Return ONLY valid JSON
- For tables: use an array of objects with column headers as keys
- For forms: use key-value pairs
- For lists: use arrays
- Preserve exact values as they appear on screen
- If multiple data structures are visible, return them under descriptive top-level keys""",
                [img_b64],
                max_tokens=2000,
                detail="high",
            )
        except Exception as e:
            return f"Error extracting structured data: {e}"


# Singleton instance
vision_agent = VisionAgent()
