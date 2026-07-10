# MathPlatform — Student Performance Analytics

A full-stack mathematics school platform for analysing student performance trends across examinations.

**Stack:** Django 5 · Django REST Framework · React 18 · Vite · TypeScript · Tailwind CSS · Recharts · SQLite (dev) · JWT Auth

---

## Prerequisites

| Tool | Minimum version | Download |
|---|---|---|
| Python | 3.10+ | https://python.org |
| Node.js | 18+ | https://nodejs.org |
| npm | 9+ | Included with Node |

No database server needed — SQLite is used out of the box.

---

## Setup: Two terminals, five minutes

### Terminal 1 — Backend

**macOS / Linux**
```bash
cd mathplatform/backend
bash setup_backend.sh
```

**Windows**
```bat
cd mathplatform\backend
setup_backend.bat
```

This script will:
1. Create a Python virtual environment (`venv/`)
2. Install all Python packages from `requirements.txt`
3. Run Django migrations (creates `db.sqlite3`)
4. Seed demo data — 20 students, 7 exams, 2 classrooms
5. Start the API server at **http://localhost:8000**

### Terminal 2 — Frontend

**macOS / Linux**
```bash
cd mathplatform/frontend
bash setup_frontend.sh
```

**Windows**
```bat
cd mathplatform\frontend
setup_frontend.bat
```

This script will:
1. Install all npm packages
2. Start the Vite dev server at **http://localhost:5173**

Open **http://localhost:5173** in your browser.

---

## After first run (subsequent starts)

Once set up, you don't need to re-run the setup scripts. Use these instead:

**Backend**
```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
python manage.py runserver
```

**Frontend**
```bash
cd frontend
npm run dev
```

---

## Demo Credentials

| Role    | Email                              | Password   |
|---------|------------------------------------|------------|
| Admin   | admin@mathplatform.edu             | admin123   |
| Teacher | teacher@mathplatform.edu           | teacher123 |
| Student | alice.adeyemi@student.mathplatform.edu | student123 |

---

## Project Structure

```
mathplatform/
├── backend/
│   ├── mathapi/
│   │   ├── apps/
│   │   │   ├── accounts/     # Auth, users, roles, audit log
│   │   │   ├── students/     # Grade levels, classrooms, profiles
│   │   │   ├── exams/        # Exams, scores, topic weights
│   │   │   ├── analytics/    # Trend engine, at-risk, heatmaps
│   │   │   └── reports/      # Report generation, CSV export
│   │   ├── settings/
│   │   └── urls.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── setup_backend.sh      ← run this first (Mac/Linux)
│   └── setup_backend.bat     ← run this first (Windows)
│
└── frontend/
    ├── src/
    │   ├── api/              # Axios client + all API calls
    │   ├── components/       # Layout, UI components
    │   ├── pages/            # All page components
    │   ├── store/            # Zustand auth store
    │   ├── types/            # TypeScript types
    │   └── utils/            # Formatters, helpers
    ├── package.json
    ├── vite.config.ts
    ├── setup_frontend.sh     ← run this first (Mac/Linux)
    └── setup_frontend.bat    ← run this first (Windows)
```

---

## Pages & Features

| Page | Path | Description |
|---|---|---|
| Login | `/login` | JWT auth with demo credential display |
| Dashboard | `/dashboard` | KPI cards, recent exams chart, at-risk alert |
| Students | `/students` | Searchable student list with analytics link |
| Exams | `/exams` | Exam list, stats, publish flow |
| Create Exam | `/exams/new` | Full exam form with topic weight builder |
| Exam Detail | `/exams/:id` | Score table, distribution chart, edit scores |
| Analytics Hub | `/analytics` | Entry point to all analytics views |
| Student Analytics | `/analytics/student/:id` | Timeline, radar chart, topic breakdown |
| Class Analytics | `/analytics/class` | Classroom selector, trend lines, rankings |
| At-Risk | `/at-risk` | Flagged students with sparklines |
| Reports | `/reports` | Student report + exam CSV export |

---

## API Endpoints

### Auth — `/api/auth/`
```
POST   /login/             → JWT access + refresh tokens
POST   /logout/            → Blacklist refresh token
POST   /token/refresh/     → Get new access token
GET    /me/                → Current user profile
POST   /register/          → Create user
POST   /change-password/   → Change password
GET    /users/             → List users
```

### Students — `/api/students/`
```
GET/POST        /grade-levels/
GET/POST        /classrooms/
GET             /classrooms/:id/students/
GET/POST        /profiles/
GET/PATCH       /profiles/:id/
GET             /profiles/:id/performance_summary/
```

### Exams — `/api/exams/`
```
GET/POST        /topics/
GET/POST        /exams/
GET/PATCH       /exams/:id/
POST            /exams/:id/publish/
GET             /exams/:id/scores/
GET             /exams/:id/statistics/
POST            /exams/:id/bulk_scores/
GET/POST        /scores/
GET/PATCH       /scores/:id/
GET             /scores/:id/history/
```

### Analytics — `/api/analytics/`
```
GET    /dashboard/
GET    /students/:id/summary/
GET    /students/:id/trend/          ?exam_type=final&term=term_2
GET    /students/:id/topics/
GET    /classrooms/:id/              ?term=term_1&academic_year=2024/2025
GET    /classrooms/:id/heatmap/
GET    /at-risk/                     ?classroom_id=1&threshold=50
GET    /compare/                     ?classroom_ids=1,2&term=term_1
```

### Reports — `/api/reports/`
```
GET    /student/:id/
GET    /classroom/:id/
GET    /export/exam/:id/csv/
GET    /export/classroom/:id/csv/
```

---

## Analytics Engine

All performance computations live in `backend/mathapi/apps/analytics/services.py`:

- **Trend detection** — linear regression slope → improving / stable / declining
- **Moving average** — 3-point smoothing on score timelines
- **Topic mastery** — per-topic percentage with trend per student
- **At-risk detection** — flags students below threshold OR with >10% decline over last 3 exams
- **Score distribution** — bucketed into 6 bands (0-49, 50-59, 60-69, 70-79, 80-89, 90-100)
- **Class comparisons** — averages, pass rates, rankings across classrooms

## Data & Audit Integrity

- Every score edit logs old/new value + editor in `ScoreEditLog`
- All logins and mutations tracked in `AuditLog`
- Bulk score upload returns per-row errors without aborting the whole batch
- Score validation: cannot exceed `max_score`, no negative values
- Topic weight sum must equal exam `max_score` before saving

---

## Switching to PostgreSQL later

When you're ready for production, install psycopg2 and update `settings/base.py`:

```bash
pip install psycopg2-binary
```

```python
# mathapi/settings/base.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'mathplatform',
        'USER': 'youruser',
        'PASSWORD': 'yourpassword',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

Then re-run `python manage.py migrate`.
