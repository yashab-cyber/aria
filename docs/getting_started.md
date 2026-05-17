# Getting Started with A.R.I.A.

## Prerequisites
- Python 3.10+
- Node.js & npm (for UI)
- Valid LLM API Keys (configured in `.env`)

## Installation

### 1. Backend Setup
Clone the repository and install the Python dependencies:

```bash
git clone <repo-url>
cd aria
pip install -r requirements.txt
```

Set up your environment variables:
```bash
cp .env.example .env
# Edit .env and insert your API keys
```

### 2. Frontend Setup
Navigate to the `ui` directory and install the required npm packages:

```bash
cd ui
npm install
```

## Running A.R.I.A.

1. **Start the backend server (FastAPI):**
```bash
# In the root directory
python3 server.py
# or
python3 main.py
```

2. **Start the UI development server:**
In a separate terminal instance:
```bash
cd ui
npm run dev
```

3. **Access the Interface:**
Open your browser to `http://localhost:5173` (or the port specified by Vite) to access the JARVIS-inspired UI and interact with A.R.I.A.
