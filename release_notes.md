# A.R.I.A v1.1.0: God-Level Vision, Control & Premium UI Upgrade

This major release transforms A.R.I.A. from a text-based AI assistant into a fully autonomous agent with "God-Level" vision and system control, paired with a brand new ChatGPT-tier UI. A massive addition of ~21 new tools across multiple modules drastically expands what ARIA is capable of achieving on your local machine.

## 🌟 Major Highlights

### 👁️ God-Level Vision & Control
- **Smart Vision Targeting:** Added `smart_click` and `smart_type` tools. Tell ARIA to "Click the submit button" and she will visually analyze your screen, compute the pixel coordinates of the button using Vision AI, and click it autonomously.
- **Document Reading:** ARIA can now natively read PDFs, DOCX, and PPTX files. It renders the pages to images and uses the Vision LLM for precise extraction.
- **Annotated Screenshots:** A new tool that takes a screenshot and overlays numbered boxes on interactive UI elements for precise reasoning.

### 💻 Deep Desktop Automation
- **Window Management:** Full capability to manage active windows (minimize, maximize, focus, resize) using `wmctrl` and `xdotool`.
- **Mouse & Clipboard:** Unrestricted mouse movement, scrolling, dragging, and reading/writing to the system clipboard.
- **Application Launching:** ARIA can now silently launch background applications and processes.

### 🌐 Headless Browser Agent
- **Playwright Engine:** ARIA can now autonomously spin up headless Chromium instances to navigate the web, execute JavaScript, click elements, wait for selectors, and fill out forms seamlessly in the background.

### ⏰ Scheduler & Multi-Channel Notifications
- **Persistent Task Engine:** A robust SQLite-backed APScheduler allows you to ask ARIA to "run a system scan every morning at 9am".
- **Multi-Channel Delivery:** ARIA can push the results of her autonomous background tasks directly to you via Slack, Telegram, WhatsApp, Email, or Discord.

### 🎨 Premium UI Upgrade
- **Wide ChatGPT-Style Layout:** The UI has been heavily modernized with a clean, centered wide layout, glassmorphic sidebars, and frameless message bubbles.
- **Real-Time Tool Visualizations:** When ARIA uses a tool (e.g., executing a bash script), you now see a real-time, expandable "Executing..." dropdown block directly in the chat stream.
- **Episodic Memory Browser:** A new modal lets you search through ARIA's ChromaDB episodic memory. You can view session summaries and selectively delete past conversations.
- **Smooth Streaming:** Text generation now streams smoothly with a blinking cursor effect rather than flickering Markdown.
- **Enhanced Voice UI:** The microphone button now features a premium, animated red ripple effect while actively recording.

## 🛠️ Fixes & Maintenance
- Added a professional `README.md`, `LICENSE` (MIT), and `CONTRIBUTING.md`.
- Properly configured `.gitignore` to prevent runtime `.db` files from being committed.
- Stabilized `browser_agent` initialization in the tool registry.

## 📦 Dependencies Added
- `apscheduler>=3.10.0`
- `aiosmtplib>=3.0.0`
- `pymupdf>=1.24.0`
