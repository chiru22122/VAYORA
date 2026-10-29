# VAYORA Production Deployment Guide (Vercel Unified Architecture)

This guide details the single-platform production deployment for **VAYORA** hosted entirely on **Vercel**:
* **Frontend**: Vanilla HTML5, CSS3, and ES6+ JavaScript in `frontend/`
* **Backend**: Python FastAPI running via Vercel Serverless Functions (`api/index.py` -> `backend.main:app`)
* **Database**: [Supabase](https://supabase.com) (Managed Cloud PostgreSQL 17.11)

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        VERCEL EDGE NETWORK                             │
│                  https://<your-project>.vercel.app                     │
├───────────────────────────────────┬────────────────────────────────────┤
│         STATIC FRONTEND           │        SERVERLESS API BACKEND      │
│     All paths matching /(.*)      │       All paths matching /api/*    │
│           (rewrites)              │               (rewrites)           │
│                │                  │                   │                │
│                ▼                  │                   ▼                │
│     frontend/*.html, CSS, JS      │            api/index.py            │
│  frontend/index.html served at /  │          (FastAPI ASGI app)        │
└───────────────────────────────────┴───────────────────┬────────────────┘
                                                        │
                                                        │ Supabase Session Pooler
                                                        ▼
                                            ┌────────────────────────────┐
                                            │   Supabase Cloud Postgres  │
                                            │      (AWS eu-west-1)       │
                                            └────────────────────────────┘
```

---

## 1. Vercel Project Setup (Single Unified Project)

1. Log in to [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** -> **Project**.
3. Import your GitHub repository: `chiru22122/VAYORA`.
4. Configure Project Settings:
   * **Framework Preset**: `Other`
   * **Root Directory**: `./` *(Default)*
   * **Build Command**: *(Leave empty — Vercel reads `vercel.json`)*
   * **Output Directory**: *(Leave empty — handled automatically by `vercel.json`)*
5. Add **Environment Variables** (see table below).
6. Click **Deploy**.

---

## 2. Required Vercel Environment Variables

Add these in **Vercel Dashboard** -> **Project Settings** -> **Environment Variables** (apply to **Production**, **Preview**, and **Development**):

| Variable | Recommended Value / Format | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `postgresql+psycopg://postgres.<PROJECT_REF>:<PASSWORD>@aws-0-eu-west-1.pooler.supabase.com:5432/postgres` | Supabase Cloud Database Connection via IPv4 Pooler |
| `SECRET_KEY` | *(Paste a 64-character secret key or random hex)* | JWT token signing & session encryption |
| `ALGORITHM` | `HS256` | JWT signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Session lifetime (24 hours) |
| `ENVIRONMENT` | `production` | Platform environment mode |
| `DEMO_EXCHANGE_RATE_USDT_INR` | `86.50` | Default benchmark exchange rate |
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

## 3. Email & Real-Time Considerations on Vercel

* **Email Delivery**: 
  * Direct SMTP (`smtp.gmail.com:587`) runs synchronously inside the serverless handler before the container freezes.
  * For high-throughput transactional emails, an HTTPS API like Resend (`RESEND_API_KEY`) is recommended.
* **Real-Time Presence**:
  * Persistent bidirectional WebSockets are unsupported on ephemeral serverless functions.
  * The frontend automatically falls back to periodic HTTP heartbeats (`/api/user/heartbeat` every 15s) to track online users without interruption.
  * Instant event broadcasts can utilize Supabase Realtime channels directly from the client.

---

## 4. Post-Deployment Verification Checklist

1. **Verify Backend Health & OpenAPI Docs**:
   * Visit `https://<your-project>.vercel.app/api/health`
     Expected JSON response:
     ```json
     {
       "status": "healthy",
       "system": "VAYORA Core Engine",
       "version": "1.0.0"
     }
     ```
   * Visit `https://<your-project>.vercel.app/api/docs` to verify interactive Swagger API docs.

2. **Verify Frontend Live Site**:
   * Visit `https://<your-project>.vercel.app/`
   * Confirm the landing page loads cleanly.
   * Test logging in via `login.html`:
     - Demo User: `sender@vayora.demo` / `Password@123`
     - Verify wallet balances load directly from Supabase PostgreSQL via `/api/wallet/balances`.
