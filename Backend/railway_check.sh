#!/bin/bash
# Railway Setup Checker - Detects existing setup and shows what's missing

set -e

echo "========================================================================"
echo "LeadSynergy - Railway Setup Checker"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}✗${NC} Railway CLI is not installed"
    echo ""
    echo "Install it with:"
    echo "  npm install -g @railway/cli"
    exit 1
fi

echo -e "${GREEN}✓${NC} Railway CLI installed"

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${RED}✗${NC} Not logged in to Railway"
    echo ""
    echo "Login with: railway login"
    exit 1
fi

WHOAMI=$(railway whoami 2>&1)
echo -e "${GREEN}✓${NC} Logged in as: $WHOAMI"
echo ""

# Check if project is linked
if ! railway status &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} No Railway project linked to this directory"
    echo ""
    echo "Link a project with:"
    echo "  railway link"
    echo ""
    exit 1
fi

PROJECT_NAME=$(railway status 2>&1 | grep -i "project" | awk '{print $2}' || echo "Unknown")
echo -e "${GREEN}✓${NC} Project linked: $PROJECT_NAME"
echo ""

echo "========================================================================"
echo "Checking Existing Services"
echo "========================================================================"
echo ""

# List all services
SERVICES=$(railway service 2>&1)

echo "Current services:"
echo "$SERVICES"
echo ""

# Check for each required service
has_web=false
has_worker=false
has_beat=false
has_redis=false

if echo "$SERVICES" | grep -qi "web"; then
    echo -e "${GREEN}✓${NC} Web service found"
    has_web=true
else
    echo -e "${RED}✗${NC} Web service missing"
fi

if echo "$SERVICES" | grep -qi "worker"; then
    echo -e "${GREEN}✓${NC} Worker service found"
    has_worker=true
else
    echo -e "${RED}✗${NC} Worker service missing"
fi

if echo "$SERVICES" | grep -qi "beat"; then
    echo -e "${GREEN}✓${NC} Beat service found"
    has_beat=true
else
    echo -e "${RED}✗${NC} Beat service missing"
fi

if echo "$SERVICES" | grep -qi "redis\|database"; then
    echo -e "${GREEN}✓${NC} Redis database found"
    has_redis=true
else
    echo -e "${YELLOW}⚠${NC} Redis database not detected (might exist with different name)"
fi

echo ""
echo "========================================================================"
echo "Checking Environment Variables"
echo "========================================================================"
echo ""

# Check environment variables for web service
if [ "$has_web" = true ]; then
    echo "Checking Web service variables..."
    WEB_VARS=$(railway variables --service web 2>&1)

    check_var() {
        local var_name=$1
        if echo "$WEB_VARS" | grep -q "$var_name"; then
            echo -e "${GREEN}✓${NC} $var_name is set"
            return 0
        else
            echo -e "${RED}✗${NC} $var_name is missing"
            return 1
        fi
    }

    check_var "FUB_API_KEY"
    check_var "SUPABASE_URL"
    check_var "SUPABASE_KEY"
    check_var "ANTHROPIC_API_KEY"

    if echo "$WEB_VARS" | grep -q "REDIS_URL"; then
        echo -e "${GREEN}✓${NC} REDIS_URL is set (Redis connected)"
    else
        echo -e "${YELLOW}⚠${NC} REDIS_URL not set (Redis may not be connected)"
    fi

    echo ""
fi

echo "========================================================================"
echo "Summary & Next Steps"
echo "========================================================================"
echo ""

# Determine what needs to be done
missing_services=()
[ "$has_web" = false ] && missing_services+=("web")
[ "$has_worker" = false ] && missing_services+=("worker")
[ "$has_beat" = false ] && missing_services+=("beat")
[ "$has_redis" = false ] && missing_services+=("redis")

if [ ${#missing_services[@]} -eq 0 ]; then
    echo -e "${GREEN}✓ All services are present!${NC}"
    echo ""
    echo "Your setup looks complete. To verify it's working:"
    echo ""
    echo "1. Check Worker logs:"
    echo "   railway logs --service worker"
    echo ""
    echo "2. Check Beat logs:"
    echo "   railway logs --service beat"
    echo ""
    echo "3. Check Web logs:"
    echo "   railway logs --service web"
    echo ""
    echo "4. Test with a new lead in FUB"
else
    echo -e "${YELLOW}Missing services:${NC}"
    for service in "${missing_services[@]}"; do
        echo "  - $service"
    done
    echo ""
    echo "To add missing services:"
    echo ""

    if [ "$has_redis" = false ]; then
        echo "Add Redis:"
        echo "  railway add --plugin redis"
        echo ""
    fi

    if [ "$has_worker" = false ]; then
        echo "Add Worker service:"
        echo "  railway service create worker"
        echo "  railway variables --service worker set START_COMMAND=\"celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=4\""
        echo ""
    fi

    if [ "$has_beat" = false ]; then
        echo "Add Beat service:"
        echo "  railway service create beat"
        echo "  railway variables --service beat set START_COMMAND=\"celery -A app.scheduler.celery_app beat --loglevel=info\""
        echo ""
    fi
fi

echo "========================================================================"
echo ""
echo "Want to complete the setup automatically?"
echo "Run: ./railway_complete_setup.sh"
echo ""
echo "========================================================================"
