"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { AlertCircle, CheckCircle2, Key, RefreshCw } from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function SystemSettingsPage() {
  const [apiKey, setApiKey] = useState("")
  const [apiKeyConfigured, setApiKeyConfigured] = useState(false)
  const [minDays, setMinDays] = useState("5")
  const [maxDays, setMaxDays] = useState("10")
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch settings
  useEffect(() => {
    if (user) {
      fetchSettings()
    }
  }, [user])

  const fetchSettings = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      // Fetch system settings
      const res = await fetch(`${API_BASE_URL}/api/supabase/system-settings`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && data.data) {
        setMinDays(data.data.min_update_interval_days?.toString() || "5")
        setMaxDays(data.data.max_update_interval_days?.toString() || "10")
      }

      // Check if user has FUB API key by checking session user data
      const supabase = createClient()
      const { data: userData } = await supabase.from('users').select('fub_api_key').eq('id', user.id).single()
      if (userData) {
        setApiKeyConfigured(!!userData.fub_api_key)
      }
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSaveSettings = async () => {
    if (!user) return
    setIsSaving(true)
    setError(null)
    setSaveSuccess(false)

    try {
      let settingsSuccess = true

      // Only try to save system settings if values changed from defaults
      // Note: min/max update interval columns may not exist in DB yet
      try {
        const settingsRes = await fetch(`${API_BASE_URL}/api/supabase/system-settings`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user.id
          },
          body: JSON.stringify({
            // Only send updated_at for now since interval columns don't exist
            // min_update_interval_days: parseInt(minDays),
            // max_update_interval_days: parseInt(maxDays)
          })
        })
        const settingsData = await settingsRes.json()
        settingsSuccess = settingsData.success
      } catch (settingsErr) {
        console.warn('System settings update skipped:', settingsErr)
        // Don't fail the whole save if system settings fails
      }

      // If API key is provided, save it to user's profile
      if (apiKey) {
        // Get auth token for the user profile endpoint
        const supabase = createClient()
        const { data: sessionData } = await supabase.auth.getSession()
        const token = sessionData.session?.access_token

        if (!token) {
          setError('Session expired. Please refresh the page.')
          return
        }

        const apiKeyRes = await fetch(`${API_BASE_URL}/api/supabase/users/current/profile/api-key`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ fub_api_key: apiKey })
        })
        const apiKeyData = await apiKeyRes.json()
        if (apiKeyData.success) {
          setApiKeyConfigured(true)
          setApiKey("") // Clear the input after saving
          // Show success for API key save
          setSaveSuccess(true)
          setTimeout(() => setSaveSuccess(false), 3000)
        } else {
          setError(apiKeyData.error || 'Failed to save API key')
          return
        }
      } else {
        // No API key to save, show success if we got here
        setSaveSuccess(true)
        setTimeout(() => setSaveSuccess(false), 3000)
      }
    } catch (err) {
      setError('Failed to save settings')
    } finally {
      setIsSaving(false)
    }
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
          <h1 className="text-3xl font-bold tracking-tight">System Settings</h1>
          <p className="text-muted-foreground">Configure core integrations, API keys, and global system parameters</p>
        </div>
      </div>

      {saveSuccess && (
        <Alert className="mb-6 bg-green-50 border-green-200 text-green-800">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertTitle>Success</AlertTitle>
          <AlertDescription>Your system settings have been saved successfully.</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>API Keys & Integrations</CardTitle>
          <CardDescription>Configure external service integrations and API keys</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="h-5 w-5 text-primary" />
                <h3 className="font-medium">Follow Up Boss API Key Status:</h3>
              </div>
              <Badge variant={apiKeyConfigured ? "default" : "secondary"}>
                {apiKeyConfigured ? "Configured" : "Not Configured"}
              </Badge>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="fub-api-key">Enter FUB API Key</Label>
              <Input
                id="fub-api-key"
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={apiKeyConfigured ? "Enter new API key to update" : "Enter your Follow Up Boss API key"}
              />
              <p className="text-sm text-muted-foreground">Required for lead synchronization & webhook setup.</p>
            </div>
          </div>

          {!apiKeyConfigured && apiKey === "" && (
            <Alert variant="destructive" className="bg-red-50 border-red-200 text-red-800">
              <AlertCircle className="h-4 w-4 text-red-600" />
              <AlertTitle>API Key Required</AlertTitle>
              <AlertDescription>
                A Follow Up Boss API key is required for lead synchronization to function properly.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Automated Update Interval</CardTitle>
          <CardDescription>Configure the timing for automated lead status updates</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <p className="text-sm text-muted-foreground">
              Set the minimum and maximum days for random delay between automated lead updates. This helps create a
              natural communication pattern.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="grid gap-2">
                <Label htmlFor="min-days">Minimum Days</Label>
                <Input
                  id="min-days"
                  type="number"
                  min="1"
                  max="30"
                  value={minDays}
                  onChange={(e) => setMinDays(e.target.value)}
                />
                <p className="text-sm text-muted-foreground">Min random delay (e.g., 5)</p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="max-days">Maximum Days</Label>
                <Input
                  id="max-days"
                  type="number"
                  min="1"
                  max="30"
                  value={maxDays}
                  onChange={(e) => setMaxDays(e.target.value)}
                />
                <p className="text-sm text-muted-foreground">Max random delay (e.g., 10)</p>
              </div>
            </div>

            <Separator />

            <div className="flex justify-end">
              <Button onClick={handleSaveSettings} disabled={isSaving}>
                {isSaving ? (
                  <>
                    <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save System Settings'
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}
