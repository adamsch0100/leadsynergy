"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  Check,
  ChevronRight,
  Key,
  Loader2,
  MessageSquareText,
  CheckCircle,
  AlertTriangle,
} from "lucide-react"
import { apiFetch } from "@/lib/api"

type OnboardingStep = "fub_api_key" | "lead_sources_info" | "complete"

export default function OnboardingPage() {
  const router = useRouter()
  const [step, setStep] = useState<OnboardingStep>("fub_api_key")
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState("")

  // Step 1: FUB API Key
  const [fubApiKey, setFubApiKey] = useState("")
  const [fubKeyTesting, setFubKeyTesting] = useState(false)
  const [fubKeyValid, setFubKeyValid] = useState<boolean | null>(null)

  // Step 2: Lead Sources Info (free-text)
  const [platformsDescription, setPlatformsDescription] = useState("")
  const [submittingInfo, setSubmittingInfo] = useState(false)

  // Load onboarding status on mount
  useEffect(() => {
    loadOnboardingStatus()
  }, [])

  const loadOnboardingStatus = async () => {
    setIsLoading(true)
    try {
      const res = await apiFetch("/api/onboarding/status")
      if (!res) {
        router.push("/login")
        return
      }
      const data = await res.json()

      if (data.success) {
        const status = data.data
        // If already complete, redirect to dashboard
        if (status.current_step === "complete" || status.is_complete) {
          router.push("/admin/dashboard")
          return
        }
        // Map legacy step names to new ones
        const stepMap: Record<string, OnboardingStep> = {
          fub_api_key: "fub_api_key",
          lead_sources: "lead_sources_info",
          lead_sources_info: "lead_sources_info",
          configure_sources: "lead_sources_info",
          complete: "complete",
        }
        setStep(stepMap[status.current_step] || "fub_api_key")
        if (status.fub_api_key) {
          setFubApiKey(status.fub_api_key)
          setFubKeyValid(true)
        }
      }
    } catch {
      // If status check fails, start from beginning
    } finally {
      setIsLoading(false)
    }
  }

  // Step 1: Test FUB API Key
  const testFubApiKey = async () => {
    if (!fubApiKey.trim()) return
    setFubKeyTesting(true)
    setFubKeyValid(null)
    setError("")

    try {
      const res = await apiFetch("/api/setup/fub-api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fub_api_key: fubApiKey }),
      })
      if (!res) throw new Error("Not authenticated")
      const data = await res.json()

      if (data.success || data.valid) {
        setFubKeyValid(true)
      } else {
        setFubKeyValid(false)
        setError(data.error || "Invalid API key")
      }
    } catch (e: any) {
      setFubKeyValid(false)
      setError(e.message || "Failed to test API key")
    } finally {
      setFubKeyTesting(false)
    }
  }

  const proceedFromFubKey = () => {
    if (!fubKeyValid) return
    setStep("lead_sources_info")
  }

  // Step 2: Submit platform info
  const submitPlatformInfo = async () => {
    if (!platformsDescription.trim()) {
      setError("Please tell us about the referral platforms you use")
      return
    }
    setSubmittingInfo(true)
    setError("")

    try {
      const res = await apiFetch("/api/onboarding/submit-platform-info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platforms_description: platformsDescription }),
      })

      if (!res) throw new Error("Not authenticated")
      const data = await res.json()

      if (data.success) {
        await completeOnboarding()
      } else {
        setError(data.error || "Failed to submit platform info")
      }
    } catch (e: any) {
      setError(e.message || "An unexpected error occurred")
    } finally {
      setSubmittingInfo(false)
    }
  }

  const skipPlatformInfo = async () => {
    setSubmittingInfo(true)
    setError("")
    try {
      await completeOnboarding()
    } finally {
      setSubmittingInfo(false)
    }
  }

  const completeOnboarding = async () => {
    setIsLoading(true)
    try {
      const res = await apiFetch("/api/onboarding/complete", {
        method: "POST",
      })
      if (res) {
        const data = await res.json()
        if (data.success) {
          setStep("complete")
        } else {
          setError(data.error || "Failed to complete onboarding")
        }
      }
    } finally {
      setIsLoading(false)
    }
  }

  // Loading state
  if (isLoading && step === "fub_api_key") {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Step indicators
  const steps = [
    { key: "fub_api_key", label: "Connect FUB" },
    { key: "lead_sources_info", label: "Your Platforms" },
    { key: "complete", label: "Done" },
  ]
  const currentStepIndex = steps.findIndex((s) => s.key === step)

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-950 dark:to-blue-950/20">
      <div className="container max-w-2xl py-12">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center mx-auto mb-4">
            <span className="text-white font-bold text-lg">LS</span>
          </div>
          <h1 className="text-2xl font-bold">Welcome to LeadSynergy</h1>
          <p className="text-muted-foreground mt-1">Let&apos;s get your account set up</p>
        </div>

        {/* Step Progress */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {steps.map((s, i) => (
            <div key={s.key} className="flex items-center gap-2">
              <div
                className={`h-8 w-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  i < currentStepIndex
                    ? "bg-primary text-primary-foreground"
                    : i === currentStepIndex
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground"
                }`}
              >
                {i < currentStepIndex ? <Check className="h-4 w-4" /> : i + 1}
              </div>
              <span
                className={`text-sm hidden sm:block ${
                  i === currentStepIndex ? "font-medium" : "text-muted-foreground"
                }`}
              >
                {s.label}
              </span>
              {i < steps.length - 1 && (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          ))}
        </div>

        {/* Error */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Step 1: FUB API Key */}
        {step === "fub_api_key" && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                Connect Follow Up Boss
              </CardTitle>
              <CardDescription>
                Enter your Follow Up Boss API key to connect your CRM. You can find this in FUB under
                Admin &gt; API.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fub-key">FUB API Key</Label>
                <div className="flex gap-2">
                  <Input
                    id="fub-key"
                    type="password"
                    placeholder="Enter your Follow Up Boss API key"
                    value={fubApiKey}
                    onChange={(e) => {
                      setFubApiKey(e.target.value)
                      setFubKeyValid(null)
                      setError("")
                    }}
                  />
                  <Button
                    variant="outline"
                    onClick={testFubApiKey}
                    disabled={!fubApiKey.trim() || fubKeyTesting}
                  >
                    {fubKeyTesting ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      "Test"
                    )}
                  </Button>
                </div>
                {fubKeyValid === true && (
                  <p className="text-sm text-green-600 flex items-center gap-1">
                    <CheckCircle className="h-4 w-4" /> API key is valid
                  </p>
                )}
                {fubKeyValid === false && (
                  <p className="text-sm text-red-600 flex items-center gap-1">
                    <AlertTriangle className="h-4 w-4" /> Invalid API key
                  </p>
                )}
              </div>

              <div className="flex justify-end pt-4">
                <Button onClick={proceedFromFubKey} disabled={!fubKeyValid}>
                  Continue
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 2: Tell us about your platforms */}
        {step === "lead_sources_info" && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquareText className="h-5 w-5" />
                Tell Us About Your Lead Sources
              </CardTitle>
              <CardDescription>
                What referral platforms do you currently use to receive leads? Our team will
                configure your integrations and notify you when everything is connected.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="platforms-desc">
                  Which referral platforms or lead sources do you use?
                </Label>
                <Textarea
                  id="platforms-desc"
                  placeholder="Example: I receive referrals from HomeLight and ReferralExchange. I also get leads from my Redfin partner account..."
                  value={platformsDescription}
                  onChange={(e) => {
                    setPlatformsDescription(e.target.value)
                    setError("")
                  }}
                  rows={5}
                  className="resize-none"
                />
                <p className="text-xs text-muted-foreground">
                  Include any platform names, login details you want us to know about, or
                  questions about supported integrations.
                </p>
              </div>

              <div className="rounded-lg bg-blue-50 dark:bg-blue-950/30 p-4 text-sm text-blue-800 dark:text-blue-200">
                <p className="font-medium mb-1">What happens next?</p>
                <ul className="list-disc list-inside space-y-1 text-blue-700 dark:text-blue-300">
                  <li>Our team reviews your platform info</li>
                  <li>We configure your lead source integrations</li>
                  <li>You&apos;ll be notified when syncing is live</li>
                  <li>You can also reach out to support at any time</li>
                </ul>
              </div>

              <div className="flex justify-between pt-4">
                <Button variant="ghost" onClick={() => setStep("fub_api_key")}>
                  Back
                </Button>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={skipPlatformInfo} disabled={submittingInfo}>
                    Skip for now
                  </Button>
                  <Button
                    onClick={submitPlatformInfo}
                    disabled={!platformsDescription.trim() || submittingInfo}
                  >
                    {submittingInfo ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Submit & Continue
                    <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Step 3: Complete */}
        {step === "complete" && (
          <Card>
            <CardContent className="pt-8 pb-8">
              <div className="text-center">
                <div className="mx-auto h-16 w-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-6">
                  <CheckCircle className="h-8 w-8 text-green-600" />
                </div>
                <h2 className="text-2xl font-bold mb-2">You&apos;re All Set!</h2>
                <p className="text-muted-foreground mb-4 max-w-md mx-auto">
                  Your Follow Up Boss connection is active and your AI agent is ready to engage
                  leads.
                </p>
                {platformsDescription.trim() && (
                  <p className="text-sm text-muted-foreground mb-6 max-w-md mx-auto">
                    We&apos;ve received your lead source info and our team will configure your
                    integrations shortly. You&apos;ll receive a notification when syncing is live.
                  </p>
                )}
                <Button size="lg" onClick={() => router.push("/admin/dashboard")}>
                  Go to Dashboard
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
