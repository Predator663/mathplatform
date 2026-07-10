# Deploying MathPlatform to Render

## Prerequisites
- A [Render account](https://render.com) (free tier works)
- Your code pushed to a **GitHub or GitLab** repository

---

## Step 1 — Push to GitHub

```bash
cd mathplatform
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mathplatform.git
git push -u origin main
```

---

## Step 2 — Deploy via Render Blueprint (recommended — one click)

1. Go to **https://render.com/deploy** and paste your repo URL, OR
2. In the Render dashboard → **New → Blueprint** → connect your repo.
3. Render reads `render.yaml` and creates:
   - `mathplatform-db` — PostgreSQL (free)
   - `mathplatform-api` — Django web service (free)
   - `mathplatform-frontend` — React static site (free)
4. Click **Apply** and wait ~5 minutes for the first build.

---

## Step 3 — Update CORS after first deploy

Once both services are live:

1. Open `mathplatform-api` → **Environment** in the Render dashboard.
2. Set:
   ```
   CORS_ALLOWED_ORIGINS = https://mathplatform-frontend.onrender.com
   CORS_ALLOW_ALL_ORIGINS = False
   ```
3. **Save** — the service redeploys automatically.

---

## Step 4 — Verify

| URL | What you should see |
|-----|---------------------|
| `https://mathplatform-frontend.onrender.com` | Login page |
| `https://mathplatform-api.onrender.com/api/auth/settings/` | JSON settings response |
| `https://mathplatform-api.onrender.com/admin/` | Django admin |

Demo credentials (created by `seed_demo`):
| Role | Email | Password |
|------|-------|----------|
| Super Admin | admin@amani.ac.tz | admin1234 |
| Teacher | teacher@amani.ac.tz | teacher1234 |

---

## Manual deploy (without Blueprint)

### Backend (Web Service)
| Field | Value |
|-------|-------|
| Runtime | Python 3 |
| Root directory | `backend` |
| Build command | `./build.sh` |
| Start command | `gunicorn mathapi.wsgi:application --bind 0.0.0.0:$PORT --workers 2` |

**Environment variables:**
```
DJANGO_SETTINGS_MODULE = mathapi.settings.production
SECRET_KEY             = <generate a random 50-char string>
DEBUG                  = False
DATABASE_URL           = <from the PostgreSQL service>
ALLOWED_HOSTS          = your-api.onrender.com
CORS_ALLOW_ALL_ORIGINS = True
```

### PostgreSQL
Create a **PostgreSQL** service, copy its **Internal Database URL** into the
`DATABASE_URL` env var of the backend.

### Frontend (Static Site)
| Field | Value |
|-------|-------|
| Root directory | `frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `dist` |

**Environment variables:**
```
VITE_API_URL = https://your-api.onrender.com
```

**Redirects/Rewrites:** Add a rewrite rule:
```
Source:      /*
Destination: /index.html
Action:      Rewrite
```

---

## Free tier notes
- Free services spin down after 15 min of inactivity — first request after sleep takes ~30s.
- Free PostgreSQL expires after 90 days on the legacy free plan; check current Render pricing.
- To keep the service warm, use [UptimeRobot](https://uptimerobot.com) to ping the API every 10 minutes.
