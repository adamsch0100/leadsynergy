"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Check, ExternalLink, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { SidebarWrapper } from "@/components/sidebar"
import { useSubscription } from "@/contexts/subscription-context"
import {
  BASE_PLANS,
  BASE_PLAN_ORDER,
  ENHANCEMENT_PLANS,
  ENHANCEMENT_PLAN_ORDER,
  type BasePlanId,
  type EnhancementPlanId,
} from "@/lib/plans"
import { apiFetch } from "@/lib/api"

export default function UpgradePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const defaultTab = searchParams.get("tab") === "enhancement" ? "enhancement" : "platform"
  const { subscription } = useSubscription()

  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")

  // Open Stripe Customer Portal for billing management
  const openCustomerPortal = async () => {
    setIsLoading(true)
    setError("")
    try {
      const res = await apiFetch("/api/billing/portal", { method: "POST" })
      if (!res) {
        setError("Not authenticated. Please sign in again.")
        return
      }
      const data = await res.json()
      if (data.ok && data.url) {
        window.location.href = data.url
      } else {
        setError(data.error || "Failed to open billing portal")
      }
    } catch {
      setError("Failed to connect to billing service")
    } finally {
      setIsLoading(false)
    }
  }

  // Determine the current base plan (resolve legacy plan IDs)
  const currentPlanId = subscription.plan
  const isLegacyPlan = !BASE_PLAN_ORDER.includes(currentPlanId as BasePlanId)

  return (
    <SidebarWrapper>
      <div className="flex-1 p-6 space-y-6">
        {/* Header */}
        <div>
          <Button
            variant="ghost"
            onClick={() => router.push("/admin/billing")}
            className="mb-4"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Billing
          </Button>
          <h1 className="text-2xl font-bold">Change Plan</h1>
          <p className="text-muted-foreground mt-1">
            Compare plans and manage your subscription
          </p>
        </div>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue={defaultTab}>
          <TabsList>
            <TabsTrigger value="platform">Platform Plans</TabsTrigger>
            <TabsTrigger value="enhancement">Enhancement Plans</TabsTrigger>
          </TabsList>

          {/* Platform Plans Tab */}
          <TabsContent value="platform" className="space-y-6">
            <p className="text-sm text-muted-foreground">
              Platform plans determine how many lead source connections you can use.
              All plans include unlimited team members.
            </p>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
              {BASE_PLAN_ORDER.map((planId) => {
                const plan = BASE_PLANS[planId]
                const isCurrent = currentPlanId === planId
                const isEnterprise = plan.contactSales

                return (
                  <Card
                    key={planId}
                    className={`relative ${
                      isCurrent ? "border-primary ring-2 ring-primary/20" : ""
                    } ${plan.popular ? "border-primary/50" : ""}`}
                  >
                    {plan.popular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <Badge className="bg-primary">Most Popular</Badge>
                      </div>
                    )}
                    {isCurrent && (
                      <div className="absolute -top-3 right-4">
                        <Badge variant="outline" className="bg-background">
                          Current Plan
                        </Badge>
                      </div>
                    )}

                    <CardHeader className="pb-4">
                      <CardTitle>{plan.name}</CardTitle>
                      <CardDescription>{plan.description}</CardDescription>
                    </CardHeader>

                    <CardContent className="pb-4">
                      <div className="mb-4">
                        {isEnterprise ? (
                          <span className="text-3xl font-bold">Custom</span>
                        ) : (
                          <>
                            <span className="text-3xl font-bold">
                              ${plan.price}
                            </span>
                            <span className="text-muted-foreground">/mo</span>
                          </>
                        )}
                      </div>

                      <div className="mb-4">
                        <p className="text-sm font-medium">
                          {plan.platforms === -1
                            ? "Unlimited platforms"
                            : `${plan.platforms} platform${plan.platforms > 1 ? "s" : ""}`}
                        </p>
                      </div>

                      <ul className="space-y-2">
                        {plan.features.map((feature, i) => (
                          <li key={i} className="flex items-start gap-2 text-sm">
                            <Check className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
                            {feature}
                          </li>
                        ))}
                      </ul>
                    </CardContent>

                    <CardFooter>
                      {isCurrent ? (
                        <Button className="w-full" variant="outline" disabled>
                          Current Plan
                        </Button>
                      ) : isEnterprise ? (
                        <Button
                          className="w-full"
                          variant="outline"
                          onClick={() =>
                            (window.location.href = "mailto:support@leadsynergy.com?subject=Enterprise Plan Inquiry")
                          }
                        >
                          Contact Sales
                        </Button>
                      ) : (
                        <Button
                          className="w-full"
                          onClick={openCustomerPortal}
                          disabled={isLoading}
                        >
                          {isLoading ? (
                            <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          ) : null}
                          {isCurrent ? "Current" : "Switch Plan"}
                        </Button>
                      )}
                    </CardFooter>
                  </Card>
                )
              })}
            </div>

            {isLegacyPlan && (
              <Alert>
                <AlertDescription>
                  You&apos;re on a legacy plan ({subscription.planName}). Use the button
                  below to manage your subscription and switch to one of the current plans.
                </AlertDescription>
              </Alert>
            )}
          </TabsContent>

          {/* Enhancement Plans Tab */}
          <TabsContent value="enhancement" className="space-y-6">
            <p className="text-sm text-muted-foreground">
              Enhancement plans provide monthly credits for lead data enrichment,
              criminal background checks, and DNC verification.
            </p>

            <div className="grid gap-6 md:grid-cols-3">
              {ENHANCEMENT_PLAN_ORDER.map((planId) => {
                const plan = ENHANCEMENT_PLANS[planId]

                return (
                  <Card key={planId}>
                    <CardHeader className="pb-4">
                      <CardTitle>{plan.name}</CardTitle>
                      <CardDescription>{plan.description}</CardDescription>
                    </CardHeader>

                    <CardContent className="pb-4">
                      <div className="mb-4">
                        <span className="text-3xl font-bold">
                          ${plan.price}
                        </span>
                        <span className="text-muted-foreground">/mo</span>
                      </div>

                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between py-1 border-b">
                          <span>Enhancement Credits</span>
                          <span className="font-medium">
                            {plan.credits.enhancement}
                          </span>
                        </div>
                        <div className="flex justify-between py-1 border-b">
                          <span>Criminal Searches</span>
                          <span className="font-medium">
                            {plan.credits.criminal}
                          </span>
                        </div>
                        <div className="flex justify-between py-1">
                          <span>DNC Checks</span>
                          <span className="font-medium">
                            {plan.credits.dnc}
                          </span>
                        </div>
                      </div>
                    </CardContent>

                    <CardFooter>
                      <Button
                        className="w-full"
                        onClick={openCustomerPortal}
                        disabled={isLoading}
                      >
                        {isLoading ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                        ) : null}
                        Subscribe
                      </Button>
                    </CardFooter>
                  </Card>
                )
              })}
            </div>
          </TabsContent>
        </Tabs>

        {/* Manage via Stripe Portal */}
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Manage Subscription & Payment Methods</p>
                <p className="text-sm text-muted-foreground">
                  Update your payment method, view invoices, or cancel your subscription
                  via the Stripe customer portal.
                </p>
              </div>
              <Button variant="outline" onClick={openCustomerPortal} disabled={isLoading}>
                {isLoading ? (
                  <Loader2 className="h-4 w-4 animate-spin mr-2" />
                ) : (
                  <ExternalLink className="h-4 w-4 mr-2" />
                )}
                Open Billing Portal
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </SidebarWrapper>
  )
}
