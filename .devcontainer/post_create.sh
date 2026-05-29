#!/bin/bash

# Development container setup script
set -e

# Resolve repo root from this script's location (works regardless of folder name)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Setting up development environment in $REPO_ROOT..."

# Ensure uv is in PATH
export PATH="$HOME/.cargo/bin:$PATH"

# Install project dependencies
echo "📦 Installing Python dependencies..."
cd "$REPO_ROOT"

# Check if uv is available, if not install it
if ! command -v uv &> /dev/null; then
    echo "🐍 Installing uv (Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

export UV_LINK_MODE=copy
# Sync dependencies
uv sync

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p .vscode

# Set proper permissions
echo "🔒 Setting permissions..."
chmod +x "$SCRIPT_DIR/post_create.sh"
for f in bin/env bin/help bin/test bin/lint/all bin/lint/py bin/lint/md; do
    [ -f "$REPO_ROOT/$f" ] && chmod +x "$REPO_ROOT/$f"
done

# Create a sample .env file if it doesn't exist
if [ ! -f ".env" ] && [ -f ".env.template" ]; then
    echo "🔐 Creating .env file from template..."
    cp .env.template .env
fi

echo "✅ Developer environment setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Configure your .env file with actual credentials"
echo "2. Run 'uv run python -m src.main --help' to see available commands"
echo "3. Start coding! 🚀"
echo ""

echo "📝 Available commands:"
echo "  - bin/help                    # Shows help options"
echo "  - bin/env                     # Exports variables from an environment file"
echo "  - bin/lint/all                # Run all linting"
echo "  - bin/lint/md                 # Lint all Markdown files"
echo "  - bin/lint/py                 # Format, line and type check all Python files"
echo "  - bin/test                    # Run all unit tests"
echo "  - uv sync                     # Install/update dependencies"
echo "  - uv run ruff check           # Lint code"
echo "  - uv run ruff format          # Format code"
echo "  - uv run mypy src tests       # Type checking"
echo "  - uv run uvicorn src.api.main:app --reload"
