-- ============================================================================
-- LEADDATA INTEGRATION MIGRATION
-- ============================================================================
-- This migration adds all tables and columns needed to integrate Leaddata
-- features into ReferralLink, including:
-- - Credit system (bundles, transactions)
-- - Enrichment lookup history
-- - Support ticket system
-- - User extensions for credits and roles
-- ============================================================================

-- ============================================================================
-- 1. CREDIT BUNDLES TABLE
-- Defines purchasable credit packages (subscriptions and add-ons)
-- ============================================================================
CREATE TABLE IF NOT EXISTS credit_bundles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,  -- Price in cents
    enhancement_credits INTEGER DEFAULT 0,
    criminal_credits INTEGER DEFAULT 0,
    dnc_credits INTEGER DEFAULT 0,
    stripe_price_id VARCHAR(100),
    bundle_type VARCHAR(20) DEFAULT 'addon',  -- 'addon' or 'subscription'
    is_active BOOLEAN DEFAULT TRUE,
    is_test BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_credit_bundles_stripe_price_id ON credit_bundles(stripe_price_id);
CREATE INDEX IF NOT EXISTS idx_credit_bundles_bundle_type ON credit_bundles(bundle_type);
CREATE INDEX IF NOT EXISTS idx_credit_bundles_active ON credit_bundles(is_active) WHERE is_active = TRUE;

-- ============================================================================
-- 2. CREDIT TRANSACTIONS TABLE
-- Audit trail for all credit movements (usage, purchases, allocations)
-- ============================================================================
CREATE TABLE IF NOT EXISTS credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    broker_id UUID REFERENCES users(id) ON DELETE SET NULL,  -- If agent used broker's shared pool
    bundle_id INTEGER REFERENCES credit_bundles(id) ON DELETE SET NULL,
    transaction_type VARCHAR(50) NOT NULL,  -- 'usage', 'purchase', 'subscription', 'allocation', 'refund'
    enhancement_credits INTEGER DEFAULT 0,
    criminal_credits INTEGER DEFAULT 0,
    dnc_credits INTEGER DEFAULT 0,
    amount INTEGER DEFAULT 0,  -- Amount in cents (for purchases)
    currency VARCHAR(3) DEFAULT 'USD',
    credit_source VARCHAR(50),  -- 'broker_plan', 'broker_bundle', 'agent_allocated', etc.
    description TEXT,
    status VARCHAR(50) DEFAULT 'completed',  -- 'pending', 'completed', 'failed', 'refunded'
    stripe_charge_id VARCHAR(255),
    stripe_session_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_broker_id ON credit_transactions(broker_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at);

-- ============================================================================
-- 3. LOOKUP HISTORY TABLE
-- Tracks all enrichment searches (for audit and analytics)
-- ============================================================================
CREATE TABLE IF NOT EXISTS lookup_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    search_type VARCHAR(50) NOT NULL,  -- 'contact_enrichment', 'reverse_phone', 'criminal', 'dnc', etc.
    criteria JSONB,  -- Search parameters used
    result JSONB,  -- Search results (may be truncated for large results)
    success BOOLEAN DEFAULT FALSE,
    message TEXT,  -- Error message if failed
    usage_type VARCHAR(50),  -- Credit type used
    lead_id UUID REFERENCES leads(id) ON DELETE SET NULL,  -- Optional link to lead
    fub_person_id VARCHAR(255),  -- FUB person ID if searched from FUB embedded app
    billing_period_start TIMESTAMPTZ,
    billing_period_end TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_lookup_history_user_id ON lookup_history(user_id);
CREATE INDEX IF NOT EXISTS idx_lookup_history_search_type ON lookup_history(search_type);
CREATE INDEX IF NOT EXISTS idx_lookup_history_created_at ON lookup_history(created_at);
CREATE INDEX IF NOT EXISTS idx_lookup_history_lead_id ON lookup_history(lead_id);

-- ============================================================================
-- 4. SUPPORT TICKETS TABLE
-- Customer support ticket management
-- ============================================================================
CREATE TABLE IF NOT EXISTS support_tickets (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    subject VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'open',  -- 'open', 'in_progress', 'waiting', 'closed'
    priority VARCHAR(20) DEFAULT 'normal',  -- 'low', 'normal', 'high', 'urgent'
    category VARCHAR(50),  -- 'billing', 'technical', 'feature_request', 'account', 'other'
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_support_tickets_user_id ON support_tickets(user_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON support_tickets(priority);
CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned_to ON support_tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_support_tickets_created_at ON support_tickets(created_at);

-- ============================================================================
-- 5. TICKET NOTES TABLE
-- Notes/comments on support tickets (for back-and-forth communication)
-- ============================================================================
CREATE TABLE IF NOT EXISTS ticket_notes (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER REFERENCES support_tickets(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    content TEXT NOT NULL,
    is_internal BOOLEAN DEFAULT FALSE,  -- Internal notes not visible to user
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_ticket_notes_ticket_id ON ticket_notes(ticket_id);
CREATE INDEX IF NOT EXISTS idx_ticket_notes_user_id ON ticket_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_ticket_notes_created_at ON ticket_notes(created_at);

-- ============================================================================
-- 6. EXTEND USERS TABLE
-- Add credit system and role fields to existing users table
-- ============================================================================

-- User type and hierarchy
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT 'agent';  -- 'admin', 'broker', 'agent'
ALTER TABLE users ADD COLUMN IF NOT EXISTS broker_id UUID REFERENCES users(id) ON DELETE SET NULL;

-- Subscription plan credits (reset each billing cycle)
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_enhancement_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_criminal_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS plan_dnc_credits INTEGER DEFAULT 0;

-- Bundle credits (purchased add-ons, accumulate)
ALTER TABLE users ADD COLUMN IF NOT EXISTS bundle_enhancement_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bundle_criminal_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS bundle_dnc_credits INTEGER DEFAULT 0;

-- Allocated credits (from broker to agent)
ALTER TABLE users ADD COLUMN IF NOT EXISTS allocated_enhancement_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS allocated_criminal_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS allocated_dnc_credits INTEGER DEFAULT 0;

-- Personal credits (for brokers who purchase personally)
ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_enhancement_credits INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_criminal_credits INTEGER DEFAULT 0;

-- Credit allocation settings
ALTER TABLE users ADD COLUMN IF NOT EXISTS credit_allocation_type VARCHAR(20) DEFAULT 'shared';  -- 'shared' or 'restricted'

-- Usage counters
ALTER TABLE users ADD COLUMN IF NOT EXISTS enhancement_count INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS criminal_search_count INTEGER DEFAULT 0;

-- Auto-enhancement settings
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_phone BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_email BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_enhance_credit_limit INTEGER DEFAULT 10;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_phone_to_fub_on_manual_enhance BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_add_email_to_fub_on_manual_enhance BOOLEAN DEFAULT FALSE;

-- Stripe fields (if not already present)
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_item_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_plan VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS billing_frequency VARCHAR(20) DEFAULT 'monthly';  -- 'monthly' or 'annually'
ALTER TABLE users ADD COLUMN IF NOT EXISTS test_mode BOOLEAN DEFAULT FALSE;

-- Admin flag
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;

-- FUB integration fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_user_id VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS fub_terms_accepted_at TIMESTAMPTZ;

-- Setup tracking
ALTER TABLE users ADD COLUMN IF NOT EXISTS needs_setup BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS temp_password_set_at TIMESTAMPTZ;

-- Indexes for new user columns
CREATE INDEX IF NOT EXISTS idx_users_user_type ON users(user_type);
CREATE INDEX IF NOT EXISTS idx_users_broker_id ON users(broker_id);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_users_is_admin ON users(is_admin) WHERE is_admin = TRUE;

-- ============================================================================
-- 7. FUB TERMS ACCEPTANCE TABLE
-- Track FUB terms acceptance (separate from user table for cleaner queries)
-- ============================================================================
CREATE TABLE IF NOT EXISTS fub_terms_acceptance (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL UNIQUE,
    accepted BOOLEAN DEFAULT FALSE,
    accepted_at TIMESTAMPTZ,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- 8. SEED INITIAL CREDIT BUNDLES (Optional - for testing)
-- ============================================================================
-- Uncomment these inserts to seed initial bundles for testing

-- Subscription Plans
-- INSERT INTO credit_bundles (name, description, price, enhancement_credits, criminal_credits, dnc_credits, stripe_price_id, bundle_type, is_test) VALUES
-- ('Essential Plan', 'Up to 60 Enhancements, 2 Criminal Searches, and 100 DNC Checks', 4999, 60, 2, 100, 'price_test_essential', 'subscription', TRUE),
-- ('Professional Plan', 'Up to 150 Enhancements, 4 Criminal Searches, and 200 DNC Checks', 8999, 150, 4, 200, 'price_test_professional', 'subscription', TRUE),
-- ('Pro Plus Plan', 'Up to 350 Enhancements, 8 Criminal Searches, and 500 DNC Checks', 16499, 350, 8, 500, 'price_test_proplus', 'subscription', TRUE),
-- ('Enterprise Plan', 'Up to 800 Enhancements, 12 Criminal Searches, and 1200 DNC Checks', 27999, 800, 12, 1200, 'price_test_enterprise', 'subscription', TRUE);

-- Add-on Bundles
-- INSERT INTO credit_bundles (name, description, price, enhancement_credits, criminal_credits, dnc_credits, stripe_price_id, bundle_type, is_test) VALUES
-- ('50 Enhancement Credits', 'One-time purchase of 50 enhancement credits', 999, 50, 0, 0, 'price_test_enh_50', 'addon', TRUE),
-- ('100 Enhancement Credits', 'One-time purchase of 100 enhancement credits', 1799, 100, 0, 0, 'price_test_enh_100', 'addon', TRUE),
-- ('5 Criminal Searches', 'One-time purchase of 5 criminal search credits', 999, 0, 5, 0, 'price_test_crim_5', 'addon', TRUE),
-- ('10 Criminal Searches', 'One-time purchase of 10 criminal search credits', 1799, 0, 10, 0, 'price_test_crim_10', 'addon', TRUE),
-- ('500 DNC Checks', 'One-time purchase of 500 DNC check credits', 1000, 0, 0, 500, 'price_test_dnc_500', 'addon', TRUE);

-- ============================================================================
-- 9. RECORD MIGRATION
-- ============================================================================
INSERT INTO schema_migrations (id, version, description)
VALUES (
    gen_random_uuid(),
    '20260108_add_leaddata_integration',
    'Add Leaddata integration tables: credit_bundles, credit_transactions, lookup_history, support_tickets, ticket_notes, and extend users table with credit/role fields'
) ON CONFLICT (version) DO NOTHING;
