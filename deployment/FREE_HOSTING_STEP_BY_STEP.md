# 🌐 Free Cloud Hosting Guide: MedCare Pharma SCM Control Tower

This guide walked you through hosting the entire **MedCare Pharma SCM Control Tower** on **100% Free Hosting Services** with **$0/month cost** and **NO credit card required**.

---

## 🏗 The Recommended Free Architecture Stack

| Layer | Provider | Free Tier Limits | Cost |
|---|---|---|---|
| **Frontend UI** | **[Vercel](https://vercel.com/)** or **[Render Static](https://render.com/)** | 100 GB bandwidth, unlimited deploys, fast global CDN, **zero sleep/cold starts** | **$0.00** / mo |
| **Backend API** | **[Render](https://render.com/)** or **[Koyeb](https://koyeb.com/)** | 512 MB RAM, 0.1 CPU, automatic HTTPS, WebSocket support | **$0.00** / mo |
| **PostgreSQL DB** | **[Neon.tech](https://neon.tech/)** or **[Supabase](https://supabase.com/)** | 0.5 GB storage, serverless autoscaling, SSL encryption | **$0.00** / mo |
| **AI SCM Copilot** | **[Google AI Studio](https://aistudio.google.com/)** | Gemini 1.5/2.0 Flash (15 RPM free tier) | **$0.00** / mo |
| **Email Alerts** | **[Resend](https://resend.com/)** | 3,000 emails/month free | **$0.00** / mo |

---

## 📋 Step-by-Step Deployment Walkthrough

---

### 🟢 STEP 1: Set Up Free PostgreSQL Database on Neon (2 Minutes)

1. Go to **[https://neon.tech](https://neon.tech/)** and click **Sign Up** (Sign in with GitHub or Google — no credit card needed).
2. Click **Create Project**:
   - **Project Name**: `medcare-scm`
   - **Postgres Version**: `16` (Default)
   - **Region**: Choose the region closest to you (e.g., `US East (Ohio)` or `Europe (Frankfurt)`).
3. Once created, you will see your **Connection String**.
4. In the connection string dropdown:
   - Select **Connection string** -> Choose **Pooled connection** (or Direct).
   - Your connection string will look like:
     ```text
     postgresql://neondb_owner:npg_AbCdEf12345@ep-cool-cloud-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
5. **Save this connection string!** You will paste it into Render in Step 2.

> [!TIP]
> MedCare's async database engine automatically formats `postgresql://` and `postgres://` URLs to `postgresql+asyncpg://` behind the scenes!

---

### 🟢 STEP 2: Deploy Backend API to Render (4 Minutes)

1. Push your MedCare repository to **GitHub** (public or private).
2. Go to **[https://render.com](https://render.com/)** and click **Get Started for Free** (Sign in with GitHub).
3. In your Render Dashboard, click **New +** -> Select **Web Service**.
4. Choose **Build and deploy from a Git repository** -> Connect your `medcare-pharma-control-tower` repository.
5. Fill in the service configuration:
   - **Name**: `medcare-backend` (or your preferred name)
   - **Region**: Same region as your Neon database (e.g., `Oregon (US West)` or `Frankfurt`)
   - **Branch**: `main`
   - **Root Directory**: Leave blank (root of repo)
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install --upgrade pip && pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
     ```
   - **Instance Type**: Select **Free** ($0 / month).

6. Scroll down to **Environment Variables** and click **Add Environment Variable**:

   | Key | Value | Notes |
   |---|---|---|
   | `DATABASE_URL` | `postgresql://...` | *Paste your Neon connection string from Step 1* |
   | `CORS_ORIGINS` | `*` | *Allows frontend to communicate with API* |
   | `JWT_SECRET_KEY` | *Click "Generate"* | *Render generates a secure random key* |
   | `ADMIN_INITIAL_PASSWORD` | `Admin@12345` | *Default admin login password* |
   | `GEMINI_API_KEY` | `your_gemini_api_key` | *(Optional) Free key from Google AI Studio* |
   | `RESEND_API_KEY` | `your_resend_key` | *(Optional) Free key from Resend* |

7. Click **Create Web Service**.
8. Render will now build and deploy your backend:
   - It will install dependencies, automatically connect to your Neon PostgreSQL database, create all 28 tables, and run the initial data seeder.
   - Once deployment completes, your backend URL will be live at:
     ```text
     https://medcare-backend-xxxx.onrender.com
     ```
9. Verify your backend is live by opening: `https://medcare-backend-xxxx.onrender.com/api/health` in your browser. You should see `{"status":"HEALTHY","database":"CONNECTED",...}`!

---

### 🟢 STEP 3: Deploy Frontend UI to Vercel (3 Minutes)

1. Go to **[https://vercel.com](https://vercel.com/)** and sign in with GitHub.
2. Click **Add New...** -> **Project**.
3. Import your `medcare-pharma-control-tower` repository.
4. In the configuration screen:
   - **Project Name**: `medcare-pharma` (or your preferred name)
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click **Edit** -> Select `medcare-frontend` -> Click **Continue**.
   - **Build Command**: `npm run build` (Default)
   - **Output Directory**: `dist` (Default)
5. Expand **Environment Variables** and add:
   - **Name**: `VITE_API_BASE_URL`
   - **Value**: `https://medcare-backend-xxxx.onrender.com/api` *(Your Render backend URL from Step 2 with `/api` at the end)*
   - **Name**: `VITE_WS_URL`
   - **Value**: `wss://medcare-backend-xxxx.onrender.com/api/ws` *(Your Render backend WebSocket URL with `wss://`)*
6. Click **Deploy**.
7. In ~60 seconds, Vercel will give you your free live production URL:
   ```text
   https://medcare-pharma.vercel.app
   ```

---

### 🟢 STEP 4: Login & Verify Live System

1. Open your live frontend URL (e.g. `https://medcare-pharma.vercel.app`).
2. Log in using the seeded administrator credentials:
   - **Email**: `admin@medcare.com`
   - **Password**: `Admin@12345`
3. Verify that:
   - **Executive Dashboard**: Displays live KPI metrics, stock valuation, and stock trajectories.
   - **Inventory Ledger**: Shows real-time product balances across all warehouses.
   - **FEFO Expiry Tracker**: Shows batch aging with color-coded risk stratification.
   - **Demand Sensing**: Displays forward 30-day ML forecasts with event overlays.
   - **AI Copilot**: Test querying the live database via the chat assistant!

---

## ⚡ Alternative Free Setup: Single-Container Unified Web Service

If you prefer to have **only 1 service** instead of two:

1. Build the React frontend locally or in Render:
   ```bash
   python deployment/scripts/build_fullstack.py
   ```
2. Commit the `medcare-frontend/dist` directory to your repository.
3. On Render.com, create a single **Web Service** using the root repository.
4. FastAPI will automatically detect `medcare-frontend/dist` and serve both:
   - Your API at `https://your-service.onrender.com/api/*`
   - Your React UI at `https://your-service.onrender.com/`
5. Single URL, zero CORS setup needed, 100% free!

---

## 💡 Free Tier Pro-Tips & Best Practices

### 1. Preventing Render Free-Tier Cold Starts
Render free web services enter sleep mode after 15 minutes of inactivity. When a new request arrives, it takes ~40-50 seconds to wake up.

**How to keep it awake for free 24/7:**
1. Go to **[https://uptimerobot.com](https://uptimerobot.com/)** or **[https://cron-job.org](https://cron-job.org/)** (both 100% free).
2. Create an **HTTP Monitor**:
   - **URL**: `https://medcare-backend-xxxx.onrender.com/api/health`
   - **Interval**: Every `10 minutes`
3. This sends a lightweight ping to your health endpoint, keeping your backend awake with zero cold starts!

### 2. Free AI API Key (Gemini)
To enable the grounded AI supply chain copilot:
1. Visit **[https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)**.
2. Click **Create API Key** (Free tier gives 15 requests per minute with Gemini 1.5 Flash).
3. Paste the key into Render's `GEMINI_API_KEY` environment variable.

### 3. Free Alert Email Dispatch (Resend)
To enable automated email notifications for critical shortages and expiry risks:
1. Visit **[https://resend.com/](https://resend.com/)** and create a free account (3,000 free emails/month).
2. Copy your API Key and paste into Render's `RESEND_API_KEY` environment variable.
