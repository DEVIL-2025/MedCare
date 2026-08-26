@echo off
REM ==============================================================================
REM MedCare Pharma Control Tower - Production Launch Script (Windows)
REM ==============================================================================

echo ==============================================================================
echo  Starting MedCare Pharma SCM Control Tower in Production Mode (Windows)
echo ==============================================================================

set HOST=0.0.0.0
set PORT=8000
set DEBUG=false

echo --^> Running pre-flight system verification...
python deployment\scripts\deploy_check.py
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Pre-flight deployment check failed!
    exit /b %ERRORLEVEL%
)

echo --^> Launching FastAPI application server on http://%HOST%:%PORT%...
python -m uvicorn backend.app.main:app --host %HOST% --port %PORT%
