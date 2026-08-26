#!/usr/bin/env python3
"""
==============================================================================
MedCare Pharma SCM Control Tower - Full-Stack Production Build Tool
==============================================================================
Builds the React frontend and prepares the workspace for zero-config
single-container or single-service deployment.
"""

import os
import sys
import subprocess
import shutil

# Reconfigure stdout for utf-8 on Windows consoles if supported
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "medcare-frontend")
DIST_DIR = os.path.join(FRONTEND_DIR, "dist")


def run_command(cmd, cwd):
    print(f"--> Running: {cmd} (in {cwd})")
    is_windows = sys.platform.startswith("win")
    res = subprocess.run(cmd, cwd=cwd, shell=is_windows)
    if res.returncode != 0:
        print(f"[FAIL] Error: Command '{cmd}' failed with return code {res.returncode}")
        sys.exit(res.returncode)


def main():
    print("=" * 70)
    print("  Building MedCare Full-Stack Application for Production")
    print("=" * 70)

    if not os.path.exists(FRONTEND_DIR):
        print(f"[FAIL] Frontend directory not found at: {FRONTEND_DIR}")
        sys.exit(1)

    print("\n[Step 1/2] Installing frontend dependencies & building React SPA...")
    run_command("npm run build", cwd=FRONTEND_DIR)

    if os.path.exists(os.path.join(DIST_DIR, "index.html")):
        print(f"\n[Step 2/2] Frontend built successfully in: {DIST_DIR}")
        index_size = os.path.getsize(os.path.join(DIST_DIR, "index.html"))
        print(f"  [OK] index.html generated ({index_size} bytes)")
        
        assets_dir = os.path.join(DIST_DIR, "assets")
        if os.path.exists(assets_dir):
            asset_files = os.listdir(assets_dir)
            print(f"  [OK] {len(asset_files)} asset files generated in dist/assets")

        print("\n" + "=" * 70)
        print("  FULL-STACK BUILD COMPLETE!")
        print("=" * 70)
        print("\nTo start the unified server (FastAPI + React SPA in a single process):")
        print("  python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000")
        print("\nOpen http://localhost:8000 in your browser to view the application.")
    else:
        print(f"[FAIL] Failed to find dist/index.html after build.")
        sys.exit(1)


if __name__ == "__main__":
    main()
