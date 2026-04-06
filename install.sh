#!/usr/bin/env bash
set -e

echo "=========================================="
echo "    Powermetrics Dashboard Installer"
echo "=========================================="

# 1. Check if we are on macOS
if [ "$(uname)" != "Darwin" ]; then
    echo "❌ Error: This dashboard relies on 'powermetrics', which is only available on macOS."
    exit 1
fi

echo "🍏 macOS environment detected."

# 2. Determine the project path
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 3. Create global 'activity' launch bash script
WRAPPER_SCRIPT="/usr/local/bin/activity"
echo "⚙️  Configuring the 'activity' command handler (requires sudo)..."

cat << EOF | sudo tee "$WRAPPER_SCRIPT" > /dev/null
#!/usr/bin/env bash

# Handle Ctrl+C gracefully without dumping Python trace
trap 'echo ""; echo "🛑 Stopping Powermetrics Dashboard. Goodbye!"; exit 0' INT TERM

REPO_DIR="$REPO_DIR"
VENV_DIR="\$REPO_DIR/.venv"

# Check if environment and dependencies exist
if [ ! -d "\$VENV_DIR" ] || ! "\$VENV_DIR/bin/python3" -c "import websockets" 2>/dev/null; then
    echo "📦 One-time setup: Auto-installing websocket dependencies..."
    python3 -m venv "\$VENV_DIR"
    "\$VENV_DIR/bin/pip" install websockets --quiet
    echo "✅ Dependencies ready."
fi

echo "🚀 Starting Powermetrics Dashboard..."
# Give the server a second to boot, then open the browser
(sleep 1.5 && open "http://localhost:7070" > /dev/null 2>&1) &

# Launch the backend server via sudo. 
# (Ctrl+C here exits server.py and triggers the trap)
sudo "\$VENV_DIR/bin/python3" "\$REPO_DIR/server.py" "\$@"
EOF

# 4. Make it executable
sudo chmod +x "$WRAPPER_SCRIPT"

echo ""
echo "✅ Installation Complete!"
echo "Dependencies are now lazy-loaded on the first run of the app."
echo "You can now start the dashboard from any terminal folder by typing:"
echo ""
echo "    activity"
echo ""
