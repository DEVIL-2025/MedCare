#!/usr/bin/env bash
# ==============================================================================
# MedCare Pharma Control Tower - Production Launch Script (Linux / macOS)
# ==============================================================================
set -e

echo "=============================================================================="
echo " Starting MedCare Pharma SCM Control Tower in Production Mode"
echo "=============================================================================="

# 1. Export Environment Defaults
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export DEBUG="${DEBUG:-false}"

# 2. Run Pre-flight Health Check
echo "--> Running pre-flight system verification..."
python3 deployment/scripts/deploy_check.py

# 3. Start Uvicorn Server with multi-workers (if Gunicorn is installed) or standard Uvicorn
echo "--> Launching FastAPI application server on http://${HOST}:${PORT}..."
exec uvicorn backend.app.main:app --host "${HOST}" --port "${PORT}" --workers "${WORKERS:-2}"
