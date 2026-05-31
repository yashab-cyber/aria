#!/bin/bash

# Define colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${CYAN}====================================================${NC}"
echo -e "${BOLD}${CYAN}          A.R.I.A. Development Launcher             ${NC}"
echo -e "${BOLD}${CYAN}====================================================${NC}"

# Function to run command and prefix output
prefix_output() {
    local prefix="$1"
    local color="$2"
    while IFS= read -r line; do
        echo -e "${color}${prefix}${NC} $line"
    done
}

# Determine script's directory (root of the workspace)
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Determine python executable
if command -v python3 &>/dev/null; then
    PYTHON_EXEC="python3"
elif command -v python &>/dev/null; then
    PYTHON_EXEC="python"
else
    echo -e "${RED}[Launcher] Error: Python is not installed or not in PATH.${NC}"
    exit 1
fi

# 1. Virtual Environment Activation
if [ -d ".venv" ]; then
    echo -e "${GREEN}[Launcher] Found .venv. Activating...${NC}"
    source .venv/bin/activate
elif [ -d "venv" ]; then
    echo -e "${GREEN}[Launcher] Found venv. Activating...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}[Launcher] No virtual environment (.venv/venv) found. Running with system Python.${NC}"
fi

# 2. Check UI node_modules
if [ ! -d "ui/node_modules" ]; then
    echo -e "${YELLOW}[Launcher] ui/node_modules not found. Installing UI dependencies...${NC}"
    (cd ui && npm install)
fi

# 3. Start Backend Server
echo -e "${BLUE}[Launcher] Starting Backend Server...${NC}"
$PYTHON_EXEC -u main.py 2>&1 | prefix_output "[Backend]" "${BLUE}" &
BACKEND_PID=$!

# 4. Start UI Frontend
echo -e "${GREEN}[Launcher] Starting Frontend UI...${NC}"
FORCE_COLOR=1 npm --prefix ui run dev 2>&1 | prefix_output "[Frontend]" "${GREEN}" &
FRONTEND_PID=$!

# Print access info
echo -e "${BOLD}${YELLOW}====================================================${NC}"
echo -e "${BOLD}${YELLOW}  A.R.I.A. is starting!${NC}"
echo -e "${BOLD}${YELLOW}  - Frontend URL: https://localhost:5173${NC}"
echo -e "${BOLD}${YELLOW}  - Backend URL:  http://localhost:8000${NC}"
echo -e "${BOLD}${YELLOW}  Press Ctrl+C to stop both processes gracefully.${NC}"
echo -e "${BOLD}${YELLOW}====================================================${NC}"

# Cleanup function to kill background processes on exit
cleanup() {
    echo -e "\n${BOLD}${RED}[Launcher] Stopping services...${NC}"
    # Send SIGINT to backend and frontend
    kill -INT "$BACKEND_PID" 2>/dev/null
    kill -INT "$FRONTEND_PID" 2>/dev/null
    
    # Wait for processes to exit
    wait "$BACKEND_PID" 2>/dev/null
    wait "$FRONTEND_PID" 2>/dev/null
    
    echo -e "${BOLD}${GREEN}[Launcher] Clean shutdown successful.${NC}"
    exit 0
}

# Trap signals for graceful exit
trap cleanup SIGINT SIGTERM

# Keep the script running and wait for background jobs
wait
