"use client"

import { createContext, useContext, useState, useEffect } from "react"
import { apiFetch } from "@/lib/api"
import {
  PlanId, getPlan, getPlanCredits, getPlanLimits, PLANS,
  type BasePlanId, BASE_PLANS,
} from "@/lib/plans"

export interface Credits {
  enhancement: {
    used: number
    limit: number
    purchased: number // Extra credits purchased
  }
  criminal: {
    used: number
    limit: number
    purchased: number
  }
  dnc: {
    used: number
    limit: number
    purchased: number
  }
}

export interface Usage {
  teamMembers: {
    current: number
    limit: number
  }
  leadSources: {
    current: number
    limit: number
  }
}

export interface Subscription {
  plan: PlanId
  planName: string
  status: "active" | "trialing" | "past_due" | "canceled" | "incomplete"
  trialEndsAt: Date | null
  currentPeriodEnd: Date
  cancelAtPeriodEnd: boolean
  credits: Credits
  usage: Usage
  price: number
}

interface SubscriptionContextType {
  subscription: Subscription
  isLoading: boolean
  updateSubscription: (updates: Partial<Subscription>) => void
  cancelSubscription: () => Promise<boolean>
  reactivateSubscription: () => Promise<boolean>
  refreshSubscription: () => Promise<void>
  purchaseCredits: (packageId: string) => Promise<boolean>
  changePlan: (newPlan: PlanId) => Promise<boolean>
}

function getDefaultSubscription(): Subscription {
  const plan = getPlan("solo")
  const credits = getPlanCredits("solo")
  const limits = getPlanLimits("solo")

  return {
    plan: "solo", // Legacy default — new signups will get "starter"
    planName: plan.name,
    status: "active",
    trialEndsAt: null,
    currentPeriodEnd: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
    cancelAtPeriodEnd: false,
    credits: {
      enhancement: { used: 0, limit: credits.enhancement, purchased: 0 },
      criminal: { used: 0, limit: credits.criminal, purchased: 0 },
      dnc: { used: 0, limit: credits.dnc, purchased: 0 },
    },
    usage: {
      teamMembers: { current: 1, limit: limits.teamMembers },
      leadSources: { current: 0, limit: limits.leadSources },
    },
    price: plan.price,
  }
}

const SubscriptionContext = createContext<SubscriptionContextType | undefined>(undefined)

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const [subscription, setSubscription] = useState<Subscription>(getDefaultSubscription())
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchSubscription()
  }, [])

  const fetchSubscription = async () => {
    setIsLoading(true)
    try {
      const res = await apiFetch('/api/supabase/user/subscription')

      if (!res) {
        setSubscription(getDefaultSubscription())
        setIsLoading(false)
        return
      }

      const data = await res.json()

      if (data.success && data.data) {
        const subData = data.data
        const rawPlanId = subData.plan || "solo"

        // Resolve plan info — handle both new base plan IDs and legacy plan IDs
        let planName: string
        let planPrice: number
        let planCredits = { enhancement: 0, criminal: 0, dnc: 0 }
        let planLimits = { leadSources: 1, teamMembers: -1 }

        if (rawPlanId in BASE_PLANS) {
          // New modular plan (starter, growth, pro, enterprise)
          const basePlan = BASE_PLANS[rawPlanId as BasePlanId]
          planName = basePlan.name
          planPrice = basePlan.price
          planLimits = { leadSources: basePlan.platforms, teamMembers: -1 }
          // Credits come from enhancement subscription, not base plan
        } else if (rawPlanId in PLANS) {
          // Legacy bundled plan (solo, team, brokerage, enterprise)
          const legacyPlan = PLANS[rawPlanId as PlanId]
          planName = legacyPlan.name
          planPrice = legacyPlan.price
          planCredits = legacyPlan.credits
          planLimits = legacyPlan.limits
        } else {
          // Unknown plan — fall back to starter
          const fallback = BASE_PLANS.starter
          planName = fallback.name
          planPrice = fallback.price
          planLimits = { leadSources: fallback.platforms, teamMembers: -1 }
        }

        setSubscription({
          plan: rawPlanId as PlanId,
          planName,
          status: subData.status || "active",
          trialEndsAt: subData.trialEndsAt ? new Date(subData.trialEndsAt) : null,
          currentPeriodEnd: subData.currentPeriodEnd
            ? new Date(subData.currentPeriodEnd)
            : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          cancelAtPeriodEnd: subData.cancelAtPeriodEnd || false,
          credits: {
            enhancement: {
              used: subData.credits?.enhancement?.used || 0,
              limit: subData.credits?.enhancement?.limit || planCredits.enhancement,
              purchased: subData.credits?.enhancement?.purchased || 0,
            },
            criminal: {
              used: subData.credits?.criminal?.used || 0,
              limit: subData.credits?.criminal?.limit || planCredits.criminal,
              purchased: subData.credits?.criminal?.purchased || 0,
            },
            dnc: {
              used: subData.credits?.dnc?.used || 0,
              limit: subData.credits?.dnc?.limit || planCredits.dnc,
              purchased: subData.credits?.dnc?.purchased || 0,
            },
          },
          usage: {
            teamMembers: {
              current: subData.usage?.teamMembers?.current || 1,
              limit: planLimits.teamMembers === -1 ? Infinity : planLimits.teamMembers,
            },
            leadSources: {
              current: subData.usage?.leadSources?.current || 0,
              limit: planLimits.leadSources,
            },
          },
          price: planPrice,
        })
      }
    } catch (err) {
      console.error('Failed to fetch subscription:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const updateSubscription = (updates: Partial<Subscription>) => {
    setSubscription(curr => ({ ...curr, ...updates }))
  }

  const cancelSubscription = async (): Promise<boolean> => {
    try {
      const res = await apiFetch('/api/supabase/user/subscription/cancel', {
        method: 'POST',
      })
      if (!res) return false
      const data = await res.json()

      if (data.success) {
        setSubscription(curr => ({ ...curr, cancelAtPeriodEnd: true }))
        return true
      }
      return false
    } catch (err) {
      console.error('Failed to cancel subscription:', err)
      return false
    }
  }

  const reactivateSubscription = async (): Promise<boolean> => {
    try {
      const res = await apiFetch('/api/supabase/user/subscription/reactivate', {
        method: 'POST',
      })
      if (!res) return false
      const data = await res.json()

      if (data.success) {
        setSubscription(curr => ({ ...curr, cancelAtPeriodEnd: false }))
        return true
      }
      return false
    } catch (err) {
      console.error('Failed to reactivate subscription:', err)
      return false
    }
  }

  const refreshSubscription = async () => {
    await fetchSubscription()
  }

  const purchaseCredits = async (packageId: string): Promise<boolean> => {
    try {
      const res = await apiFetch('/api/supabase/user/credits/purchase', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ packageId }),
      })
      if (!res) return false
      const data = await res.json()

      if (data.success) {
        await refreshSubscription()
        return true
      }
      return false
    } catch (err) {
      console.error('Failed to purchase credits:', err)
      return false
    }
  }

  const changePlan = async (newPlan: PlanId): Promise<boolean> => {
    try {
      const res = await apiFetch('/api/supabase/user/subscription/change-plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newPlan }),
      })
      if (!res) return false
      const data = await res.json()

      if (data.success) {
        await refreshSubscription()
        return true
      }
      return false
    } catch (err) {
      console.error('Failed to change plan:', err)
      return false
    }
  }

  return (
    <SubscriptionContext.Provider
      value={{
        subscription,
        isLoading,
        updateSubscription,
        cancelSubscription,
        reactivateSubscription,
        refreshSubscription,
        purchaseCredits,
        changePlan,
      }}
    >
      {children}
    </SubscriptionContext.Provider>
  )
}

export function useSubscription() {
  const context = useContext(SubscriptionContext)
  if (context === undefined) {
    throw new Error("useSubscription must be used within a SubscriptionProvider")
  }
  return context
}
