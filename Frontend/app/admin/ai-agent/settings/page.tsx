"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Bot,
  Clock,
  MessageSquare,
  Users,
  Settings2,
  Sparkles
} from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface AISettings {
  is_enabled: boolean
  agent_name: string
  brokerage_name: string
  personality_tone: string
  working_hours_start: string
  working_hours_end: string
  timezone: string
  response_delay_seconds: number
  max_response_length: number
  auto_handoff_score: number
  max_ai_messages_per_lead: number
  qualification_questions: string[]
  custom_scripts: Record<string, string>
}

const DEFAULT_SETTINGS: AISettings = {
  is_enabled: true,
  agent_name: "Sarah",
  brokerage_name: "",
  personality_tone: "friendly_casual",
  working_hours_start: "08:00",
  working_hours_end: "20:00",
  timezone: "America/New_York",
  response_delay_seconds: 30,
  max_response_length: 160,
  auto_handoff_score: 80,
  max_ai_messages_per_lead: 10,
  qualification_questions: [],
  custom_scripts: {},
}

const PERSONALITY_OPTIONS = [
  { value: "friendly_casual", label: "Friendly & Casual", description: "Warm, conversational tone like texting a helpful friend" },
  { value: "professional", label: "Professional", description: "Polished and formal business communication" },
  { value: "enthusiastic", label: "Enthusiastic", description: "High energy, excited about helping" },
  { value: "consultative", label: "Consultative", description: "Expert advisor approach, more educational" },
]

const TIMEZONE_OPTIONS = [
  { value: "America/New_York", label: "Eastern Time (ET)" },
  { value: "America/Chicago", label: "Central Time (CT)" },
  { value: "America/Denver", label: "Mountain Time (MT)" },
  { value: "America/Los_Angeles", label: "Pacific Time (PT)" },
  { value: "America/Phoenix", label: "Arizona (no DST)" },
]

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AISettingsPage() {
  const [settings, setSettings] = useState<AISettings>(DEFAULT_SETTINGS)
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [newQuestion, setNewQuestion] = useState("")

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch AI settings
  useEffect(() => {
    if (user) {
      fetchSettings()
    }
  }, [user])

  const fetchSettings = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      const response = await fetch(`${API_BASE_URL}/api/ai-settings`, {
        headers: { 'X-User-ID': user.id }
      })

      const data = await response.json()

      if (data.success && data.settings) {
        setSettings({
          ...DEFAULT_SETTINGS,
          ...data.settings,
          qualification_questions: data.settings.qualification_questions || [],
          custom_scripts: data.settings.custom_scripts || {},
        })
      }
    } catch (err) {
      console.error('Failed to fetch AI settings:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleSave = async () => {
    if (!user) return
    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai-settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify(settings)
      })

      const data = await response.json()

      if (data.success) {
        setSuccessMessage('AI settings saved successfully!')
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

  const addQuestion = () => {
    if (newQuestion.trim()) {
      setSettings({
        ...settings,
        qualification_questions: [...settings.qualification_questions, newQuestion.trim()]
      })
      setNewQuestion("")
    }
  }

  const removeQuestion = (index: number) => {
    setSettings({
      ...settings,
      qualification_questions: settings.qualification_questions.filter((_, i) => i !== index)
    })
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
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Bot className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AI Agent Settings</h1>
            <p className="text-muted-foreground">Configure your AI sales agent behavior and personality</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              id="ai-enabled"
              checked={settings.is_enabled}
              onCheckedChange={(checked) => setSettings({ ...settings, is_enabled: checked })}
            />
            <Label htmlFor="ai-enabled" className="font-medium">
              {settings.is_enabled ? "AI Agent Active" : "AI Agent Paused"}
            </Label>
          </div>
        </div>
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

      <Tabs defaultValue="identity" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="identity" className="flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            Identity
          </TabsTrigger>
          <TabsTrigger value="behavior" className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            Behavior
          </TabsTrigger>
          <TabsTrigger value="schedule" className="flex items-center gap-2">
            <Clock className="h-4 w-4" />
            Schedule
          </TabsTrigger>
          <TabsTrigger value="qualification" className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4" />
            Qualification
          </TabsTrigger>
        </TabsList>

        {/* Identity Tab */}
        <TabsContent value="identity">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Agent Identity</CardTitle>
                <CardDescription>How your AI agent introduces itself to leads</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="agent_name">Agent Name</Label>
                  <Input
                    id="agent_name"
                    value={settings.agent_name}
                    onChange={(e) => setSettings({ ...settings, agent_name: e.target.value })}
                    placeholder="Sarah"
                  />
                  <p className="text-xs text-muted-foreground">
                    The name your AI agent uses when introducing itself
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="brokerage_name">Brokerage Name</Label>
                  <Input
                    id="brokerage_name"
                    value={settings.brokerage_name}
                    onChange={(e) => setSettings({ ...settings, brokerage_name: e.target.value })}
                    placeholder="Your Real Estate Company"
                  />
                  <p className="text-xs text-muted-foreground">
                    Your company name included in messages
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Personality Style</CardTitle>
                <CardDescription>Choose how your AI agent communicates</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>Tone of Voice</Label>
                  <Select
                    value={settings.personality_tone}
                    onValueChange={(value) => setSettings({ ...settings, personality_tone: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PERSONALITY_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          <div className="flex flex-col">
                            <span className="font-medium">{option.label}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {PERSONALITY_OPTIONS.find(p => p.value === settings.personality_tone)?.description}
                  </p>
                </div>

                <div className="p-4 rounded-lg bg-muted/50 border">
                  <p className="text-sm font-medium mb-2">Example Message Preview:</p>
                  <p className="text-sm text-muted-foreground italic">
                    {settings.personality_tone === "friendly_casual" && (
                      `"Hey there! I'm ${settings.agent_name}${settings.brokerage_name ? ` from ${settings.brokerage_name}` : ''}. Saw you were checking out some places - super exciting! What's got you looking right now?"`
                    )}
                    {settings.personality_tone === "professional" && (
                      `"Hello, this is ${settings.agent_name}${settings.brokerage_name ? ` with ${settings.brokerage_name}` : ''}. Thank you for your interest in our listings. I'd be happy to assist you with your real estate needs. What type of property are you looking for?"`
                    )}
                    {settings.personality_tone === "enthusiastic" && (
                      `"Hi there! I'm ${settings.agent_name}${settings.brokerage_name ? ` from ${settings.brokerage_name}` : ''} and I'm SO excited to help you find your dream home! This is going to be an amazing journey - let's get started!"`
                    )}
                    {settings.personality_tone === "consultative" && (
                      `"Hello, I'm ${settings.agent_name}${settings.brokerage_name ? `, a real estate specialist with ${settings.brokerage_name}` : ''}. I'm here to guide you through the home buying process. What questions do you have about the current market?"`
                    )}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Behavior Tab */}
        <TabsContent value="behavior">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Response Settings</CardTitle>
                <CardDescription>Control how the AI responds to leads</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="response_delay">Response Delay (seconds)</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="response_delay"
                      type="number"
                      min="0"
                      max="300"
                      value={settings.response_delay_seconds}
                      onChange={(e) => setSettings({ ...settings, response_delay_seconds: parseInt(e.target.value) || 0 })}
                      className="w-24"
                    />
                    <span className="text-muted-foreground">seconds</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Adds a natural delay before responding (0-300 seconds)
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="max_length">Max Message Length</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="max_length"
                      type="number"
                      min="100"
                      max="500"
                      value={settings.max_response_length}
                      onChange={(e) => setSettings({ ...settings, max_response_length: parseInt(e.target.value) || 160 })}
                      className="w-24"
                    />
                    <span className="text-muted-foreground">characters</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Maximum characters per SMS message (160 recommended for single SMS)
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Handoff Settings</CardTitle>
                <CardDescription>When to escalate to human agents</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="handoff_score">Auto-Handoff Score Threshold</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="handoff_score"
                      type="number"
                      min="50"
                      max="100"
                      value={settings.auto_handoff_score}
                      onChange={(e) => setSettings({ ...settings, auto_handoff_score: parseInt(e.target.value) || 80 })}
                      className="w-24"
                    />
                    <span className="text-muted-foreground">/ 100</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Automatically notify human agent when lead score reaches this threshold
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="max_messages">Max AI Messages Per Lead</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="max_messages"
                      type="number"
                      min="3"
                      max="50"
                      value={settings.max_ai_messages_per_lead}
                      onChange={(e) => setSettings({ ...settings, max_ai_messages_per_lead: parseInt(e.target.value) || 10 })}
                      className="w-24"
                    />
                    <span className="text-muted-foreground">messages</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    After this many messages, the AI will hand off to a human agent
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Schedule Tab */}
        <TabsContent value="schedule">
          <Card>
            <CardHeader>
              <CardTitle>Operating Hours</CardTitle>
              <CardDescription>
                Define when the AI agent can send messages (for TCPA compliance)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-6 md:grid-cols-3">
                <div className="grid gap-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <Select
                    value={settings.timezone}
                    onValueChange={(value) => setSettings({ ...settings, timezone: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEZONE_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="start_time">Start Time</Label>
                  <Input
                    id="start_time"
                    type="time"
                    value={settings.working_hours_start}
                    onChange={(e) => setSettings({ ...settings, working_hours_start: e.target.value })}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="end_time">End Time</Label>
                  <Input
                    id="end_time"
                    type="time"
                    value={settings.working_hours_end}
                    onChange={(e) => setSettings({ ...settings, working_hours_end: e.target.value })}
                  />
                </div>
              </div>
              <Alert>
                <Clock className="h-4 w-4" />
                <AlertDescription>
                  TCPA regulations require SMS messages only between 8 AM and 8 PM in the recipient's local time.
                  Messages outside these hours will be queued for later delivery.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Qualification Tab */}
        <TabsContent value="qualification">
          <Card>
            <CardHeader>
              <CardTitle>Custom Qualification Questions</CardTitle>
              <CardDescription>
                Add custom questions the AI will ask during lead qualification (in addition to standard questions about timeline, budget, location)
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="Enter a custom qualification question..."
                  value={newQuestion}
                  onChange={(e) => setNewQuestion(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && addQuestion()}
                />
                <Button onClick={addQuestion} type="button">
                  Add Question
                </Button>
              </div>

              {settings.qualification_questions.length > 0 ? (
                <div className="space-y-2">
                  {settings.qualification_questions.map((question, index) => (
                    <div key={index} className="flex items-center justify-between p-3 rounded-lg border bg-muted/30">
                      <span className="text-sm">{question}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeQuestion(index)}
                        className="text-destructive hover:text-destructive"
                      >
                        Remove
                      </Button>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-muted-foreground">
                  <MessageSquare className="h-8 w-8 mx-auto mb-2 opacity-50" />
                  <p>No custom questions added yet</p>
                  <p className="text-xs mt-1">The AI will use standard qualification questions</p>
                </div>
              )}

              <div className="p-4 rounded-lg bg-muted/50 border mt-4">
                <p className="text-sm font-medium mb-2">Default Questions (always asked):</p>
                <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                  <li>Timeline: When are you looking to buy/sell?</li>
                  <li>Budget: What's your price range?</li>
                  <li>Location: Any preferred areas or neighborhoods?</li>
                  <li>Pre-approval: Have you been pre-approved for a mortgage?</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <div className="mt-8 flex justify-end gap-4">
        <Button variant="outline" onClick={fetchSettings}>
          Reset Changes
        </Button>
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Save Settings'
          )}
        </Button>
      </div>
    </SidebarWrapper>
  )
}
