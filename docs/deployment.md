# Deployment & Local Setup Guide

## 1. Prerequisites
* Python 3.12+ (tested with Python 3.13.13)
* Node.js v18+ (tested with v24.11.0) & npm

---

## 2. Backend Setup & Startup

1. **Install Python Dependencies**:
   ```powershell
   cd e:\medcare-pharma-control-tower-main
   pip install -r backend/requirements.txt
   ```

2. **Initialize Database & Realistic Seeder Data**:
   ```powershell
   python -m backend.app.utils.data_seeder
   ```

3. **Start FastAPI Backend Server**:
   ```powershell
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   * REST API Docs: `http://localhost:8000/docs`
   * Health Check: `http://localhost:8000/health`

---

## 3. Frontend Setup & Startup

1. **Install Frontend Dependencies**:
   ```powershell
   cd e:\medcare-pharma-control-tower-main\medcare-frontend
   npm install
   ```

2. **Start Vite Development Server**:
   ```powershell
   npm run dev
   ```
   * Control Tower Dashboard: `http://localhost:5173`

3. **Build for Production**:
   ```powershell
   npm run build
   ```
