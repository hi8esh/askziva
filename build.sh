#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Chromium browser..."
python -m playwright install chromium 2>&1 || echo "⚠️ Playwright install failed, continuing anyway..."

echo "Build complete!"
