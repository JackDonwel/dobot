#!/usr/bin/env bash
# TBot cross-platform installer.
#
#   Linux/macOS  →  pip install .  +  symlink to ~/.local/bin/tbot
#   Windows      →  pip install .  (tbot.exe placed in Scripts/ by pip)
#
set -euo pipefail

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

echo "▸ Installing TBot..."

# ── Install the Python package ──────────────────────
if command -v uv &>/dev/null; then
    uv pip install --quiet -e "$APP_DIR"
elif command -v pipx &>/dev/null; then
    pipx install "$APP_DIR"
else
    pip install --quiet -e "$APP_DIR"
fi

echo "  ✓ Package installed"

# ── Symlink for Linux/macOS ─────────────────────────
case "$(uname -s)" in
    Linux|Darwin)
        mkdir -p "$HOME/.local/bin"
        TARGET="$HOME/.local/bin/tbot"
        if [ -f "$TARGET" ] && [ ! -L "$TARGET" ]; then
            echo "  ⚠ $TARGET exists and is not a symlink — skipping"
        else
            ln -sf "$APP_DIR/tbot" "$TARGET"
            echo "  ✓ Symlinked → $TARGET"
        fi

        # Ensure ~/.local/bin is on PATH
        for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
            [ -f "$rc" ] || continue
            if ! grep -q '\.local/bin' "$rc" 2>/dev/null; then
                echo "  Adding ~/.local/bin to PATH in $rc"
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
            fi
        done
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "  ✓ Windows: tbot.exe is in your Python Scripts directory"
        echo "    Add it to PATH if needed:  set PATH=%PATH%;C:\Users\...\Python\Scripts"
        ;;
esac

echo ""
echo "  ─────────────────────────────────────────────"
echo "   TBot v0.2 — Multi-Agent Trading System"
echo "   https://github.com/JackDonwel/TBot"
echo "  ─────────────────────────────────────────────"
echo ""
echo "  Usage:  tbot run        # Full London session"
echo "          tbot once PAIR  # Single pair"
echo "          tbot status     # System status"
echo "          tbot watch      # Continuous mode"
echo "          tbot dashboard  # Web UI @ http://127.0.0.1:8080"
echo ""
echo "  Config: $APP_DIR/.env"
echo "  Data:   $APP_DIR/data/"
