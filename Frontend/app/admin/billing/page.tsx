"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  CreditCard, Plus, RefreshCw, AlertTriangle, CheckCircle, Sparkles,
  ShieldAlert, PhoneOff, Zap, Layers, MessageSquare, Mail, Brain, Phone, Clock
} from "lucide-react"
import { useSubscription } from "@/contexts/subscription-context"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"
import Link from "next/link"
import { Progress } from "@/components/ui/progress"
import {
  BASE_PLANS,
  ENHANCEMENT_PLANS,
  CREDIT_PACKAGES,
  FUTURE_ADDONS,
  type CreditPackage,
  type BasePlanId,
  type EnhancementPlanId,
} from "@/lib/plans"

interface PaymentMethod {
  id: string
  type: string
  lastFour: string
  expiryDate: string
  isDefault: boolean
}

interface BillingHistory {
  id: string
  date: string
  description: string
  amount: string
  status: "paid" | "pending" | "failed"
  invoiceUrl?: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// Group credit packages by type
const enhancementPackages = CREDIT_PACKAGES.filter(p => p.type === 'enhancement')
const criminalPackages = CREDIT_PACKAGES.filter(p => p.type === 'criminal')
const dncPackages = CREDIT_PACKAGES.filter(p => p.type === 'dnc')

// Icon mapping for future add-ons
const addOnIcons: Record<string, React.ReactNode> = {
  "ai-text-responder": <MessageSquare className="h-5 w-5" />,
  "ai-email-sequences": <Mail className="h-5 w-5" />,
  "smart-lead-scoring": <Brain className="h-5 w-5" />,
  "voice-ai-assistant": <Phone className="h-5 w-5" />,
}

export default function BillingPage() {
  const { subscription, cancelSubscription, reactivateSubscription, purchaseCredits, refreshSubscription } = useSubscription()
  const [isCancelDialogOpen, setIsCancelDialogOpen] = useState(false)
  const [isCreditPurchaseOpen, setIsCreditPurchaseOpen] = useState(false)
  const [selectedCreditPackage, setSelectedCreditPackage] = useState<CreditPackage | null>(null)
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([])
  const [billingHistory, setBillingHistory] = useState<BillingHistory[]>([])
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(false)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch billing data
  useEffect(() => {
    if (user) {
      fetchBillingData()
    }
  }, [user])

  const fetchBillingData = async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)

    try {
      const [pmRes, historyRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/supabase/user/payment-methods`, {
          headers: { 'X-User-ID': user.id }
        }),
        fetch(`${API_BASE_URL}/api/supabase/user/billing-history`, {
          headers: { 'X-User-ID': user.id }
        })
      ])

      const pmData = await pmRes.json()
      const historyData = await historyRes.json()

      if (pmData.success) {
        setPaymentMethods(pmData.data || [])
      }
      if (historyData.success) {
        setBillingHistory(historyData.data || [])
      }
    } catch (err) {
      console.error('Failed to fetch billing data:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSetDefaultCard = async (id: string) => {
    if (!user) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/user/payment-methods/${id}/default`, {
        method: 'POST',
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()

      if (data.success) {
        setPaymentMethods(methods =>
          methods.map(method => ({
            ...method,
            isDefault: method.id === id
          }))
        )
        setSuccessMessage('Default payment method updated')
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || 'Failed to update default payment method')
      }
    } catch (err) {
      setError('Failed to update default payment method')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleDeleteCard = async (id: string) => {
    if (!user) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/user/payment-methods/${id}`, {
        method: 'DELETE',
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()

      if (data.success) {
        setPaymentMethods(methods => methods.filter(method => method.id !== id))
        setSuccessMessage('Payment method deleted')
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || 'Failed to delete payment method')
      }
    } catch (err) {
      setError('Failed to delete payment method')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleCancelSubscription = async () => {
    if (!user) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription/cancel`, {
        method: 'POST',
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()

      if (data.success) {
        cancelSubscription()
        setIsCancelDialogOpen(false)
        setSuccessMessage('Subscription will be cancelled at the end of your billing period')
        setTimeout(() => setSuccessMessage(null), 5000)
      } else {
        setError(data.error || 'Failed to cancel subscription')
      }
    } catch (err) {
      setError('Failed to cancel subscription')
    } finally {
      setIsProcessing(false)
    }
  }

  const handleReactivateSubscription = async () => {
    if (!user) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/user/subscription/reactivate`, {
        method: 'POST',
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()

      if (data.success) {
        reactivateSubscription()
        setSuccessMessage('Subscription reactivated!')
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || 'Failed to reactivate subscription')
      }
    } catch (err) {
      setError('Failed to reactivate subscription')
    } finally {
      setIsProcessing(false)
    }
  }

  const handlePurchaseCredits = async () => {
    if (!user || !selectedCreditPackage) return
    setIsProcessing(true)
    setError(null)

    try {
      const success = await purchaseCredits(selectedCreditPackage.id)
      if (success) {
        setSuccessMessage(`Successfully purchased ${selectedCreditPackage.name}!`)
        setIsCreditPurchaseOpen(false)
        setSelectedCreditPackage(null)
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError('Failed to purchase credits. Please try again.')
      }
    } catch (err) {
      setError('Failed to purchase credits')
    } finally {
      setIsProcessing(false)
    }
  }

  // Helper to calculate credit remaining
  const getCreditsRemaining = (type: 'enhancement' | 'criminal' | 'dnc') => {
    const credit = subscription.credits[type]
    return (credit.limit + credit.purchased) - credit.used
  }

  const getCreditsTotal = (type: 'enhancement' | 'criminal' | 'dnc') => {
    const credit = subscription.credits[type]
    return credit.limit + credit.purchased
  }

  const getCreditsUsagePercent = (type: 'enhancement' | 'criminal' | 'dnc') => {
    const total = getCreditsTotal(type)
    if (total === 0) return 0
    return (subscription.credits[type].used / total) * 100
  }

  if (isLoading) {
    return (
      <SidebarWrapper role="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </SidebarWrapper>
    )
  }

  return (
    <SidebarWrapper role="admin">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Billing & Subscriptions</h1>
          <p className="text-muted-foreground">Manage your subscriptions, credits, and add-ons</p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchBillingData} disabled={isLoading}>
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
        </Button>
      </div>

      {successMessage && (
        <Alert className="mb-6 bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{successMessage}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="subscriptions" className="space-y-6">
        <TabsList>
          <TabsTrigger value="subscriptions">Subscriptions</TabsTrigger>
          <TabsTrigger value="credits">Credits & Add-ons</TabsTrigger>
          <TabsTrigger value="coming-soon">Coming Soon</TabsTrigger>
          <TabsTrigger value="history">Billing History</TabsTrigger>
        </TabsList>

        {/* Subscriptions Tab */}
        <TabsContent value="subscriptions" className="space-y-6">
          {/* Platform Subscription */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                  <Layers className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <CardTitle>Platform Subscription</CardTitle>
                  <CardDescription>Lead source syncing to Follow Up Boss</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-lg">
                      {subscription.planName}
                      {subscription.cancelAtPeriodEnd && (
                        <Badge variant="secondary" className="ml-2">Canceling</Badge>
                      )}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {subscription.price > 0 ? `$${subscription.price}/month` : "Custom pricing"} - {subscription.usage.leadSources.limit} lead source{subscription.usage.leadSources.limit !== 1 ? 's' : ''}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      Renews on {subscription.currentPeriodEnd.toLocaleDateString()}
                    </p>
                  </div>
                  <div className="space-x-2">
                    {subscription.cancelAtPeriodEnd ? (
                      <Button onClick={handleReactivateSubscription} disabled={isProcessing}>
                        {isProcessing ? 'Processing...' : 'Reactivate'}
                      </Button>
                    ) : (
                      <>
                        <Button variant="outline" asChild>
                          <Link href="/admin/billing/upgrade">Change Plan</Link>
                        </Button>
                        <Dialog open={isCancelDialogOpen} onOpenChange={setIsCancelDialogOpen}>
                          <DialogTrigger asChild>
                            <Button variant="ghost">Cancel</Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogHeader>
                              <DialogTitle>Cancel Platform Subscription</DialogTitle>
                              <DialogDescription>
                                Are you sure? You'll lose access to lead syncing at the end of your billing period on {subscription.currentPeriodEnd.toLocaleDateString()}.
                              </DialogDescription>
                            </DialogHeader>
                            <DialogFooter>
                              <Button variant="ghost" onClick={() => setIsCancelDialogOpen(false)}>
                                Keep Subscription
                              </Button>
                              <Button
                                variant="destructive"
                                onClick={handleCancelSubscription}
                                disabled={isProcessing}
                              >
                                {isProcessing ? 'Processing...' : 'Cancel Subscription'}
                              </Button>
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>
                      </>
                    )}
                  </div>
                </div>

                {/* Usage */}
                <div className="bg-muted/50 rounded-lg p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm font-medium">Lead Sources</span>
                    </div>
                    <span className="text-sm">
                      {subscription.usage.leadSources.current} / {subscription.usage.leadSources.limit} connected
                    </span>
                  </div>
                  <Progress
                    value={(subscription.usage.leadSources.current / subscription.usage.leadSources.limit) * 100}
                    className="h-2 mt-2"
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Enhancement Subscription */}
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-full bg-purple-100 dark:bg-purple-900 flex items-center justify-center">
                  <Sparkles className="h-4 w-4 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <CardTitle>Enhancement Subscription</CardTitle>
                  <CardDescription>Monthly credits for lead enrichment</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {subscription.credits.enhancement.limit > 0 ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-lg">Enhancement Plan Active</p>
                      <p className="text-sm text-muted-foreground">
                        {subscription.credits.enhancement.limit} enhancement, {subscription.credits.criminal.limit} criminal, {subscription.credits.dnc.limit} DNC credits/month
                      </p>
                    </div>
                    <Button variant="outline" asChild>
                      <Link href="/admin/billing/upgrade?tab=enhancement">Change Plan</Link>
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-6">
                  <Sparkles className="h-12 w-12 mx-auto text-muted-foreground mb-3" />
                  <h3 className="font-medium mb-1">No Enhancement Subscription</h3>
                  <p className="text-sm text-muted-foreground mb-4">
                    Add monthly credits to enhance your leads with phone numbers, emails, criminal checks, and DNC verification.
                  </p>
                  <Button asChild>
                    <Link href="/admin/billing/upgrade?tab=enhancement">
                      <Plus className="h-4 w-4 mr-2" />
                      Add Enhancement Plan
                    </Link>
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Payment Methods */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Payment Methods</CardTitle>
                <CardDescription>Manage your payment methods</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {paymentMethods.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No payment methods on file.
                </div>
              ) : (
                <div className="space-y-4">
                  {paymentMethods.map(method => (
                    <div key={method.id} className="flex items-center justify-between p-4 border rounded-lg">
                      <div className="flex items-center space-x-4">
                        <CreditCard className="h-5 w-5 text-muted-foreground" />
                        <div>
                          <p className="font-medium capitalize">{method.type} •••• {method.lastFour}</p>
                          <p className="text-sm text-muted-foreground">Expires {method.expiryDate}</p>
                        </div>
                        {method.isDefault && (
                          <Badge variant="outline" className="ml-2">Default</Badge>
                        )}
                      </div>
                      <div className="flex items-center space-x-2">
                        {!method.isDefault && (
                          <Button variant="ghost" size="sm" onClick={() => handleSetDefaultCard(method.id)} disabled={isProcessing}>
                            Set as Default
                          </Button>
                        )}
                        <Button variant="ghost" size="sm" onClick={() => handleDeleteCard(method.id)} disabled={isProcessing}>
                          Delete
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Credits & Add-ons Tab */}
        <TabsContent value="credits" className="space-y-6">
          {/* Current Credits */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Your Credits</CardTitle>
                <CardDescription>
                  Monthly credits reset on {subscription.currentPeriodEnd.toLocaleDateString()}. Purchased credits never expire.
                </CardDescription>
              </div>
              <Button onClick={() => setIsCreditPurchaseOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Buy Credits
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-6">
                {/* Enhancement Credits */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                        <Sparkles className="h-4 w-4 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <p className="font-medium">Enhancement Credits</p>
                        <p className="text-xs text-muted-foreground">Find phones, emails, address history</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{getCreditsRemaining('enhancement')} remaining</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.credits.enhancement.used} used of {getCreditsTotal('enhancement')}
                        {subscription.credits.enhancement.purchased > 0 && (
                          <span className="text-green-600"> (+{subscription.credits.enhancement.purchased} pool)</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <Progress value={getCreditsUsagePercent('enhancement')} className="h-2" />
                </div>

                {/* Criminal Search Credits */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-full bg-red-100 dark:bg-red-900 flex items-center justify-center">
                        <ShieldAlert className="h-4 w-4 text-red-600 dark:text-red-400" />
                      </div>
                      <div>
                        <p className="font-medium">Criminal Search</p>
                        <p className="text-xs text-muted-foreground">FCRA-compliant background checks</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{getCreditsRemaining('criminal')} remaining</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.credits.criminal.used} used of {getCreditsTotal('criminal')}
                        {subscription.credits.criminal.purchased > 0 && (
                          <span className="text-green-600"> (+{subscription.credits.criminal.purchased} pool)</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <Progress value={getCreditsUsagePercent('criminal')} className="h-2" />
                </div>

                {/* DNC Check Credits */}
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="h-8 w-8 rounded-full bg-orange-100 dark:bg-orange-900 flex items-center justify-center">
                        <PhoneOff className="h-4 w-4 text-orange-600 dark:text-orange-400" />
                      </div>
                      <div>
                        <p className="font-medium">DNC Checks</p>
                        <p className="text-xs text-muted-foreground">Do Not Call registry verification</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-medium">{getCreditsRemaining('dnc')} remaining</p>
                      <p className="text-xs text-muted-foreground">
                        {subscription.credits.dnc.used} used of {getCreditsTotal('dnc')}
                        {subscription.credits.dnc.purchased > 0 && (
                          <span className="text-green-600"> (+{subscription.credits.dnc.purchased} pool)</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <Progress value={getCreditsUsagePercent('dnc')} className="h-2" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Credit Purchase Dialog */}
          <Dialog open={isCreditPurchaseOpen} onOpenChange={setIsCreditPurchaseOpen}>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Purchase Credit Pool</DialogTitle>
                <DialogDescription>
                  Buy extra credits that never expire. Credits are shared across your entire team.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-6 py-4">
                {/* Enhancement Packages */}
                <div>
                  <h4 className="font-medium mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-blue-600" />
                    Enhancement Credits
                  </h4>
                  <div className="grid grid-cols-3 gap-3">
                    {enhancementPackages.map(pkg => (
                      <div
                        key={pkg.id}
                        onClick={() => setSelectedCreditPackage(pkg)}
                        className={`border rounded-lg p-3 cursor-pointer transition-all hover:border-primary ${
                          selectedCreditPackage?.id === pkg.id ? 'border-primary bg-primary/5 ring-1 ring-primary' : ''
                        }`}
                      >
                        <div className="font-medium">{pkg.amount} Credits</div>
                        <div className="text-lg font-bold text-primary">{pkg.priceDisplay}</div>
                        <div className="text-xs text-muted-foreground">${(pkg.price / pkg.amount).toFixed(2)}/credit</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Criminal Packages */}
                <div>
                  <h4 className="font-medium mb-3 flex items-center gap-2">
                    <ShieldAlert className="h-4 w-4 text-red-600" />
                    Criminal Search Credits
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                    {criminalPackages.map(pkg => (
                      <div
                        key={pkg.id}
                        onClick={() => setSelectedCreditPackage(pkg)}
                        className={`border rounded-lg p-3 cursor-pointer transition-all hover:border-primary ${
                          selectedCreditPackage?.id === pkg.id ? 'border-primary bg-primary/5 ring-1 ring-primary' : ''
                        }`}
                      >
                        <div className="font-medium">{pkg.amount} Searches</div>
                        <div className="text-lg font-bold text-primary">{pkg.priceDisplay}</div>
                        <div className="text-xs text-muted-foreground">${(pkg.price / pkg.amount).toFixed(2)}/search</div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* DNC Packages */}
                <div>
                  <h4 className="font-medium mb-3 flex items-center gap-2">
                    <PhoneOff className="h-4 w-4 text-orange-600" />
                    DNC Check Credits
                  </h4>
                  <div className="grid grid-cols-2 gap-3">
                    {dncPackages.map(pkg => (
                      <div
                        key={pkg.id}
                        onClick={() => setSelectedCreditPackage(pkg)}
                        className={`border rounded-lg p-3 cursor-pointer transition-all hover:border-primary ${
                          selectedCreditPackage?.id === pkg.id ? 'border-primary bg-primary/5 ring-1 ring-primary' : ''
                        }`}
                      >
                        <div className="font-medium">{pkg.amount} Checks</div>
                        <div className="text-lg font-bold text-primary">{pkg.priceDisplay}</div>
                        <div className="text-xs text-muted-foreground">${(pkg.price / pkg.amount).toFixed(3)}/check</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="ghost" onClick={() => {
                  setIsCreditPurchaseOpen(false)
                  setSelectedCreditPackage(null)
                }}>
                  Cancel
                </Button>
                <Button
                  onClick={handlePurchaseCredits}
                  disabled={!selectedCreditPackage || isProcessing}
                >
                  {isProcessing ? 'Processing...' : selectedCreditPackage ? `Purchase for ${selectedCreditPackage.priceDisplay}` : 'Select a package'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* Coming Soon Tab */}
        <TabsContent value="coming-soon" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Coming Soon</CardTitle>
              <CardDescription>
                Powerful add-ons to supercharge your lead management
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid md:grid-cols-2 gap-4">
                {FUTURE_ADDONS.map(addon => (
                  <div key={addon.id} className="border rounded-lg p-4 relative">
                    <Badge variant="outline" className="absolute top-4 right-4">
                      <Clock className="h-3 w-3 mr-1" />
                      Coming Soon
                    </Badge>
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-100 to-purple-100 dark:from-blue-900 dark:to-purple-900 flex items-center justify-center text-blue-600 dark:text-blue-400">
                        {addOnIcons[addon.id]}
                      </div>
                      <div className="flex-1">
                        <h3 className="font-medium">{addon.name}</h3>
                        <p className="text-sm text-muted-foreground mb-2">{addon.description}</p>
                        <p className="text-sm font-medium text-primary mb-3">{addon.priceEstimate}</p>
                        <ul className="text-xs text-muted-foreground space-y-1">
                          {addon.features.slice(0, 3).map((feature, idx) => (
                            <li key={idx} className="flex items-center gap-1">
                              <CheckCircle className="h-3 w-3 text-green-500" />
                              {feature}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 text-center">
                <p className="text-sm text-muted-foreground mb-3">
                  Want early access or have feature requests?
                </p>
                <Button variant="outline" asChild>
                  <a href="mailto:support@leadsynergy.io?subject=Add-on Feature Request">
                    Contact Us
                  </a>
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Billing History Tab */}
        <TabsContent value="history" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Billing History</CardTitle>
              <CardDescription>View your past invoices and payments</CardDescription>
            </CardHeader>
            <CardContent>
              {billingHistory.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  No billing history yet.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Invoice</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {billingHistory.map(item => (
                      <TableRow key={item.id}>
                        <TableCell>{new Date(item.date).toLocaleDateString()}</TableCell>
                        <TableCell>{item.description}</TableCell>
                        <TableCell>{item.amount}</TableCell>
                        <TableCell>
                          <Badge
                            variant={
                              item.status === "paid"
                                ? "default"
                                : item.status === "pending"
                                ? "secondary"
                                : "destructive"
                            }
                          >
                            {item.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {item.invoiceUrl ? (
                            <Button variant="ghost" size="sm" asChild>
                              <a href={item.invoiceUrl} target="_blank" rel="noopener noreferrer">
                                Download
                              </a>
                            </Button>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </SidebarWrapper>
  )
}
