/**
 * LeadSynergy Modular Pricing Configuration
 * Single source of truth for all pricing
 *
 * STRUCTURE:
 * 1. Base Platform Subscription - Lead source syncing (based on # of platforms)
 * 2. Enhancement Subscription - Monthly credits for data enrichment
 * 3. Credit Add-ons - One-time purchases (never expire)
 * 4. Future Add-ons - AI features, etc.
 *
 * NO TEAM MEMBER LIMITS - All subscriptions shared across organization
 */

// ===========================================
// BASE PLATFORM SUBSCRIPTIONS
// Lead source syncing to FUB
// ===========================================

export type BasePlanId = "starter" | "growth" | "pro" | "enterprise"

export interface BasePlan {
  id: BasePlanId
  name: string
  price: number
  priceDisplay: string
  interval: string
  platforms: number // -1 = unlimited/custom
  description: string
  features: string[]
  popular?: boolean
  contactSales?: boolean
  stripePriceId?: string
}

export const BASE_PLANS: Record<BasePlanId, BasePlan> = {
  starter: {
    id: "starter",
    name: "Starter",
    price: 29.99,
    priceDisplay: "$29.99",
    interval: "per month",
    platforms: 1,
    description: "Perfect for agents starting with one referral platform",
    features: [
      "1 lead source connection",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Stage mapping",
      "FUB embedded app",
      "Email support",
      "Unlimited team members",
    ],
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER,
  },
  growth: {
    id: "growth",
    name: "Growth",
    price: 69.99,
    priceDisplay: "$69.99",
    interval: "per month",
    platforms: 3,
    description: "For agents managing multiple referral sources",
    features: [
      "3 lead source connections",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Custom stage mapping",
      "Commission tracking",
      "FUB embedded app",
      "Priority support",
      "Unlimited team members",
    ],
    popular: true,
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_GROWTH,
  },
  pro: {
    id: "pro",
    name: "Pro",
    price: 119.99,
    priceDisplay: "$119.99",
    interval: "per month",
    platforms: 5,
    description: "For teams using all major referral platforms",
    features: [
      "5 lead source connections",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Advanced stage mapping",
      "Advanced commission tracking",
      "Team analytics dashboard",
      "FUB embedded app",
      "Priority support",
      "Unlimited team members",
    ],
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO,
  },
  enterprise: {
    id: "enterprise",
    name: "Enterprise",
    price: 0,
    priceDisplay: "Custom",
    interval: "",
    platforms: -1,
    description: "Custom solutions for large brokerages",
    features: [
      "Unlimited lead sources",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Custom stage mapping",
      "Advanced commission tracking",
      "Advanced analytics & reporting",
      "API access",
      "Dedicated account manager",
      "Custom integrations",
      "Unlimited team members",
    ],
    contactSales: true,
  },
}

export const BASE_PLAN_ORDER: BasePlanId[] = ["starter", "growth", "pro", "enterprise"]

// ===========================================
// ENHANCEMENT SUBSCRIPTIONS
// Monthly credits for data enrichment
// Target: 55-60% margin
// Cost basis: Enhancement $0.18/ea, Criminal $2.00/ea, DNC $0.025/ea
// ===========================================

export type EnhancementPlanId = "enhance-starter" | "enhance-growth" | "enhance-pro"

export interface EnhancementCredits {
  enhancement: number
  criminal: number
  dnc: number
}

export interface EnhancementPlan {
  id: EnhancementPlanId
  name: string
  price: number
  priceDisplay: string
  interval: string
  credits: EnhancementCredits
  description: string
  costBreakdown: string // For internal reference
  margin: string
  stripePriceId?: string
}

export const ENHANCEMENT_PLANS: Record<EnhancementPlanId, EnhancementPlan> = {
  "enhance-starter": {
    id: "enhance-starter",
    name: "Enhancement Starter",
    price: 29,
    priceDisplay: "$29",
    interval: "per month",
    credits: {
      enhancement: 50,  // Cost: $9
      criminal: 1,      // Cost: $2
      dnc: 50,          // Cost: $1.25
    },
    description: "Basic enrichment for casual users",
    costBreakdown: "$9 + $2 + $1.25 = $12.25",
    margin: "58%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCE_STARTER,
  },
  "enhance-growth": {
    id: "enhance-growth",
    name: "Enhancement Growth",
    price: 59,
    priceDisplay: "$59",
    interval: "per month",
    credits: {
      enhancement: 100, // Cost: $18
      criminal: 2,      // Cost: $4
      dnc: 100,         // Cost: $2.50
    },
    description: "Popular choice for active agents",
    costBreakdown: "$18 + $4 + $2.50 = $24.50",
    margin: "58%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCE_GROWTH,
  },
  "enhance-pro": {
    id: "enhance-pro",
    name: "Enhancement Pro",
    price: 99,
    priceDisplay: "$99",
    interval: "per month",
    credits: {
      enhancement: 175, // Cost: $31.50
      criminal: 3,      // Cost: $6
      dnc: 150,         // Cost: $3.75
    },
    description: "Maximum value for high-volume teams",
    costBreakdown: "$31.50 + $6 + $3.75 = $41.25",
    margin: "58%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCE_PRO,
  },
}

export const ENHANCEMENT_PLAN_ORDER: EnhancementPlanId[] = [
  "enhance-starter",
  "enhance-growth",
  "enhance-pro",
]

// ===========================================
// CREDIT ADD-ON PACKAGES
// One-time purchases - NEVER EXPIRE
// Target: 75% margin
// ===========================================

export type CreditType = "enhancement" | "criminal" | "dnc"

export interface CreditPackage {
  id: string
  name: string
  type: CreditType
  amount: number
  price: number
  priceDisplay: string
  description: string
  costBasis: string
  margin: string
  stripePriceId?: string
}

export const CREDIT_PACKAGES: CreditPackage[] = [
  // Enhancement: $0.18 cost → $0.70/ea = 74% margin
  {
    id: "enhancement-50",
    name: "50 Enhancement Credits",
    type: "enhancement",
    amount: 50,
    price: 35,
    priceDisplay: "$35",
    description: "Find missing phone numbers, emails, and addresses",
    costBasis: "$9 cost",
    margin: "74%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCEMENT_50,
  },
  {
    id: "enhancement-100",
    name: "100 Enhancement Credits",
    type: "enhancement",
    amount: 100,
    price: 70,
    priceDisplay: "$70",
    description: "Best value for enhancement credits",
    costBasis: "$18 cost",
    margin: "74%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCEMENT_100,
  },
  {
    id: "enhancement-250",
    name: "250 Enhancement Credits",
    type: "enhancement",
    amount: 250,
    price: 175,
    priceDisplay: "$175",
    description: "Bulk enhancement pack",
    costBasis: "$45 cost",
    margin: "74%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENHANCEMENT_250,
  },

  // Criminal: $2.00 cost → $8/ea = 75% margin
  {
    id: "criminal-5",
    name: "5 Criminal Searches",
    type: "criminal",
    amount: 5,
    price: 40,
    priceDisplay: "$40",
    description: "FCRA-compliant background checks",
    costBasis: "$10 cost",
    margin: "75%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_CRIMINAL_5,
  },
  {
    id: "criminal-10",
    name: "10 Criminal Searches",
    type: "criminal",
    amount: 10,
    price: 75,
    priceDisplay: "$75",
    description: "Best value for criminal searches",
    costBasis: "$20 cost",
    margin: "73%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_CRIMINAL_10,
  },

  // DNC: $0.025 cost → $0.10/ea = 75% margin
  {
    id: "dnc-200",
    name: "200 DNC Checks",
    type: "dnc",
    amount: 200,
    price: 20,
    priceDisplay: "$20",
    description: "Do Not Call registry verification",
    costBasis: "$5 cost",
    margin: "75%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_DNC_200,
  },
  {
    id: "dnc-500",
    name: "500 DNC Checks",
    type: "dnc",
    amount: 500,
    price: 50,
    priceDisplay: "$50",
    description: "Best value for DNC checks",
    costBasis: "$12.50 cost",
    margin: "75%",
    stripePriceId: process.env.NEXT_PUBLIC_STRIPE_PRICE_DNC_500,
  },
]

// ===========================================
// FUTURE ADD-ONS (Coming Soon)
// FUB API-based features
// ===========================================

export interface FutureAddOn {
  id: string
  name: string
  description: string
  priceEstimate: string
  features: string[]
  status: "coming_soon" | "beta" | "available"
}

export const FUTURE_ADDONS: FutureAddOn[] = [
  {
    id: "ai-text-responder",
    name: "AI Text Responder",
    description: "Automated SMS responses using AI with FUB texting integration",
    priceEstimate: "$29-49/mo",
    features: [
      "AI-powered lead qualification via text",
      "Automatic appointment scheduling",
      "Smart follow-up sequences",
      "Customizable response templates",
      "Conversation analytics",
    ],
    status: "coming_soon",
  },
  {
    id: "ai-email-sequences",
    name: "AI Email Sequences",
    description: "Intelligent email drip campaigns through FUB email integration",
    priceEstimate: "$19-39/mo",
    features: [
      "AI-generated email content",
      "Behavioral trigger sequences",
      "A/B testing automation",
      "Open/click optimization",
      "CRM-synced personalization",
    ],
    status: "coming_soon",
  },
  {
    id: "smart-lead-scoring",
    name: "Smart Lead Scoring",
    description: "AI-powered lead scoring based on behavior and enrichment data",
    priceEstimate: "$19-29/mo",
    features: [
      "Predictive conversion scoring",
      "Engagement tracking",
      "Auto-prioritization in FUB",
      "Score-based routing",
      "Historical pattern analysis",
    ],
    status: "coming_soon",
  },
  {
    id: "voice-ai-assistant",
    name: "Voice AI Assistant",
    description: "AI voice agent for lead qualification calls",
    priceEstimate: "$49-99/mo",
    features: [
      "Inbound call handling",
      "Outbound qualification calls",
      "Natural conversation flow",
      "Call recording & transcription",
      "FUB activity logging",
    ],
    status: "coming_soon",
  },
]

// ===========================================
// LEGACY SUPPORT
// Keep old types for backward compatibility during migration
// ===========================================

export type PlanId = "solo" | "team" | "brokerage" | "enterprise"

export interface PlanCredits {
  enhancement: number
  criminal: number
  dnc: number
}

export interface PlanLimits {
  leadSources: number
  teamMembers: number
}

export interface Plan {
  id: PlanId
  name: string
  price: number
  priceDisplay: string
  interval: string
  description: string
  highlights: string[]
  credits: PlanCredits
  limits: PlanLimits
  features: string[]
  popular?: boolean
  stripePriceId?: string
}

// Legacy plans mapped to new structure for backward compatibility
export const PLANS: Record<PlanId, Plan> = {
  solo: {
    id: "solo",
    name: "Solo Agent",
    price: 49.99,
    priceDisplay: "$49.99",
    interval: "per month",
    description: "For individual agents managing referral leads",
    highlights: [
      "3 referral platform connections",
      "Unlimited lead syncing to FUB",
      "Status updates back to platforms",
    ],
    credits: {
      enhancement: 50,
      criminal: 2,
      dnc: 100,
    },
    limits: {
      leadSources: 3,
      teamMembers: -1, // Unlimited
    },
    features: [
      "Connect 3 referral platforms",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Stage mapping",
      "50 enhancement credits/month",
      "2 criminal searches/month",
      "100 DNC checks/month",
      "FUB embedded app",
      "Email support",
    ],
  },
  team: {
    id: "team",
    name: "Team",
    price: 89.99,
    priceDisplay: "$89.99",
    interval: "per month",
    description: "For small teams with multiple agents",
    highlights: [
      "All 5 referral platforms",
      "Unlimited team members",
      "Commission tracking",
    ],
    credits: {
      enhancement: 100,
      criminal: 3,
      dnc: 200,
    },
    limits: {
      leadSources: 5,
      teamMembers: -1, // Unlimited
    },
    features: [
      "All 5 referral platforms",
      "Unlimited team members",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Custom stage mapping",
      "Commission tracking",
      "100 enhancement credits/month",
      "3 criminal searches/month",
      "200 DNC checks/month",
      "Auto-enhancement on new leads",
      "Priority support",
    ],
    popular: true,
  },
  brokerage: {
    id: "brokerage",
    name: "Brokerage",
    price: 164.99,
    priceDisplay: "$164.99",
    interval: "per month",
    description: "For brokerages managing agent teams",
    highlights: [
      "Unlimited agents",
      "Credit allocation",
      "Team analytics",
    ],
    credits: {
      enhancement: 200,
      criminal: 5,
      dnc: 300,
    },
    limits: {
      leadSources: 7,
      teamMembers: -1, // Unlimited
    },
    features: [
      "7 lead source connections",
      "Unlimited team members",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Custom stage mapping",
      "Advanced commission tracking",
      "200 enhancement credits/month",
      "5 criminal searches/month",
      "300 DNC checks/month",
      "Auto-enhancement on new leads",
      "Credit allocation to agents",
      "Team analytics dashboard",
      "Priority support",
    ],
  },
  enterprise: {
    id: "enterprise",
    name: "Enterprise",
    price: 349.99,
    priceDisplay: "$349.99",
    interval: "per month",
    description: "For large brokerages with custom needs",
    highlights: [
      "Unlimited agents",
      "API access",
      "Dedicated support",
    ],
    credits: {
      enhancement: 500,
      criminal: 10,
      dnc: 500,
    },
    limits: {
      leadSources: 10,
      teamMembers: -1, // Unlimited
    },
    features: [
      "All referral platforms",
      "Unlimited team members",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Custom stage mapping",
      "Advanced commission tracking",
      "500 enhancement credits/month",
      "10 criminal searches/month",
      "500 DNC checks/month",
      "Auto-enhancement on new leads",
      "Credit allocation to agents",
      "Advanced analytics & reporting",
      "API access",
      "Dedicated account manager",
      "Custom integrations",
    ],
  },
}

export const PLAN_ORDER: PlanId[] = ["solo", "team", "brokerage", "enterprise"]

// Additional team member pricing (legacy - now unlimited team members)
export const ADDITIONAL_TEAM_MEMBER_PRICE = 15 // per month (legacy)

// ===========================================
// HELPER FUNCTIONS
// ===========================================

// Base plan helpers
export function getBasePlan(planId: BasePlanId): BasePlan {
  return BASE_PLANS[planId]
}

export function getBasePlanPlatforms(planId: BasePlanId): number {
  return BASE_PLANS[planId].platforms
}

// Enhancement plan helpers
export function getEnhancementPlan(planId: EnhancementPlanId): EnhancementPlan {
  return ENHANCEMENT_PLANS[planId]
}

export function getEnhancementCredits(planId: EnhancementPlanId): EnhancementCredits {
  return ENHANCEMENT_PLANS[planId].credits
}

// Credit package helpers
export function getCreditPackagesByType(type: CreditType): CreditPackage[] {
  return CREDIT_PACKAGES.filter(pkg => pkg.type === type)
}

// Legacy helpers (keep for backward compatibility)
export function getPlan(planId: PlanId): Plan {
  return PLANS[planId]
}

export function getPlanLimits(planId: PlanId): PlanLimits {
  return PLANS[planId].limits
}

export function getPlanCredits(planId: PlanId): PlanCredits {
  return PLANS[planId].credits
}

export function canUpgrade(currentPlan: PlanId, targetPlan: PlanId): boolean {
  const currentIndex = PLAN_ORDER.indexOf(currentPlan)
  const targetIndex = PLAN_ORDER.indexOf(targetPlan)
  return targetIndex > currentIndex
}

export function canDowngrade(currentPlan: PlanId, targetPlan: PlanId): boolean {
  const currentIndex = PLAN_ORDER.indexOf(currentPlan)
  const targetIndex = PLAN_ORDER.indexOf(targetPlan)
  return targetIndex < currentIndex
}
