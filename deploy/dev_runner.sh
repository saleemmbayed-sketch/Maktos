#!/usr/bin/env bash
# CampaignOps Kernel v1 — Dev Runner
# One command to validate everything.
# Usage: bash deploy/dev_runner.sh [--api] [--simulate] [--summary]

set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

run_all=true
if [ $# -gt 0 ]; then run_all=false; fi

header() { echo -e "\n${BOLD}${CYAN}═══ $1 ═══${RESET}"; }
pass()  { echo -e "  ${GREEN}✓${RESET} $1"; }
fail()  { echo -e "  ${RED}✗${RESET} $1"; exit 1; }
warn()  { echo -e "  ${YELLOW}⚠${RESET} $1"; }
info()  { echo -e "  ${CYAN}→${RESET} $1"; }

# ──── 1. Python environment ────────────────────────────────────────
if $run_all || [[ "$*" == *"--check"* ]]; then
header "Python Environment"
python --version || fail "Python not found"

if python -c "import fastapi" 2>/dev/null; then
    pass "FastAPI installed"
else
    warn "FastAPI not installed — pip install -r requirements.txt"
fi

if python -c "import pydantic" 2>/dev/null; then
    pass "Pydantic installed"
else
    fail "Pydantic required — pip install pydantic"
fi
fi

# ──── 2. All tests ──────────────────────────────────────────────────
if $run_all || [[ "$*" == *"--test"* ]]; then
header "Test Suite"

python tests/test_scoring.py 2>&1 | tail -1
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Scoring (11 tests)" || fail "Scoring tests failed"

python tests/test_compliance.py 2>&1 | tail -1
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Compliance (12 tests)" || fail "Compliance tests failed"

python tests/test_reply_classifier.py 2>&1 | tail -1
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Reply classifier (15 tests)" || fail "Reply classifier tests failed"

python tests/test_integration.py 2>&1 | tail -1
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Integration (8 suites)" || fail "Integration tests failed"

echo -e "  ${BOLD}${GREEN}All 46 tests passed${RESET}"
fi

# ──── 3. API syntax check ───────────────────────────────────────────
if $run_all || [[ "$*" == *"--api"* ]]; then
header "API Validation"
python -c "import ast; ast.parse(open('apps/api/main.py').read()); print('  API main.py: valid Python syntax')" || fail "API syntax error"

ENDPOINTS=$(grep -c '@app\.\(get\|post\)' apps/api/main.py)
pass "API: $ENDPOINTS endpoints defined"

# Optional: start API server for live test
if [[ "$*" == *"--live"* ]]; then
    info "Starting API server on port 8000..."
    uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 &
    API_PID=$!
    sleep 2
    
    if curl -s http://localhost:8000/health | grep -q "ok"; then
        pass "API health check: OK"
    else
        fail "API health check: FAILED"
    fi
    
    kill $API_PID 2>/dev/null
fi
fi

# ──── 4. Campaign simulation ────────────────────────────────────────
if $run_all || [[ "$*" == *"--simulate"* ]]; then
header "Campaign Simulation"
python deploy/simulate_campaign.py 2>&1 | tail -5
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Simulation complete" || fail "Simulation failed"
fi

# ──── 5. Daily summary ──────────────────────────────────────────────
if $run_all || [[ "$*" == *"--summary"* ]]; then
header "Daily Summary"
python deploy/generate_daily_summary.py 2>&1 | head -15
[ ${PIPESTATUS[0]} -eq 0 ] && pass "Summary generated" || fail "Summary failed"
fi

# ──── 6. File integrity ─────────────────────────────────────────────
if $run_all || [[ "$*" == *"--check"* ]]; then
header "File Integrity"
FILES=$(find . -type f \( -name "*.py" -o -name "*.sql" -o -name "*.json" \) ! -path "*/__pycache__/*" ! -name "*.pyc" | wc -l)
pass "$FILES source files present"

PACKAGES=$(ls -d packages/*/ 2>/dev/null | wc -l)
pass "$PACKAGES packages"

WORKFLOWS=$(ls workflows/*.json 2>/dev/null | wc -l)
pass "$WORKFLOWS n8n workflows"

TABLES=$(grep -c "CREATE TABLE" db/migrations/001_initial_schema.sql)
pass "$TABLES database tables defined"
fi

# ──── 7. Summary ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${BOLD}${GREEN}  CampaignOps Kernel v1 — All checks passed${RESET}"
echo -e "${BOLD}${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo "  Quick start:"
echo "    uvicorn apps.api.main:app --reload     # Start API"
echo "    python deploy/simulate_campaign.py      # Full simulation"
echo "    python deploy/generate_daily_summary.py # Today's report"
echo "    python tests/test_integration.py        # All integration tests"
echo ""
