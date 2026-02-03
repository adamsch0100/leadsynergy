#!/bin/bash
# Railway Automated Deployment Script for LeadSynergy AI Agent
# This script creates all 3 services (Web, Worker, Beat) + Redis in one command

set -e  # Exit on any error

echo "========================================================================"
echo "LeadSynergy - Railway Automated Deployment"
echo "========================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo -e "${RED}ERROR: Railway CLI is not installed${NC}"
    echo ""
    echo "Install it with:"
    echo "  npm install -g @railway/cli"
    echo ""
    echo "Or download from: https://railway.app/cli"
    exit 1
fi

echo -e "${GREEN}✓${NC} Railway CLI found"
echo ""

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo -e "${YELLOW}Not logged in to Railway${NC}"
    echo "Logging in..."
    railway login
fi

echo -e "${GREEN}✓${NC} Authenticated with Railway"
echo ""

# Ask for project name
read -p "Enter project name (default: leadsynergy): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-leadsynergy}

echo ""
echo "========================================================================"
echo "Creating Railway Project: $PROJECT_NAME"
echo "========================================================================"
echo ""

# Create new project or link existing
read -p "Create new project? (y/n, default: y): " CREATE_NEW
CREATE_NEW=${CREATE_NEW:-y}

if [[ "$CREATE_NEW" == "y" ]]; then
    railway init --name "$PROJECT_NAME"
else
    railway link
fi

echo -e "${GREEN}✓${NC} Project linked"
echo ""

# Get current directory
BACKEND_DIR=$(pwd)

echo "========================================================================"
echo "Step 1: Adding Redis Database"
echo "========================================================================"
echo ""

railway add --plugin redis

echo -e "${GREEN}✓${NC} Redis database added"
echo ""

echo "========================================================================"
echo "Step 2: Creating Web Service (Flask API)"
echo "========================================================================"
echo ""

# Create service for Web
railway service create web

# Set start command for web service
railway variables --service web set START_COMMAND="gunicorn main:app --workers 4 --bind 0.0.0.0:\$PORT --timeout 120"
railway variables --service web set RAILWAY_SERVICE_TYPE="web"

echo -e "${GREEN}✓${NC} Web service created"
echo ""

echo "========================================================================"
echo "Step 3: Creating Worker Service (Celery Worker)"
echo "========================================================================"
echo ""

# Create service for Worker
railway service create worker

# Set start command for worker service
railway variables --service worker set START_COMMAND="celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=4"
railway variables --service worker set RAILWAY_SERVICE_TYPE="worker"

echo -e "${GREEN}✓${NC} Worker service created"
echo ""

echo "========================================================================"
echo "Step 4: Creating Beat Service (Celery Beat)"
echo "========================================================================"
echo ""

# Create service for Beat
railway service create beat

# Set start command for beat service
railway variables --service beat set START_COMMAND="celery -A app.scheduler.celery_app beat --loglevel=info"
railway variables --service beat set RAILWAY_SERVICE_TYPE="beat"

echo -e "${GREEN}✓${NC} Beat service created"
echo ""

echo "========================================================================"
echo "Step 5: Setting Environment Variables"
echo "========================================================================"
echo ""

echo "Now we need to set your environment variables."
echo "These will be shared across all 3 services."
echo ""

# Function to prompt for env var
set_env_var() {
    local var_name=$1
    local var_description=$2
    local is_required=$3

    if [[ "$is_required" == "true" ]]; then
        while [[ -z "${!var_name}" ]]; do
            read -p "$var_description (required): " value
            if [[ -n "$value" ]]; then
                railway variables --service web set "$var_name=$value"
                railway variables --service worker set "$var_name=$value"
                railway variables --service beat set "$var_name=$value"
                echo -e "${GREEN}✓${NC} $var_name set"
            else
                echo -e "${RED}This variable is required${NC}"
            fi
        done
    else
        read -p "$var_description (optional, press Enter to skip): " value
        if [[ -n "$value" ]]; then
            railway variables --service web set "$var_name=$value"
            railway variables --service worker set "$var_name=$value"
            railway variables --service beat set "$var_name=$value"
            echo -e "${GREEN}✓${NC} $var_name set"
        fi
    fi
}

echo "Required Variables:"
echo "-------------------"
set_env_var "FUB_API_KEY" "FUB API Key" "true"
set_env_var "SUPABASE_URL" "Supabase URL" "true"
set_env_var "SUPABASE_KEY" "Supabase Key" "true"
set_env_var "ANTHROPIC_API_KEY" "Anthropic API Key (for Claude)" "true"

echo ""
echo "Optional Variables:"
echo "-------------------"
set_env_var "OPENROUTER_API_KEY" "OpenRouter API Key" "false"
set_env_var "OPENAI_API_KEY" "OpenAI API Key" "false"
set_env_var "FRONTEND_URL" "Frontend URL (for CORS)" "false"
set_env_var "SENTRY_DSN" "Sentry DSN (for error tracking)" "false"

echo ""
echo -e "${GREEN}✓${NC} Environment variables configured"
echo ""

echo "========================================================================"
echo "Step 6: Deploying Services"
echo "========================================================================"
echo ""

echo "Deploying Web service..."
railway up --service web

echo "Deploying Worker service..."
railway up --service worker

echo "Deploying Beat service..."
railway up --service beat

echo ""
echo -e "${GREEN}✓${NC} All services deployed!"
echo ""

echo "========================================================================"
echo "Deployment Complete!"
echo "========================================================================"
echo ""
echo "Your LeadSynergy AI Agent is now live on Railway!"
echo ""
echo "Next steps:"
echo "1. Check deployment logs: railway logs --service web"
echo "2. View your project: railway open"
echo "3. Test with a new lead in FUB (should get SMS within 60 seconds)"
echo ""
echo "Service URLs:"
echo "  Dashboard: https://railway.app/project/$PROJECT_NAME"
echo "  Web API: (check Railway dashboard for the public URL)"
echo ""
echo "To view logs:"
echo "  Web:    railway logs --service web"
echo "  Worker: railway logs --service worker"
echo "  Beat:   railway logs --service beat"
echo ""
echo "========================================================================"
