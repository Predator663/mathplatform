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
# Render's PostgreSQL persists between deploys. If admin migrations
# were applied before our custom User model migrations (accounts,
# students, exams), Django raises InconsistentMigrationHistory.
#
# Strategy: if admin.0001_initial is already applied but any of our
# local app migrations are missing, directly INSERT the missing rows
# into django_migrations so Django considers them applied, then let
# the normal migrate run handle anything genuinely pending.
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
        return False  # django_migrations table doesn't exist yet — fresh DB

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
else:
    print("  Fresh DB — no repair needed.")

# ── Repair site_settings table: add any missing columns ──────────
# This handles the case where 0001_initial was fake-applied but the
# actual site_settings table/columns were never created.
# It ALSO handles partial deploys where new columns exist but the
# existing singleton row has NULLs (because it was inserted before
# the column existed). We always patch NULLs before migrate runs.
if table_exists("site_settings"):
    print("  site_settings table exists — checking for missing columns...")
    # Every column the model has ever had — keyed by migration that added it.
    # Adding a new column here is the ONLY change needed for future migrations.
    missing_cols = {
        # 0001_initial
        "platform_name":    "VARCHAR(100) NOT NULL DEFAULT 'MathPlatform'",
        "platform_subtitle":"VARCHAR(100) NOT NULL DEFAULT 'Tanzania'",
        "logo_url":         "VARCHAR(200) NOT NULL DEFAULT ''",
        "logo_letter":      "VARCHAR(3) NOT NULL DEFAULT 'Σ'",
        "favicon_url":      "VARCHAR(200) NOT NULL DEFAULT ''",
        "footer_text":      "TEXT NOT NULL DEFAULT '© 2025 MathPlatform · Built for Tanzanian Secondary Schools'",
        "page_settings":    "JSONB NOT NULL DEFAULT '{}'",
        "updated_at":       "TIMESTAMPTZ NOT NULL DEFAULT NOW()",
        "updated_by_id":    "INTEGER REFERENCES users(id) ON DELETE SET NULL",
        # 0002_sitesettings_login_fields
        "login_tagline":    "VARCHAR(200) NOT NULL DEFAULT 'Student Performance Analytics'",
        "login_welcome":    "VARCHAR(200) NOT NULL DEFAULT 'Sign in to your account'",
        "login_bg_gradient":"BOOLEAN NOT NULL DEFAULT TRUE",
        # 0006_sitesettings_legal_pages
        "privacy_policy":   "TEXT NOT NULL DEFAULT ''",
        "terms_of_use":     "TEXT NOT NULL DEFAULT ''",
        "about_me":         "TEXT NOT NULL DEFAULT ''",
        # 0007_sitesettings_pwa_icon_url
        "pwa_icon_url":     "VARCHAR(200) NOT NULL DEFAULT ''",
        # 0008_sitesettings_teacher_permissions
        "teacher_permissions": "JSONB NOT NULL DEFAULT '{}'",
    }
    for col, definition in missing_cols.items():
        if not col_exists("site_settings", col):
            run_sql(f'ALTER TABLE site_settings ADD COLUMN IF NOT EXISTS "{col}" {definition}', f"added site_settings.{col}")
        else:
            print(f"    [ok] site_settings.{col}")

    # ── Patch NULLs in any existing row (safe no-op if already set) ──
    # This is the critical step: if a prior deploy added a column AFTER
    # the singleton was inserted, the row has NULLs. We fill them here
    # BEFORE migrate runs so the NOT NULL constraint is never violated.
    with connection.cursor() as c:
        c.execute("""
UPDATE site_settings SET
    privacy_policy    = COALESCE(privacy_policy,    ''),
    terms_of_use      = COALESCE(terms_of_use,      ''),
    about_me          = COALESCE(about_me,          ''),
    login_tagline     = COALESCE(login_tagline,     'Student Performance Analytics'),
    login_welcome     = COALESCE(login_welcome,     'Sign in to your account'),
    pwa_icon_url      = COALESCE(pwa_icon_url,      ''),
    teacher_permissions = COALESCE(teacher_permissions, '{}'::jsonb)
WHERE id = 1
""")
    print("    [patched] NULL columns filled in site_settings row")

    # ── Ensure singleton row exists (upsert all known columns) ───────
    with connection.cursor() as c:
        c.execute("""
INSERT INTO site_settings (
    id,
    platform_name,
    platform_subtitle,
    logo_url,
    logo_letter,
    favicon_url,
    footer_text,
    page_settings,
    updated_at,
    updated_by_id,
    login_tagline,
    login_welcome,
    login_bg_gradient,
    privacy_policy,
    terms_of_use,
    about_me,
    pwa_icon_url,
    teacher_permissions
)
VALUES (
    1,
    'MathPlatform',
    'Tanzania',
    '',
    'M',
    '',
    '© 2025 MathPlatform',
    '{}'::jsonb,
    NOW(),
    NULL,
    'Student Performance Analytics',
    'Sign in to your account',
    TRUE,
    '',
    '',
    '',
    '',
    '{}'::jsonb
)
ON CONFLICT (id) DO NOTHING
""")
    print("  site_settings repair complete.")
else:
    print("  site_settings table does not exist — will be created by migrate.")

# ── Fake-apply migrations whose columns now exist ────────────────
if col_exists("site_settings", "login_tagline") and not is_applied("accounts", "0002_sitesettings_login_fields"):
    fake_apply("accounts", "0002_sitesettings_login_fields")
if col_exists("site_settings", "privacy_policy") and not is_applied("accounts", "0006_sitesettings_legal_pages"):
    fake_apply("accounts", "0006_sitesettings_legal_pages")
PYEOF

# ── Normal migrate ────────────────────────────────────────────────
echo "==> Running migrations..."
python manage.py migrate --settings="$SETTINGS"

# ── Static files ─────────────────────────────────────────────────
echo "==> Collecting static files..."
python manage.py collectstatic --no-input --settings="$SETTINGS"

# ── Seed demo data (idempotent) ───────────────────────────────────
# NOTE: previously this was `... || true`, which silently swallowed any
# exception from seed_demo. That meant a failed seed (bad state, a
# get_or_create conflict, etc.) still reported "Build succeeded" on
# Render with an EMPTY database — the exact cause of a dashboard that
# shows 0 everywhere with no error anywhere in sight. We still don't
# want a seed failure to fail the whole deploy (the app should still
# come up even if demo data can't be (re)seeded), but the failure must
# be impossible to miss in the logs.
echo "==> Seeding demo data (skip if already seeded)..."
if ! python manage.py seed_demo --settings="$SETTINGS"; then
    echo ""
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo "!! seed_demo FAILED — see traceback above. The database may now"
    echo "!! be missing demo data, which will make the dashboard show 0s"
    echo "!! and empty graphs. Deploy is continuing anyway, but you should"
    echo "!! fix this and re-run: python manage.py seed_demo"
    echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
    echo ""
fi

echo "==> Build complete."
