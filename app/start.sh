#!/bin/bash
set -e

echo "=== Starting Flask Application ==="
echo "Current directory: $(pwd)"
echo "Python version: $(python --version)"
echo "PORT: ${PORT:-8080}"
echo "APP_ENV: ${APP_ENV:-development}"
echo ""
echo "=== Checking Python imports ==="
python -c "import flask; print('Flask import: OK')"
python -c "import os, sys; print('Standard libs: OK')"
echo ""
echo "=== Starting Flask app ==="
exec python -u app.py
