#!/usr/bin/env bash
echo "======================================================="
echo "       🚀 Find the Job AI — Launcher"
echo "======================================================="
echo ""

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# 1. Setup & Start Python Backend
cd "$DIR/PythonScripts"
if [ ! -d ".venv" ]; then
    echo "[1/3] Creating Python virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "[1/3] Installing Python dependencies..."
    pip install -r requirements.txt
else
    source .venv/bin/activate
fi

echo "[2/3] Starting Python AI Backend (port 8000)..."
python3 -m uvicorn main:app --port 8000 &
BACKEND_PID=$!

sleep 2

# 2. Start Blazor Frontend
cd "$DIR"
echo "[3/3] Starting Blazor Frontend..."
echo ""
echo "======================================================="
echo "  Application running at: http://localhost:5104"
echo "  Press Ctrl+C to stop both frontend and backend."
echo "======================================================="
echo ""

trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM EXIT

# Open default browser
if command -v xdg-open > /dev/null; then
    xdg-open http://localhost:5104 &
elif command -v open > /dev/null; then
    open http://localhost:5104 &
fi

dotnet run
