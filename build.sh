#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing system dependencies for Playwright..."
python -m playwright install-deps chromium

echo "Installing Chromium browser..."
python -m playwright install chromium

echo "Build complete!"
