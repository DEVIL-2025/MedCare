# ?? MedCare Pharma SCM Control Tower

> **Unified Supply Chain Management Control Tower for MedCare Pharma**
> A full-stack, real-time pharmaceutical supply chain intelligence platform built with FastAPI, React, PostgreSQL, and a suite of domain-specific business engines.

---

## ?? Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Core Engines & Modules](#core-engines--modules)
- [Frontend Pages](#frontend-pages)
- [API Routers](#api-routers)
- [ML Pipeline](#ml-pipeline)
- [Getting Started](#getting-started)
- [Environment Variables Reference](#environment-variables-reference)
- [Automated Testing](#automated-testing)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)
- [Project Status](#project-status)

---

## ?? Project Overview

MedCare Pharma SCM Control Tower is an end-to-end supply chain management platform designed for pharmaceutical distribution networks. It provides real-time inventory tracking, AI-driven demand forecasting, automated replenishment planning, FEFO (First Expired First Out) batch management, network balancing across distribution centres, SLA-based alert escalation, and a natural language AI assistant powered by Google Gemini.

**Key Capabilities:**
- **Real-time inventory monitoring** across multiple distribution centres (DCs)
- **ML-driven demand sensing** with seasonal surge detection
- **FEFO batch tracking** with expiry risk classification
- **Automated replenishment** with explainable ROQ (Recommended Order Quantity) recommendations
- **Inter-DC stock transfers** with transfer-first network balancing policy
- **SLA escalation engine** with multi-channel alert dispatch (Email / WebSocket)
- **What-If scenario simulation** for parametric stress testing
- **Grounded AI Copilot** for natural language supply chain queries (Google Gemini)
- **Role-Based Access Control (RBAC)** with JWT authentication
- **WebSocket real-time push notifications**

---

## ??? Architecture

```
medcare-pharma-control-tower/
+-- backend/                    # FastAPI async Python backend
¦   +-- app/
¦   ¦   +-- config.py           # Pydantic settings
¦   ¦   +-- database.py         # Async SQLAlchemy engine + session
¦   ¦   +-- main.py             # FastAPI app entrypoint & router registration
¦   ¦   +-- dependencies/       # JWT auth dependency injection
¦   ¦   +-- engines/            # Domain-specific business logic engines
¦   ¦   +-- ml/                 # Machine learning pipeline
¦   ¦   +-- models/             # SQLAlchemy ORM models
¦   ¦   +-- routers/            # FastAPI route handlers
¦   ¦   +-- schemas/            # Pydantic request/response schemas
¦   ¦   +-- services/           # External service integrations
¦   ¦   +-- tests/              # pytest test suite
¦   ¦   +-- utils/              # Data seeder & utilities
¦   +-- database/               # SQL schema, seed scripts, migration utilities
+-- medcare-frontend/           # Vite + React frontend
¦   +-- src/
¦       +-- api/                # Axios API client & WebSocket client
¦       +-- components/         # Reusable UI components
¦       +-- context/            # React context (Auth, ControlTower)
¦       +-- pages/              # Application page views
¦       +-- utils/              # Frontend utilities
+-- deployment/                 # Docker & cloud platform configs
¦   +-- docker/                 # Dockerfiles (backend, frontend, fullstack)
¦   +-- cloud-platforms/        # Render, Railway, Vercel, Netlify configs
+-- docs/                       # Architecture, API, and engine documentation
```

---

## ??? Tech Stack

### Backend
| Technology | Version | Purpose |
|---|---|---|
| **Python** | 3.11+ | Runtime |
| **FastAPI** | =0.110.0 | Async REST API framework |
| **Uvicorn** | =0.28.0 | ASGI server |
| **SQLAlchemy** | =2.0.28 | Async ORM |
| **PostgreSQL** | 15+ | Primary database |
| **asyncpg** | =0.29.0 | Async PostgreSQL driver |
| **aiosqlite** | =0.20.0 | SQLite async driver (dev/test) |
| **Pydantic v2** | =2.6.0 | Request/response validation |
| **scikit-learn** | =1.4.0 | ML model (RandomForestRegressor) |
| **pandas / numpy** | =2.2 / =1.26 | Feature engineering & data prep |
| **statsmodels** | =0.14.0 | Statistical modelling |
| **joblib** | =1.3.0 | Model serialization |
| **PyJWT** | =2.8.0 | JWT authentication |
| **bcrypt** | =4.0.0 | Password hashing |
| **google-genai** | =1.0.0 | Google Gemini AI integration |
| **websockets** | =12.0 | WebSocket support |
| **pytest / pytest-asyncio** | =8.0 / =0.23 | Test framework |

### Frontend
| Technology | Version | Purpose |
|---|---|---|
| **React** | ^19.2.8 | UI library |
| **Vite** | ^8.2.0 | Build tool & dev server |
| **React Router DOM** | ^7.18.2 | Client-side routing |
| **Recharts** | ^3.10.1 | Data visualisation charts |
| **Tailwind CSS** | ^3.4.19 | Utility-first CSS framework |
| **lucide-react** | ^1.33.0 | Icon library |

---

## ?? Project Structure

### Backend — Business Engines (`backend/app/engines/`)

| Engine File | Responsibility |
|---|---|
| `inventory_engine.py` | Stock level evaluation, threshold calculations, status transitions |
| `demand_sensing_engine.py` | Multi-factor demand signal processing & surge detection |
| `expiry_fefo_engine.py` | FEFO chronological batch allocation & expiry risk classification |
| `network_balancing_engine.py` | Surplus matching, inter-DC transfer opportunity identification |
| `replenishment_engine.py` | ROQ computation, review frequencies, purchase order constraints |
| `alert_escalation_engine.py` | SLA countdown timers (Critical 4h / High 24h / Medium 72h) |
| `scenario_simulation_engine.py` | Parametric stress-testing & 16-week outcome modelling |
| `risk_engine.py` | Composite risk scoring across inventory, expiry, and demand signals |

### Backend — Services (`backend/app/services/`)

| Service File | Responsibility |
|---|---|
| `auth_service.py` | JWT token creation, validation, password hashing |
| `audit_service.py` | Audit log recording for compliance |
| `gemini_service.py` | Google Gemini AI API integration for the AI Copilot |
| `email_service.py` | Transactional email dispatch |
| `email_alert_service.py` | Periodic email alert scheduler for SLA escalations |
| `notification_service.py` | In-app notification management |

### Backend — ORM Models (`backend/app/models/`)

`alert`, `auth`, `batch`, `demand`, `escalation`, `forecast`, `inventory`, `notification`, `product`, `replenishment`, `risk`, `sales`, `scenario`, `settings`, `signal`, `supplier`, `transaction`, `transfer`, `warehouse`

### Backend — Database (`backend/database/`)

| File | Purpose |
|---|---|
| `schema.sql` | PostgreSQL DDL — full table schema with constraints and indexes |
| `seed.sql` | Initial seed data |
| `connect_and_migrate.py` | Database migration & connection utility |
| `seed_fefo_test_data.py` | FEFO-specific test data seeder |
| `verify_live_postgres.py` | Live PostgreSQL connectivity verification |
| `verify_audit_suite.py` | Audit trail verification suite |

### Frontend — Pages (`medcare-frontend/src/pages/`)

| Page | Description |
|---|---|
| `Login.jsx` | Authentication page with JWT login |
| `Dashboard.jsx` | Executive Control Tower — KPI stat cards, trajectory charts, facility health grid |
| `Inventory.jsx` | Real-time inventory & FEFO ledger — SKU breakdown, batch aging, audit trail |
| `DemandForecast.jsx` | Demand sensing & ML forecast visualisation |
| `Replenishment.jsx` | Replenishment planner & ROQ recommendations |
| `Alerts.jsx` | Alert & SLA escalation console |
| `ScenarioSimulator.jsx` | What-If parametric stress-testing simulator |
| `Reports.jsx` | Financial valuation & CSV export reports |
| `Warehouses.jsx` | Distribution centre management & capacity tracking |
| `UserManagement.jsx` | RBAC user administration |
| `Settings.jsx` | Application settings & configuration |

### Frontend — Components (`medcare-frontend/src/components/`)

Organised into sub-folders: `assistant/`, `auth/`, `inventory/`, `layout/`, `transactions/`, `ui/`, `warehouses/`

---

## ?? Core Engines & Modules

### ?? Inventory Engine
Evaluates real-time stock levels against safety stock thresholds. Performs status transitions (Healthy ? Low ? Critical) and calculates days-of-stock-remaining.

### ?? Demand Sensing Engine
Multi-factor demand signal aggregation with:
- Seasonal event factor multiplication (flu season: +60% uplift)
- Surge detection threshold at +25% above baseline
- ML model transparency with feature importance reporting

### ?? FEFO Expiry Engine
First Expired First Out batch allocation engine with:
- Chronological batch allocation order enforcement
- Expiry risk classification: **Critical** (=30 days), **At Risk** (=90 days), **Watch** (=180 days)
- Expired batch filtering and aging risk calculations

### ?? Network Balancing Engine
Inter-DC stock balancing with transfer-first policy:
- Surplus identification & demand matching across DCs
- Transfer opportunity scoring with estimated savings calculation
- Atomic dual-DC stock synchronisation on transfer approval

### ?? Replenishment Engine
Explainable Recommended Order Quantity (ROQ) calculations:
- Economic Order Quantity (EOQ) model
- Safety stock based on service level (95%) and lead time buffer
- 4-part justification: demand, lead time, safety stock, batch rounding
- Financial approval tiers: Auto (=?1L), Manager (=?5L), Director (>?5L)

### ?? Alert & SLA Escalation Engine
SLA countdown-based escalation pipeline:
- **Critical**: 4-hour response SLA
- **High**: 24-hour response SLA
- **Medium**: 72-hour response SLA
- Multi-channel dispatch: Email (Resend / SMTP) + WebSocket push

### ?? Scenario Simulation Engine
Parametric what-if stress testing with:
- Adjustable demand multiplier, lead time, and stockout probability inputs
- 16-week projected stockout trajectory
- Side-by-side baseline vs. scenario metric comparison

### ?? AI Copilot (Google Gemini)
Database-grounded natural language query engine powered by Google Gemini:
- Answers supply chain questions in plain English
- Queries live database context to ground responses
- Integrated as the `assistant` router and `gemini_service.py`

---

## ?? API Routers

All routes are registered under `/api/` prefix unless noted.

| Router Module | Prefix | Description |
|---|---|---|
| `auth.py` | `/api/auth` | Login, token refresh, logout |
| `users.py` | `/api/users` | User CRUD & role management |
| `dashboard.py` | `/api/dashboard` | Aggregated KPI & dashboard data |
| `inventory.py` | `/api/inventory` | Inventory CRUD, batch management |
| `transactions.py` | `/api/transactions` | Inventory transaction ledger |
| `demand.py` | `/api/demand` | Demand signals & history |
| `forecasts.py` | `/api/forecasts` | ML forecast generation & training |
| `replenishment.py` | `/api/replenishment` | ROQ recommendations & purchase orders |
| `transfers.py` | `/api/transfers` | Inter-DC stock transfer management |
| `alerts.py` | `/api/alerts` | Alert lifecycle & escalation |
| `warehouses.py` | `/api/warehouses` | DC management & capacity |
| `scenarios.py` | `/api/scenarios` | What-if simulation runs |
| `reports.py` | `/api/reports` | CSV report generation |
| `settings.py` | `/api/settings` | Application settings |
| `notifications.py` | `/api/notifications` | In-app notification feed |
| `metrics.py` | `/api/metrics` | Operational metrics |
| `assistant.py` | `/api/assistant` | Gemini AI Copilot queries |
| `suppliers.py` | `/api/suppliers` | Supplier management |
| `ws.py` | `/ws` | WebSocket real-time push channel |

**Interactive API Docs**: `http://localhost:8000/docs` (Swagger UI) / `http://localhost:8000/redoc`

---

## ?? ML Pipeline

Located in `backend/app/ml/`:

| File | Purpose |
|---|---|
| `data_preparation.py` | Dataset extraction from the database |
| `feature_engineering.py` | Feature construction (lag features, seasonal indicators, rolling stats) |
| `train.py` | RandomForestRegressor model training |
| `evaluate.py` | Model performance evaluation (RMSE, MAE, R²) |
| `predict.py` | Inference pipeline with confidence interval generation |
| `model_registry.py` | Model artifact registry and versioning |
| `saved_models/` | Persisted `.pkl` model artifacts |

**Confidence Level**: 87% (`ML_CONFIDENCE_LEVEL=0.87`)

**Train via API**:
```bash
POST /api/forecasts/train
```

---

## ?? Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** & **npm**
- **PostgreSQL 15+** (local or Neon cloud)

### 1. Clone & Configure Environment

```bash
git clone <repository-url>
cd medcare-pharma-control-tower-main

# Copy and configure the environment file
cp .env.example .env
# Edit .env with your PostgreSQL credentials
```

### 2. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI backend (from project root)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will:
1. Connect to PostgreSQL and create all tables via SQLAlchemy
2. Seed initial data automatically via `data_seeder.py`
3. Start the periodic email alert scheduler

**Backend API**: `http://localhost:8000`
**Swagger Docs**: `http://localhost:8000/docs`
**Health Check**: `http://localhost:8000/api/health`

### 3. Frontend Setup

```bash
# Navigate to the frontend directory
cd medcare-frontend

# Install Node.js dependencies
npm install

# Start the Vite development server
npm run dev
```

**Frontend Application**: `http://localhost:5173`

### 4. Default Admin Credentials

```
Username: admin  (or the seeded admin email)
Password: Admin@12345
```

---

## ?? Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | Yes | `localhost` | PostgreSQL host address |
| `DB_PORT` | Yes | `5432` | PostgreSQL port |
| `DB_NAME` | Yes | `medcare_scm` | Target database name |
| `DB_USER` | Yes | `postgres` | Database username |
| `DB_PASSWORD` | Yes | — | Database password |
| `DB_SCHEMA` | No | `public` | PostgreSQL schema |
| `DATABASE_URL` | No | *(derived from DB_*)* | Full connection string override (`postgresql+asyncpg://...`) |
| `HOST` | No | `0.0.0.0` | FastAPI bind host |
| `PORT` | No | `8000` | FastAPI port |
| `SECRET_KEY` | Yes | — | Secret key for cryptographic signing |
| `JWT_SECRET_KEY` | No | *(configured in .env)* | JWT bearer token signing key |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `MODEL_PATH` | No | `backend/app/ml/saved_models/demand_forecast_model.pkl` | ML model artifact path |
| `ML_RETRAIN_ON_STARTUP` | No | `false` | Retrain ML model on backend startup |
| `ML_CONFIDENCE_LEVEL` | No | `0.87` | Forecast confidence interval level |
| `GEMINI_API_KEY` | No | — | Google Gemini API key (for AI Copilot) |
| `RESEND_API_KEY` | No | — | Resend API key for email alerts |
| `SMTP_HOST` | No | — | SMTP server host (alternative to Resend) |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASSWORD` | No | — | SMTP password |
| `EMAIL_FROM` | No | — | Sender email address for alerts |
| `APP_FRONTEND_URL` | No | `http://localhost:5173` | Frontend URL (used in email links) |
| `CORS_ORIGINS` | No | `*` | Comma-separated allowed CORS origins |

---

## ?? Automated Testing

The project includes a comprehensive `pytest` test suite in `backend/app/tests/` and `backend/database/`.

### Test Modules

| Test File | Coverage |
|---|---|
| `test_e1_inventory.py` | Inventory status transitions, threshold calculations, transaction validations |
| `test_e1_alerts.py` | Alert lifecycle, SLA escalation triggers |
| `test_e1_transactions.py` | Transaction ledger integrity |
| `test_p1_demand_sensing.py` | Forecast generation, seasonal factor multiplication, surge classification |
| `test_p1_expiry_fefo.py` | FEFO chronological allocation, expired batch filtering, aging risk |
| `test_p1_network_balancing.py` | Surplus matching, transfer opportunity identification |
| `test_p1_replenishment.py` | ROQ computation, review frequencies, order constraints |
| `test_p1_scenarios.py` | Parametric stress-testing simulations, metric variance calculations |
| `test_ml_pipeline.py` | Dataset extraction, feature engineering, model training & persistence |
| `test_business_engines_audit.py` | Comprehensive engine audit across all business logic |
| `test_assistant_gemini.py` | Gemini AI Copilot integration tests |
| `test_email_alert_service.py` | Email alert scheduler and dispatch tests |
| `test_e2e_integration_e1.py` | End-to-end E1 inventory integration tests |
| `test_e2e_integration_p1.py` | End-to-end P1 demand/replenishment integration tests |
| `test_replenishment_planning_sections.py` | Replenishment planner section tests |
| `test_database_strict_postgres.py` | PostgreSQL connectivity and schema validation |

### Run Tests

```bash
# Run the full pytest test suite
python -m pytest backend/app/tests/ -v

# Run a specific test module
python -m pytest backend/app/tests/test_e1_inventory.py -v

# Run database-level tests
python -m pytest backend/database/ -v
```

---

## ?? Deployment

Deployment configurations are located in `deployment/`.

### Docker (Recommended)

```bash
# Development — full stack with separate backend & frontend containers
docker-compose -f deployment/docker/docker-compose.yml up --build

# Production — optimised multi-stage build
docker-compose -f deployment/docker/docker-compose.prod.yml up --build
```

**Available Dockerfiles:**

| File | Purpose |
|---|---|
| `Dockerfile.backend` | Backend-only container |
| `Dockerfile.frontend` | Frontend-only Nginx-served container |
| `Dockerfile.fullstack` | Unified single-container deployment |

### Cloud Platforms

Deployment configs are available for:

- **Render** — `deployment/cloud-platforms/render/`
- **Railway** — `deployment/cloud-platforms/railway/`
- **Vercel** — `deployment/cloud-platforms/vercel/` (frontend) + `medcare-frontend/vercel.json`
- **Netlify** — `deployment/cloud-platforms/netlify/`

See `deployment/FREE_HOSTING_STEP_BY_STEP.md` for a step-by-step free-tier hosting guide.

### Unified Static Frontend Serving

When the `medcare-frontend/dist/` build output is present, the FastAPI backend automatically serves the React SPA at the root path, enabling single-container deployment without a separate frontend server.

```bash
# Build frontend for static serving
cd medcare-frontend && npm run build
# Then run backend — it will serve the built frontend automatically
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

---

## ?? Troubleshooting

### 1. PostgreSQL Authentication Failure (`asyncpg.exceptions.InvalidPasswordError`)
- **Cause**: Incorrect `DB_PASSWORD` or `DB_USER` in `.env`.
- **Fix**: Update `.env` with correct credentials. Verify connectivity via `psql -U postgres -h localhost`.

### 2. Port Conflict (Port 8000 or 5173 already in use)
- **Fix**:
  ```bash
  # Change backend port
  uvicorn backend.app.main:app --port 8080 --reload

  # Change frontend port
  npm run dev -- --port 3000
  ```

### 3. Missing Frontend Dependencies
- **Fix**:
  ```bash
  cd medcare-frontend
  rm -rf node_modules package-lock.json
  npm install
  npm run dev
  ```

### 4. ML Model Artifact Missing on First Run
- **Cause**: `demand_forecast_model.pkl` not yet generated.
- **Fix**: The backend trains and serialises the model automatically on the first prediction call, or trigger manually via `POST /api/forecasts/train`. Ensure write permissions exist for `backend/app/ml/saved_models/`.

### 5. GEMINI_API_KEY Not Set (AI Copilot unavailable)
- **Cause**: `GEMINI_API_KEY` not configured in `.env`.
- **Fix**: Set `GEMINI_API_KEY=<your-key>` in `.env`. The AI Copilot (`/api/assistant`) will be unavailable without a valid key.

---

## ?? Project Status

| Module / Subsystem | Status |
|---|---|
| **PostgreSQL Database Schema & DDL** | ? Implemented |
| **FastAPI Async Backend (19 routers)** | ? Implemented |
| **Executive Control Tower Dashboard** | ? Implemented |
| **Inventory & FEFO Batch Ledger** | ? Implemented |
| **Demand Sensing & Surge Detection** | ? Implemented |
| **Replenishment & ROQ Engine** | ? Implemented |
| **Inter-DC Network Balancing** | ? Implemented |
| **Alert & SLA Escalation Engine** | ? Implemented |
| **Distribution Centre Management** | ? Implemented |
| **What-If Scenario Simulator** | ? Implemented |
| **Financial Valuation & CSV Reports** | ? Implemented |
| **Role-Based Access Control (RBAC)** | ? Implemented |
| **Grounded AI Copilot (Gemini)** | ? Implemented |
| **WebSocket Real-Time Push** | ? Implemented |
| **Email Alert Scheduler (Resend/SMTP)** | ? Implemented |
| **ML Pipeline (RandomForestRegressor)** | ? Implemented |
| **Docker & Cloud Deployment Configs** | ? Implemented |
| **pytest Automated Test Suite** | ? Implemented |

---

## ?? Documentation

Additional documentation is available in the `docs/` directory:

| File | Description |
|---|---|
| `architecture.md` | System architecture overview |
| `api.md` | API endpoint reference |
| `database.md` | Database schema documentation |
| `alert-engine.md` | Alert & escalation engine details |
| `demand-forecasting.md` | Demand sensing & ML details |
| `replenishment-engine.md` | Replenishment engine details |
| `expiry-allocation.md` | FEFO expiry allocation details |
| `scenario-engine.md` | Scenario simulation engine details |
| `testing.md` | Testing strategy & approach |
| `deployment.md` | Deployment guide |
| `demo-script.md` | Demo walkthrough script |
| `functional-requirements-specification.md` | Full FRS document |
| `requirements-traceability.md` | Requirements traceability matrix |

---

## ?? License

This project is released under the **MIT License**.
