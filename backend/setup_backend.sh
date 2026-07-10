#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  MathPlatform — Backend Setup & Run
#  Works on macOS and Linux. No Docker required.
#  Usage:  bash setup_backend.sh
# ─────────────────────────────────────────────────────────────────
set -e

cd "$(dirname "$0")"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  MathPlatform — Backend Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. Check Python
echo -e "\n${YELLOW}▸ Checking Python version...${NC}"
python3 --version

# 2. Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "\n${YELLOW}▸ Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# 3. Activate
echo -e "\n${YELLOW}▸ Activating virtual environment...${NC}"
source venv/bin/activate

# 4. Install dependencies
echo -e "\n${YELLOW}▸ Installing Python dependencies...${NC}"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

# 5. Migrate
echo -e "\n${YELLOW}▸ Running database migrations...${NC}"
python manage.py migrate --run-syncdb
echo -e "${GREEN}  ✓ Migrations done (SQLite: db.sqlite3)${NC}"

# 6. Seed demo data
echo -e "\n${YELLOW}▸ Seeding demo data...${NC}"
python manage.py seed_demo
echo -e "${GREEN}  ✓ Demo data ready${NC}"

# 7. Start dev server
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  API running at → http://localhost:8000/api/${NC}"
echo -e "${GREEN}  Admin panel   → http://localhost:8000/admin/${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
python manage.py runserver
