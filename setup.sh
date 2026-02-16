#!/bin/bash
# Familiar setup script

FAMILIAR_DIR="${HOME}/Obsidian/System/Familiar"

echo "Setting up Familiar..."
echo

# Create directory structure
for dir in Jobs Processing Done Failed; do
    mkdir -p "${FAMILIAR_DIR}/${dir}"
    echo "  Created ${FAMILIAR_DIR}/${dir}"
done
echo

# Check dependencies
OK=true

if command -v claude &>/dev/null; then
    echo "✓ claude CLI found"
else
    echo "✗ claude CLI not found"
    echo "  Install: npm install -g @anthropic-ai/claude-code"
    OK=false
fi

if command -v fswatch &>/dev/null; then
    echo "✓ fswatch found"
else
    echo "⚠ fswatch not found (will use polling fallback)"
    echo "  Optional: brew install fswatch"
fi

echo
if [ "$OK" = true ]; then
    echo "Ready! Run with:"
    echo "  python3 $(cd "$(dirname "$0")" && pwd)/dispatcher.py"
else
    echo "Install missing dependencies above, then run:"
    echo "  python3 $(cd "$(dirname "$0")" && pwd)/dispatcher.py"
fi
