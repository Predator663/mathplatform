#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  MathPlatform PWA — Frontend Setup & Run
#  Usage:  bash setup_frontend.sh
# ─────────────────────────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  MathPlatform PWA — Frontend Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${YELLOW}▸ Checking Node version...${NC}"
node --version && npm --version

echo -e "\n${YELLOW}▸ Installing dependencies (includes vite-plugin-pwa + idb)...${NC}"
npm install
echo -e "${GREEN}  ✓ Dependencies installed${NC}"

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Dev server → http://localhost:5173${NC}"
echo -e ""
echo -e "  PWA notes:"
echo -e "  • Service worker only activates in PRODUCTION build"
echo -e "  • To test PWA: npm run build && npm run preview"
echo -e "  • Offline cache populates on first online visit"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
npm run dev
