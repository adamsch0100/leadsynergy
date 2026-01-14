"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Switch } from "@/components/ui/switch"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertTriangle, Bell, Lock, Mail, MessageSquare, RefreshCw, CheckCircle } from "lucide-react"
import Link from "next/link"
import { useSubscription } from "@/contexts/subscription-context"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface NotificationSetting {
  id: string
  title: string
  description: string
  emailEnabled: boolean
  smsEnabled: boolean
  pushEnabled?: boolean
  slackEnabled?: boolean
  icon: React.ElementType
  premiumChannels?: ("push" | "slack")[]
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const defaultSettings: NotificationSetting[] = [
  {
    id: "new-lead",
    title: "New Lead Assigned",
    description: "Notify agents when a new lead is assigned to them",
    emailEnabled: true,
    smsEnabled: true,
    pushEnabled: false,
    slackEnabled: false,
    icon: Bell,
    premiumChannels: ["push", "slack"],
  },
  {
    id: "stage-update",
    title: "Lead Stage Updates",
    description: "Notify when a lead's stage is updated",
    emailEnabled: true,
    smsEnabled: false,
    pushEnabled: false,
    slackEnabled: false,
    icon: MessageSquare,
    premiumChannels: ["push", "slack"],
  },
  {
    id: "commission",
    title: "Commission Tracking",
    description: "Notify when a commission is recorded or updated",
    emailEnabled: true,
    smsEnabled: false,
    pushEnabled: false,
    slackEnabled: false,
    icon: Mail,
    premiumChannels: ["push", "slack"],
  },
]

export default function NotificationsPage() {
  const { subscription } = useSubscription()
  const [showUpgradeAlert, setShowUpgradeAlert] = useState(false)
  const [settings, setSettings] = useState<NotificationSetting[]>(defaultSettings)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch notification settings
  useEffect(() => {
    if (user) {
      fetchSettings()
    }
  }, [user])

  const fetchSettings = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/settings/notifications`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && data.data) {
        // Merge fetched settings with defaults
        const fetchedSettings = data.data
        setSettings(defaultSettings.map(setting => ({
          ...setting,
          emailEnabled: fetchedSettings[`${setting.id}_email`] ?? setting.emailEnabled,
          smsEnabled: fetchedSettings[`${setting.id}_sms`] ?? setting.smsEnabled,
          pushEnabled: fetchedSettings[`${setting.id}_push`] ?? setting.pushEnabled,
          slackEnabled: fetchedSettings[`${setting.id}_slack`] ?? setting.slackEnabled,
        })))
      }
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleToggleChannel = (id: string, channel: "email" | "sms" | "push" | "slack") => {
    const setting = settings.find((s) => s.id === id)
    if (setting?.premiumChannels?.includes(channel as "push" | "slack") && subscription.plan === "free") {
      setShowUpgradeAlert(true)
      return
    }

    setSettings(settings.map((setting) => {
      if (setting.id === id) {
        return {
          ...setting,
          [`${channel}Enabled`]: !setting[`${channel}Enabled` as keyof NotificationSetting],
        }
      }
      return setting
    }))
  }

  const handleSave = async () => {
    if (!user) return
    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      // Transform settings to API format
      const settingsPayload: Record<string, boolean> = {}
      settings.forEach(setting => {
        settingsPayload[`${setting.id}_email`] = setting.emailEnabled
        settingsPayload[`${setting.id}_sms`] = setting.smsEnabled
        settingsPayload[`${setting.id}_push`] = setting.pushEnabled || false
        settingsPayload[`${setting.id}_slack`] = setting.slackEnabled || false
      })

      const res = await fetch(`${API_BASE_URL}/api/supabase/settings/notifications`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify(settingsPayload)
      })
      const data = await res.json()
      if (data.success) {
        setSuccessMessage('Notification settings saved successfully!')
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || 'Failed to save settings')
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
          <h1 className="text-3xl font-bold tracking-tight">Notification Settings</h1>
          <p className="text-muted-foreground">Configure how and when notifications are sent</p>
        </div>
      </div>

      {showUpgradeAlert && (
        <Alert className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Premium Feature</AlertTitle>
          <AlertDescription className="mt-2">
            Push and Slack notifications are only available on Pro and Enterprise plans.
            <div className="mt-2">
              <Button variant="outline" asChild className="mr-2">
                <Link href="/admin/billing">Upgrade Plan</Link>
              </Button>
              <Button variant="ghost" onClick={() => setShowUpgradeAlert(false)}>
                Dismiss
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

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

      <Card>
        <CardHeader>
          <CardTitle>Notification Preferences</CardTitle>
          <CardDescription>Choose which notifications to receive and how to receive them</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {settings.map((setting) => (
              <div key={setting.id} className="flex items-start space-x-4 rounded-lg border p-4">
                <div className="mt-0.5 rounded-full bg-primary/10 p-2">
                  <setting.icon className="h-5 w-5 text-primary" />
                </div>
                <div className="flex-1 space-y-1">
                  <h4 className="font-medium">{setting.title}</h4>
                  <p className="text-sm text-muted-foreground">{setting.description}</p>
                </div>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={`${setting.id}-email`}
                      checked={setting.emailEnabled}
                      onCheckedChange={() => handleToggleChannel(setting.id, "email")}
                    />
                    <Label htmlFor={`${setting.id}-email`}>Email</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={`${setting.id}-sms`}
                      checked={setting.smsEnabled}
                      onCheckedChange={() => handleToggleChannel(setting.id, "sms")}
                    />
                    <Label htmlFor={`${setting.id}-sms`}>SMS</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={`${setting.id}-push`}
                      checked={setting.pushEnabled}
                      disabled={subscription.plan === "free"}
                      onCheckedChange={() => handleToggleChannel(setting.id, "push")}
                    />
                    <Label
                      htmlFor={`${setting.id}-push`}
                      className={subscription.plan === "free" ? "text-muted-foreground" : ""}
                    >
                      Push {subscription.plan === "free" && <Lock className="inline h-3 w-3 ml-1" />}
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Switch
                      id={`${setting.id}-slack`}
                      checked={setting.slackEnabled}
                      disabled={subscription.plan === "free"}
                      onCheckedChange={() => handleToggleChannel(setting.id, "slack")}
                    />
                    <Label
                      htmlFor={`${setting.id}-slack`}
                      className={subscription.plan === "free" ? "text-muted-foreground" : ""}
                    >
                      Slack {subscription.plan === "free" && <Lock className="inline h-3 w-3 ml-1" />}
                    </Label>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 flex justify-end">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Notification Settings'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}
