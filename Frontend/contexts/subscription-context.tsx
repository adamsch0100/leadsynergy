"use client"

import { createContext, useContext, useState, useEffect } from "react"
import { createClient } from "@/lib/supabase/client"
import { PlanId, getPlan, getPlanCredits, getPlanLimits, PLANS } from "@/lib/plans"

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
    plan: "solo",
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
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()

      if (!user) {
        setSubscription(getDefaultSubscription())
        setIsLoading(false)
        return
      }

      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription`, {
        headers: { 'X-User-ID': user.id }
      })

      const data = await res.json()

      if (data.success && data.data) {
        const subData = data.data
        const planId = (subData.plan || "solo") as PlanId
        const plan = PLANS[planId] || PLANS.solo
        const planCredits = plan.credits
        const planLimits = plan.limits

        setSubscription({
          plan: planId,
          planName: plan.name,
          status: subData.status || "active",
          trialEndsAt: subData.trialEndsAt ? new Date(subData.trialEndsAt) : null,
          currentPeriodEnd: subData.currentPeriodEnd
            ? new Date(subData.currentPeriodEnd)
            : new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
          cancelAtPeriodEnd: subData.cancelAtPeriodEnd || false,
          credits: {
            enhancement: {
              used: subData.credits?.enhancement?.used || 0,
              limit: planCredits.enhancement,
              purchased: subData.credits?.enhancement?.purchased || 0,
            },
            criminal: {
              used: subData.credits?.criminal?.used || 0,
              limit: planCredits.criminal,
              purchased: subData.credits?.criminal?.purchased || 0,
            },
            dnc: {
              used: subData.credits?.dnc?.used || 0,
              limit: planCredits.dnc,
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
          price: plan.price,
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
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return false

      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription/cancel`, {
        method: 'POST',
        headers: { 'X-User-ID': user.id }
      })
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
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return false

      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription/reactivate`, {
        method: 'POST',
        headers: { 'X-User-ID': user.id }
      })
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
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return false

      const res = await fetch(`${API_BASE_URL}/api/supabase/user/credits/purchase`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ packageId })
      })
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
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return false

      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription/change-plan`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ newPlan })
      })
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
