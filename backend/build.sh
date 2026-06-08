#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  MathPlatform — Render Build Script
#  Handles stale migration history on persistent Render databases.
# ─────────────────────────────────────────────────────────────────
set -e

SETTINGS="mathapi.settings.production"

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

# ── Migration history repair ──────────────────────────────────────
echo "==> Repairing migration history if needed..."

python - <<'PYEOF'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mathapi.settings.production")
django.setup()

from django.db import connection

def table_exists(name):
    return name in connection.introspection.table_names()

def col_exists(table, col):
    if not table_exists(table):
        return False
    cols = {c.name for c in connection.introspection.get_table_description(connection.cursor(), table)}
    return col in cols

def is_applied(app, name):
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1 FROM django_migrations WHERE app=%s AND name=%s", [app, name])
            return c.fetchone() is not None
    except Exception:
        return False

def fake_apply(app, name):
    with connection.cursor() as c:
        c.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW()) ON CONFLICT DO NOTHING",
            [app, name]
        )
    print(f"    [fake-applied] {app}.{name}")

def run_sql(sql, label=""):
    with connection.cursor() as c:
        c.execute(sql)
    if label:
        print(f"    [sql] {label}")

# ── Fake-apply 0001_initial for apps whose table already exists ───
if is_applied("admin", "0001_initial"):
    print("  Stale DB detected — checking local app migrations...")
    for app in ["accounts", "students", "exams"]:
        if not is_applied(app, "0001_initial"):
            fake_apply(app, "0001_initial")

# ── Repair site_settings table: add any missing columns ──────────
# This handles the case where 0001_initial was fake-applied but the
# actual site_settings table/columns were never created.
if table_exists("site_settings"):
    print("  site_settings table exists — checking for missing columns...")
    missing_cols = {
        "platform_name":    "VARCHAR(100) NOT NULL DEFAULT 'MathPlatform'",
        "platform_subtitle":"VARCHAR(100) NOT NULL DEFAULT 'Tanzania'",
        "logo_url":         "VARCHAR(200) NOT NULL DEFAULT ''",
        "logo_letter":      "VARCHAR(3) NOT NULL DEFAULT 'Σ'",
        "favicon_url":      "VARCHAR(200) NOT NULL DEFAULT ''",
        "footer_text":      "TEXT NOT NULL DEFAULT '© 2025 MathPlatform · Built for Tanzanian Secondary Schools'",
        "page_settings":    "JSONB NOT NULL DEFAULT '{}'",
        "updated_at":       "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "updated_by_id":    "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        # New login fields (from 0002)
        "login_tagline":    "VARCHAR(200) NOT NULL DEFAULT 'Student Performance Analytics'",
        "login_welcome":    "VARCHAR(200) NOT NULL DEFAULT 'Sign in to your account'",
        "login_bg_gradient":"BOOLEAN NOT NULL DEFAULT TRUE",
    }
    for col, definition in missing_cols.items():
        if not col_exists("site_settings", col):
            run_sql(f'ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS "{col}" {definition}', f"added site_settings.{col}")
        else:
            print(f"    [ok] site_settings.{col}")
    # Ensure singleton row exists
    with connection.cursor() as c:
        c.execute("INSERT INTO site_settings (id) VALUES (1) ON CONFLICT DO NOTHING")
    print("  site_settings repair complete.")
else:
    print("  site_settings table does not exist — will be created by migrate.")

# ── Fake-apply 0002 if columns now exist (added above) ───────────
if col_exists("site_settings", "login_tagline") and not is_applied("accounts", "0002_sitesettings_login_fields"):
    fake_apply("accounts", "0002_sitesettings_login_fields")
PYEOF

# ── Normal migrate ────────────────────────────────────────────────
echo "==> Running migrations..."
python manage.py migrate --settings="$SETTINGS"

# ── Static files ─────────────────────────────────────────────────
echo "==> Collecting static files..."
python manage.py collectstatic --no-input --settings="$SETTINGS"

# ── Seed demo data (idempotent) ───────────────────────────────────
echo "==> Seeding demo data (skip if already seeded)..."
python manage.py seed_demo --settings="$SETTINGS" || true

echo "==> Build complete."
