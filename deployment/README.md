# 🚀 MedCare Pharma SCM Control Tower - Deployment Center

Welcome to the **MedCare Pharma Supply Chain Control Tower** deployment repository. This folder contains all the configuration files, container definitions, platform manifests, build scripts, and step-by-step guides required to deploy MedCare Pharma to production or **100% Free Cloud Hosting**.

---

## 📂 Deployment Folder Layout

```text
deployment/
├── README.md                      # This file - Overview & Quick Start
├── FREE_HOSTING_STEP_BY_STEP.md   # Step-by-step guide for Vercel + Render + Neon (100% Free)
├── .env.free-tier.example         # Ready-to-copy free tier environment variables
├── .env.production.example        # Enterprise production environment template
│
├── docker/
│   ├── Dockerfile.backend         # Production FastAPI Python 3.12 Backend
│   ├── Dockerfile.frontend        # Multi-stage React Vite + Nginx Web Server
│   ├── Dockerfile.fullstack       # Single-container FastAPI + built React SPA image
│   ├── docker-compose.yml         # Standard 3-service stack (Postgres + API + UI)
│   ├── docker-compose.prod.yml    # Hardened production stack with resource limits & log rotation
│   ├── nginx.conf                 # Production Nginx reverse proxy & SPA router
│   └── .dockerignore              # Clean build context ignore rules
│
├── cloud-platforms/
│   ├── render/
│   │   ├── render.yaml            # Render 1-Click Infrastructure Blueprint
│   │   └── Procfile               # Web process runner for Render / Koyeb / Fly.io
│   ├── vercel/
│   │   └── vercel.json            # Vercel SPA client rewrite & caching configuration
│   ├── netlify/
│   │   ├── netlify.toml           # Netlify build and redirect configuration
│   │   └── _redirects             # Netlify SPA fallback rule
│   └── railway/
│       └── railway.toml           # Railway app deployment specification
│
└── scripts/
    ├── deploy_check.py            # Pre-flight deployment healthcheck & dependency audit
    ├── build_fullstack.py         # 1-click builder packaging React into FastAPI for single-process mode
    ├── start_production.sh        # Linux / macOS production startup script
    └── start_production.bat       # Windows production startup script
```

---

## ⚡ Quick Start: Choose Your Deployment Route

### 🌟 1. Best 100% Free Cloud Hosting (Recommended)
> **Stack**: Vercel (Frontend) + Render (Backend API) + Neon (Serverless PostgreSQL)  
> **Cost**: **$0.00 / month forever**  
> **Read the Full Step-by-Step Tutorial**: 👉 [FREE_HOSTING_STEP_BY_STEP.md](FREE_HOSTING_STEP_BY_STEP.md)

1. **Database**: Create a free project at [Neon.tech](https://neon.tech/) (0.5 GB PostgreSQL, instant SSL).
2. **Backend**: Deploy on [Render.com](https://render.com/) as a **Web Service** (Python runtime, `pip install -r requirements.txt`, start command `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`). Add environment variable `DATABASE_URL` from Neon.
3. **Frontend**: Deploy on [Vercel.com](https://vercel.com/) pointing to the `medcare-frontend` root directory. Add environment variable `VITE_API_BASE_URL=https://your-backend.onrender.com/api`.

---

### 📦 2. Single-Container Full-Stack Mode (Easiest 1-Service Free Setup)
Deploy the whole application (API + React SPA) from a single free container on Render, Koyeb, or Fly.io:

```bash
# 1. Build the React frontend into static assets
python deployment/scripts/build_fullstack.py

# 2. Run the unified FastAPI server (serves both API at /api and React SPA at /)
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

### 🐳 3. Docker Compose (Self-Hosted / VPS / Local Staging)

Run the full 3-tier stack locally or on any cloud VPS (Ubuntu, Debian, AWS EC2, DigitalOcean):

```bash
# Start all containers in background
docker compose -f deployment/docker/docker-compose.yml up -d --build

# View container logs
docker compose -f deployment/docker/docker-compose.yml logs -f

# Check health status
docker compose -f deployment/docker/docker-compose.yml ps
```

* **Frontend UI**: `http://localhost` (Port 80)
* **Backend API Docs**: `http://localhost:8000/docs`
* **PostgreSQL Database**: `localhost:5432`

---

## 🧪 Pre-Flight Deployment Audit

Before deploying to any cloud host, verify your environment with our automated check tool:

```bash
python deployment/scripts/deploy_check.py
```

This verifies:
1. Python version compatibility (>= 3.10)
2. All Python packages & ML dependencies installed
3. Database connectivity and schema initialization
4. ML model artifact loading & vectorized prediction capability
5. FastAPI app and route registrations
6. Frontend build directory status

---

## 🔐 Production Credentials & Initial Login

When the database is first initialized, the default administrator credentials seeded are:
* **Username / Email**: `admin@medcare.com`
* **Password**: `Admin@12345` (or the value set in `ADMIN_INITIAL_PASSWORD`)
* **Role**: `System Administrator` (Full SCM permissions)
