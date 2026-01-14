# LeadSynergy

**Complete Lead Management & Enrichment Platform for Real Estate Professionals**

LeadSynergy combines referral lead aggregation with lead data enrichment into one unified platform.

## Features

### Lead Aggregation (from ReferralLink)
- **5 Referral Platform Integrations**: Homelight, Redfin, Referral Exchange, Agent Pronto, My Agent Finder
- **FUB Integration**: Bi-directional sync with Follow Up Boss
- **Stage Mapping**: Map referral platform stages to FUB stages
- **Commission Tracking**: Track referral fees and commissions
- **Status Updates**: Update lead status back to referral platforms from FUB

### Lead Enrichment (from Leaddata)
- **7 Search Types**:
  - Contact Enrichment
  - Reverse Phone Search
  - Reverse Email Search
  - Criminal History Search
  - DNC (Do Not Call) Check
  - Owner Search
  - Advanced Person Search
- **FUB Embedded App**: Enrich leads directly within FUB sidebar (~400px)
- **Auto-Enhancement**: Automatically enrich new leads when they arrive
- **Credit System**: Broker/agent credit hierarchy with allocation

### Compliance
- **DNC Checking**: TCPA compliance with Do Not Call registry verification
- **FCRA Compliance**: Criminal background checks with proper disclaimers

## Architecture

```
LeadSynergy/
├── Backend/                    # Flask Python backend
│   ├── app/
│   │   ├── analytics/         # Admin/broker analytics
│   │   ├── billing/           # Credit & Stripe billing
│   │   ├── email/             # Email templates & service
│   │   ├── enrichment/        # Endato API integration
│   │   ├── fub/               # FUB embedded app & routes
│   │   ├── referral_scrapers/ # 5 platform scrapers
│   │   ├── support/           # Support ticket system
│   │   └── webhook/           # FUB & Stripe webhooks
│   ├── migrations/            # SQL migrations
│   └── main.py                # Flask entry point
│
└── Frontend/                  # Next.js React frontend
    ├── app/
    │   ├── admin/             # Admin dashboard pages
    │   ├── agent/             # Agent pages
    │   ├── pricing/           # Pricing page
    │   └── page.tsx           # Landing page
    └── components/            # React components
```

## Pricing Plans

All plans include unlimited lead syncing to FUB, bi-directional status updates, and FUB embedded app access.

| Plan | Price | Platforms | Team | Enhance | Criminal | DNC |
|------|-------|-----------|------|---------|----------|-----|
| Solo Agent | $79/mo | 3 | 1 | 25/mo | 1/mo | 50/mo |
| Team | $149/mo | All 5 | 5 | 100/mo | 3/mo | 150/mo |
| Brokerage | $299/mo | All 5 | 15 | 300/mo | 8/mo | 400/mo |
| Enterprise | Custom | All 5 | Unlimited | 1000+/mo | 25+/mo | 1500+/mo |

## Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- Redis (for Celery)
- Supabase account

### Backend Setup

```bash
cd Backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env   # Configure environment variables
python main.py
```

### Frontend Setup

```bash
cd Frontend
npm install
cp .env.local.example .env.local  # Configure environment variables
npm run dev
```

### Database Migration

Run the complete migration in Supabase SQL Editor:
```sql
-- Copy contents of Backend/migrations/COMPLETE_LEADSYNERGY_MIGRATION.sql
```

## Environment Variables

### Backend (.env)
```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key

# FUB (Follow Up Boss)
FUB_API_KEY=your_fub_api_key
FUB_EMBEDDED_APP_SECRET=your_fub_secret

# Stripe
STRIPE_SECRET_KEY=your_stripe_key
STRIPE_WEBHOOK_SECRET=your_webhook_secret

# Endato (Lead Enrichment)
ENDATO_KEY_NAME=your_endato_key_name
ENDATO_KEY_PASSWORD=your_endato_password

# Redis (for Celery)
REDIS_URL=redis://localhost:6379

# Frontend URL
FRONTEND_URL=http://localhost:3000
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## API Endpoints

### FUB Embedded App
- `GET /fub/embedded` - Serve embedded app
- `POST /fub/accept_terms` - Accept terms
- `POST /fub/manual_search` - Execute enrichment search
- `GET /fub/credits` - Get credit balance
- `GET /fub/referral/info` - Get referral platform info
- `POST /fub/referral/update-status` - Update platform status
- `POST /fub/referral/log-commission` - Log commission

### Webhooks
- `POST /stage-webhook` - FUB stage changes
- `POST /notes-created-webhook` - FUB note created
- `POST /notes-updated-webhook` - FUB note updated
- `POST /tag-webhook` - FUB tag changes
- `POST /person-created-webhook` - FUB new person (triggers auto-enhancement)
- `POST /person-updated-webhook` - FUB person updated
- `POST /webhooks/stripe/` - Stripe billing webhooks

### API
- `GET /api/enrichment/*` - Enrichment search endpoints
- `GET /api/billing/*` - Billing & credits
- `GET /api/analytics/*` - Analytics data
- `GET /api/support/*` - Support tickets

## Referral Platform Scrapers

Each scraper handles login, navigation, and status updates:

| Platform | File | Capabilities |
|----------|------|--------------|
| Homelight | `homelight/homelight_service.py` | Login, status update, lead sync |
| Redfin | `redfin/redfin_service.py` | Login, 2FA, status update |
| Referral Exchange | `referral_exchange/referral_exchange_service.py` | Login, status update |
| Agent Pronto | `agent_pronto/agent_pronto_service.py` | Magic link login, status update |
| My Agent Finder | `my_agent_finder/my_agent_finder_service.py` | Login, status update |

## Development Notes

### Running Background Tasks
```bash
# Start Celery worker
celery -A app.scheduler.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.scheduler.celery_app beat --loglevel=info
```

### Testing a Single Lead
Use scripts in `Backend/scripts/` for testing individual components.

## Support

Contact: support@leadsynergy.io

---

Built with Flask, Next.js, Supabase, and Selenium.
