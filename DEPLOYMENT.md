# VAYORA Production Deployment Guide

This guide details the step-by-step production deployment for **VAYORA** across:
* **Frontend**: [Vercel](https://vercel.com) (Global Edge Static Hosting)
* **Backend**: [Render](https://render.com) (Python FastAPI Web Service)
* **Database**: [Supabase](https://supabase.com) (Managed Cloud PostgreSQL)

---

## 🏗️ System Architecture

```text
┌────────────────────────┐         HTTPS / WSS          ┌────────────────────────┐
│     Vercel Edge        │ ───────────────────────────> │     Render Cloud       │
│  (Frontend HTML/JS/CSS)│ <─────────────────────────── │   (FastAPI Backend)    │
│  https://*.vercel.app  │          CORS Enabled        │ https://*.onrender.com │
└────────────────────────┘                              └───────────┬────────────┘
                                                                    │
                                                                    │ PostgreSQL
                                                                    ▼
                                                        ┌────────────────────────┐
                                                        │     Supabase Cloud     │
                                                        │   (PostgreSQL 17.11)   │
                                                        │  aws-0-eu-west-1 pooler│
                                                        └────────────────────────┘
```

---

## 1. Backend Deployment on Render

### Method A: 1-Click Blueprint (Recommended)
1. Log in to [Render Dashboard](https://dashboard.render.com).
2. Click **New +** -> **Blueprint**.
3. Connect your repository: `chiru22122/VAYORA`.
4. Render automatically parses [`render.yaml`](./render.yaml).
5. When prompted, enter your environment secrets (see checklist below) and click **Apply**.

---

### Method B: Manual Web Service Setup
1. In Render Dashboard, click **New +** -> **Web Service**.
2. Select repository: `chiru22122/VAYORA`.
3. Configure the service settings:
   * **Name**: `vayora-backend`
   * **Region**: `Frankfurt (EU Central)` *(closest to Supabase eu-west-1 Ireland)*
   * **Branch**: `main`
   * **Root Directory**: *(leave blank for repo root)*
   * **Runtime**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   * **Plan**: `Free`

---

### Backend Environment Variables (Render Dashboard)

Add these in **Render Dashboard** -> **Environment**:

| Variable | Recommended Value | Purpose |
|---|---|---|
| `PYTHON_VERSION` | `3.11.9` | Python runtime version |
| `ENVIRONMENT` | `production` | Platform environment mode |
| `DATABASE_URL` | `postgresql+psycopg://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres` | Supabase Cloud Database Connection |
| `SECRET_KEY` | *(Click "Generate" or paste a 64-char key)* | JWT Token Encryption Key |
| `ALGORITHM` | `HS256` | JWT signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Session lifetime (24 hours) |
| `FRONTEND_URL` | `https://your-app.vercel.app` | Allowed CORS production frontend origin (comma-separated for multiples) |
| `ALLOW_VERCEL_PREVIEWS` | `false` | Optional: Set `true` to allow scoped VAYORA preview domains (`https://vayora-*.vercel.app`) |
| `BACKEND_URL` | `https://vayora-backend.onrender.com` | Public backend service URL |
| `DEMO_EXCHANGE_RATE_USDT_INR` | `86.50` | Default benchmark rate |
| `SMTP_HOST` | `smtp.gmail.com` | Email delivery host |
| `SMTP_PORT` | `587` | Email delivery port |
| `SMTP_USER` | `your-email@gmail.com` | Sender Gmail address |
| `SMTP_PASSWORD` | `your-16-char-app-password` | 16-character Google App Password |
| `SMTP_FROM_EMAIL` | `no-reply@vayora.network` | From header address |
| `SMTP_FROM_NAME` | `VAYORA Security & FinTech` | Display sender name |
| `SMTP_USE_TLS` | `true` | Secure TLS transport |
| `SMTP_USE_SSL` | `false` | Explicit SSL flag |
| `STRIPE_MODE` | `sandbox` | Payment gateway test mode |
| `STRIPE_SECRET_KEY` | `sk_test_...` | Stripe sandbox secret key |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_...` | Stripe sandbox public key |

---

## 2. Frontend Deployment on Vercel

### Step-by-Step Setup
1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import `chiru22122/VAYORA`.
4. Configure the project:
   * **Framework Preset**: `Other`
   * **Root Directory**: `./` *(Default - root `vercel.json` automatically serves `frontend`)*
   * **Build Command**: *(Leave empty)*
   * **Output Directory**: *(Handled automatically as `frontend` by `vercel.json`)*
5. Click **Deploy**.

---

### Frontend Environment Variables (Vercel Dashboard)
In **Vercel Project Settings** -> **Environment Variables**, add:

| Key | Value | Purpose |
|---|---|---|
| `APP_NAME` | `VAYORA - Your Digital Value, One Journey` | Browser application title |
| `BACKEND_URL` | `https://vayora-backend.onrender.com` | Render production API endpoint |

*(Also editable directly in `frontend/config.js` or dynamically via browser localStorage).*

---

## 3. Post-Deployment Verification Checklist

1. **Verify Backend Health**:
   ```bash
   curl https://vayora-backend.onrender.com/api/health
   ```
   Expected response:
   ```json
   {
     "status": "healthy",
     "system": "VAYORA Core Engine",
     "version": "1.0.0",
     "environment": "production"
   }
   ```

2. **Verify Interactive API Docs**:
   Visit `https://vayora-backend.onrender.com/api/docs` in your browser.

3. **Verify Frontend Live Site**:
   Visit your Vercel deployment URL (e.g. `https://vayora.vercel.app`).
   - Sign in with demo credentials:
     - User A: `sender@vayora.demo` / `Password@123`
     - User B: `receiver@vayora.demo` / `Password@123`
     - Admin: `admin@vayora.demo` / `Admin@123`
   - Observe live database balance loading directly from Supabase.
