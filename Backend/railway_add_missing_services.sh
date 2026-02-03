#!/bin/bash
# Add missing services to existing Railway deployment

set -e

echo "========================================================================"
echo "Adding Missing Services to Railway"
echo "========================================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check Railway CLI
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not installed. Install with:"
    echo "  npm install -g @railway/cli"
    exit 1
fi

echo "This will add the missing Celery services to your existing Railway project."
echo ""
read -p "Press Enter to continue..."
echo ""

# Make sure we're in the right directory
cd "$(dirname "$0")"

echo "========================================================================"
echo "Step 1: Adding Redis Database"
echo "========================================================================"
echo ""

echo "Adding Redis (Celery needs this as message broker)..."
railway add --database redis

echo -e "${GREEN}✓${NC} Redis added"
echo ""

echo "========================================================================"
echo "Step 2: Creating Worker Service"
echo "========================================================================"
echo ""

# Link to Backend service to get the correct repo
echo "Creating Worker service from LeadSynergy Backend repo..."

# Note: Railway CLI will automatically detect the repo from the linked project
railway service create worker

echo "Setting Worker start command..."
railway run --service worker railway variables set START_COMMAND="celery -A app.scheduler.celery_app worker --loglevel=info --concurrency=4"

echo -e "${GREEN}✓${NC} Worker service created"
echo ""

echo "========================================================================"
echo "Step 3: Creating Beat Service"
echo "========================================================================"
echo ""

echo "Creating Beat service..."
railway service create beat

echo "Setting Beat start command..."
railway run --service beat railway variables set START_COMMAND="celery -A app.scheduler.celery_app beat --loglevel=info"

echo -e "${GREEN}✓${NC} Beat service created"
echo ""

echo "========================================================================"
echo "Step 4: Copying Environment Variables"
echo "========================================================================"
echo ""

echo "Copying environment variables from Backend to Worker and Beat..."
echo ""
echo -e "${YELLOW}Note:${NC} You'll need to copy these manually in Railway dashboard:"
echo ""
echo "1. Go to: https://railway.app/project/YOUR_PROJECT"
echo "2. Click on 'LeadSynergy Backend' service"
echo "3. Go to 'Variables' tab"
echo "4. Copy these variables:"
echo "   - FUB_API_KEY"
echo "   - SUPABASE_URL"
echo "   - SUPABASE_KEY"
echo "   - ANTHROPIC_API_KEY"
echo "   - OPENROUTER_API_KEY (if set)"
echo "   - OPENAI_API_KEY (if set)"
echo ""
echo "5. Go to 'Worker' service → Variables → Paste each variable"
echo "6. Go to 'Beat' service → Variables → Paste each variable"
echo ""
echo "IMPORTANT: REDIS_URL will be automatically set when you deploy"
echo ""

read -p "Press Enter when you've copied the environment variables..."
echo ""

echo "========================================================================"
echo "Step 5: Deploying Services"
echo "========================================================================"
echo ""

echo "Deploying Worker service..."
railway up --service worker

echo ""
echo "Deploying Beat service..."
railway up --service beat

echo ""
echo -e "${GREEN}✓${NC} Services deployed!"
echo ""

echo "========================================================================"
echo "Setup Complete!"
echo "========================================================================"
echo ""
echo "Your AI agent should now be fully operational!"
echo ""
echo "Next steps:"
echo "1. Check Worker logs: railway logs --service worker"
echo "2. Check Beat logs: railway logs --service beat"
echo "3. Test with a new lead in FUB"
echo ""
echo "Worker logs should show:"
echo "  [tasks]"
echo "    . app.scheduler.ai_tasks.send_scheduled_message"
echo "    . app.scheduler.ai_tasks.trigger_instant_ai_response"
echo "  celery@worker ready."
echo ""
echo "Beat logs should show:"
echo "  Scheduler: Sending due task process_pending_messages"
echo ""
echo "========================================================================"
