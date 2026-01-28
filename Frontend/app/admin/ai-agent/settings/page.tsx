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
  Sparkles,
  Key,
  Send,
  Eye,
  EyeOff,
  Bell,
  Mail,
  Shield
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface AISettings {
  is_enabled: boolean
  auto_enable_new_leads: boolean  // Auto-enable AI for new leads
  agent_name: string
  brokerage_name: string
  team_members: string  // Human agent names (e.g., "Adam and Mandi")
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
  // LLM Model Configuration
  llm_provider: string
  llm_model: string
  llm_model_fallback: string
  // Agent Notification
  notification_fub_person_id: number | null
}

interface FUBLoginSettings {
  fub_login_email: string
  fub_login_password: string
  fub_login_type: 'email' | 'google' | 'microsoft'
  has_password: boolean
}

const DEFAULT_FUB_LOGIN: FUBLoginSettings = {
  fub_login_email: '',
  fub_login_password: '',
  fub_login_type: 'email',
  has_password: false
}

const DEFAULT_SETTINGS: AISettings = {
  is_enabled: true,
  auto_enable_new_leads: false,
  agent_name: "Sarah",
  brokerage_name: "",
  team_members: "",  // e.g., "Adam and Mandi"
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
  // LLM Model Configuration
  llm_provider: "openrouter",
  llm_model: "x-ai/grok-4.1-fast",
  llm_model_fallback: "google/gemini-2.5-flash-lite",
  // Agent Notification
  notification_fub_person_id: null,
}

// Available LLM Models (OpenRouter)
const LLM_MODEL_OPTIONS = [
  { value: "x-ai/grok-4.1-fast", label: "Grok 4.1 Fast", description: "Very cheap (~$0.0003/msg), fast, reliable (Recommended)" },
  { value: "google/gemini-2.5-flash-lite", label: "Google Gemini 2.5 Flash Lite", description: "Cheap, fast, good quality" },
  { value: "meta-llama/llama-3.3-70b-instruct:free", label: "Meta Llama 3.3 70B", description: "Free, high quality" },
  { value: "deepseek/deepseek-r1-0528:free", label: "DeepSeek R1", description: "Free, reasoning model" },
  { value: "google/gemini-2.0-flash-exp:free", label: "Google Gemini 2.0 Flash", description: "Free, 1M context" },
]

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

  // FUB Login state
  const [fubLogin, setFubLogin] = useState<FUBLoginSettings>(DEFAULT_FUB_LOGIN)
  const [isSavingFubLogin, setIsSavingFubLogin] = useState(false)
  const [isTestingFubLogin, setIsTestingFubLogin] = useState(false)
  const [fubLoginMessage, setFubLoginMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showPassword, setShowPassword] = useState(false)

  // Gmail credentials state (for FUB verification emails, 2FA, etc.)
  const [gmailEmail, setGmailEmail] = useState("")
  const [gmailAppPassword, setGmailAppPassword] = useState("")
  const [gmailConfigured, setGmailConfigured] = useState(false)
  const [isSavingGmail, setIsSavingGmail] = useState(false)
  const [gmailMessage, setGmailMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showGmailPassword, setShowGmailPassword] = useState(false)

  // FUB API Key state
  const [fubApiKey, setFubApiKey] = useState("")
  const [fubApiKeyConfigured, setFubApiKeyConfigured] = useState(false)
  const [isSavingApiKey, setIsSavingApiKey] = useState(false)
  const [apiKeyMessage, setApiKeyMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  const [showApiKey, setShowApiKey] = useState(false)

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

  // Fetch FUB login settings
  const fetchFubLoginSettings = async () => {
    if (!user) return
    try {
      const response = await fetch(`${API_BASE_URL}/fub/ai/settings/fub-login`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await response.json()
      if (data.success && data.data) {
        setFubLogin({
          fub_login_email: data.data.fub_login_email || '',
          fub_login_password: '', // Never returned from server
          fub_login_type: data.data.fub_login_type || 'email',
          has_password: data.data.has_password || false
        })
      }
    } catch (err) {
      console.error('Failed to fetch FUB login settings:', err)
    }
  }

  // Save FUB login settings
  const handleSaveFubLogin = async () => {
    if (!user) return
    setIsSavingFubLogin(true)
    setFubLoginMessage(null)

    try {
      const payload: Record<string, string> = {
        fub_login_email: fubLogin.fub_login_email,
        fub_login_type: fubLogin.fub_login_type
      }
      // Only include password if it was entered
      if (fubLogin.fub_login_password) {
        payload.fub_login_password = fubLogin.fub_login_password
      }

      const response = await fetch(`${API_BASE_URL}/fub/ai/settings/fub-login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (data.success) {
        setFubLoginMessage({ type: 'success', text: 'FUB login credentials saved successfully!' })
        setFubLogin({ ...fubLogin, fub_login_password: '', has_password: true })
        setTimeout(() => setFubLoginMessage(null), 5000)
      } else {
        setFubLoginMessage({ type: 'error', text: data.message || 'Failed to save credentials' })
      }
    } catch (err) {
      setFubLoginMessage({ type: 'error', text: 'Failed to save FUB login credentials' })
    } finally {
      setIsSavingFubLogin(false)
    }
  }

  // Test FUB login
  const handleTestFubLogin = async () => {
    if (!user) return
    setIsTestingFubLogin(true)
    setFubLoginMessage(null)

    try {
      const payload: Record<string, string> = {}
      // Only include credentials if entered (otherwise uses saved ones)
      if (fubLogin.fub_login_email) {
        payload.fub_login_email = fubLogin.fub_login_email
      }
      if (fubLogin.fub_login_password) {
        payload.fub_login_password = fubLogin.fub_login_password
      }
      if (fubLogin.fub_login_type) {
        payload.fub_login_type = fubLogin.fub_login_type
      }

      const response = await fetch(`${API_BASE_URL}/fub/ai/settings/fub-login/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify(payload)
      })

      const data = await response.json()
      if (data.success && data.session_valid) {
        setFubLoginMessage({ type: 'success', text: 'Login test successful! FUB connection is working.' })
      } else {
        setFubLoginMessage({ type: 'error', text: data.message || 'Login test failed' })
      }
    } catch (err) {
      setFubLoginMessage({ type: 'error', text: 'Failed to test FUB login' })
    } finally {
      setIsTestingFubLogin(false)
    }
  }

  // Fetch FUB login settings when user loads
  useEffect(() => {
    if (user) {
      fetchFubLoginSettings()
      fetchGmailSettings()
      fetchApiKeyStatus()
    }
  }, [user])

  // Fetch Gmail settings
  const fetchGmailSettings = async () => {
    if (!user) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/system-settings`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && data.data) {
        if (data.data.gmail_email) {
          setGmailEmail(data.data.gmail_email)
          setGmailConfigured(true)
        }
        if (data.data.gmail_app_password) {
          setGmailConfigured(true)
        }
      }
    } catch (err) {
      console.error('Failed to fetch Gmail settings:', err)
    }
  }

  // Save Gmail settings
  const handleSaveGmail = async () => {
    if (!user) return
    setIsSavingGmail(true)
    setGmailMessage(null)

    try {
      const payload: Record<string, string> = {}
      if (gmailEmail) payload.gmail_email = gmailEmail
      if (gmailAppPassword) payload.gmail_app_password = gmailAppPassword

      const res = await fetch(`${API_BASE_URL}/api/supabase/system-settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      if (data.success) {
        setGmailMessage({ type: 'success', text: 'Gmail credentials saved successfully!' })
        setGmailConfigured(true)
        setGmailAppPassword('') // Clear password after saving
        setTimeout(() => setGmailMessage(null), 5000)
      } else {
        setGmailMessage({ type: 'error', text: data.error || 'Failed to save Gmail credentials' })
      }
    } catch (err) {
      setGmailMessage({ type: 'error', text: 'Failed to save Gmail credentials' })
    } finally {
      setIsSavingGmail(false)
    }
  }

  // Fetch FUB API key status
  const fetchApiKeyStatus = async () => {
    if (!user) return
    try {
      const supabase = createClient()
      const { data: userData } = await supabase.from('users').select('fub_api_key').eq('id', user.id).single()
      if (userData) {
        setFubApiKeyConfigured(!!userData.fub_api_key)
      }
    } catch (err) {
      console.error('Failed to fetch API key status:', err)
    }
  }

  // Save FUB API key
  const handleSaveApiKey = async () => {
    if (!user || !fubApiKey) return
    setIsSavingApiKey(true)
    setApiKeyMessage(null)

    try {
      const supabase = createClient()
      const { data: sessionData } = await supabase.auth.getSession()
      const token = sessionData.session?.access_token

      if (!token) {
        setApiKeyMessage({ type: 'error', text: 'Session expired. Please refresh the page.' })
        return
      }

      const res = await fetch(`${API_BASE_URL}/api/supabase/users/current/profile/api-key`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ fub_api_key: fubApiKey })
      })
      const data = await res.json()
      if (data.success) {
        setApiKeyMessage({ type: 'success', text: 'FUB API key saved successfully!' })
        setFubApiKeyConfigured(true)
        setFubApiKey('') // Clear after saving
        setTimeout(() => setApiKeyMessage(null), 5000)
      } else {
        setApiKeyMessage({ type: 'error', text: data.error || 'Failed to save API key' })
      }
    } catch (err) {
      setApiKeyMessage({ type: 'error', text: 'Failed to save FUB API key' })
    } finally {
      setIsSavingApiKey(false)
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
        <TabsList className="grid w-full grid-cols-5">
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
          <TabsTrigger value="credentials" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Credentials
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
                  <Label htmlFor="brokerage_name">Brokerage/Team Name</Label>
                  <Input
                    id="brokerage_name"
                    value={settings.brokerage_name}
                    onChange={(e) => setSettings({ ...settings, brokerage_name: e.target.value })}
                    placeholder="The Schwartz Team at Coldwell Banker"
                  />
                  <p className="text-xs text-muted-foreground">
                    Your team/company name included in messages
                  </p>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="team_members">Human Agent Names</Label>
                  <Input
                    id="team_members"
                    value={settings.team_members}
                    onChange={(e) => setSettings({ ...settings, team_members: e.target.value })}
                    placeholder="Adam and Mandi"
                  />
                  <p className="text-xs text-muted-foreground">
                    Names of the human agents the AI works with (helps AI personalize context)
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

            {/* AI Model Selection Card */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5" />
                  AI Model
                </CardTitle>
                <CardDescription>Choose which AI model powers your agent</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label>Primary Model</Label>
                  <Select
                    value={settings.llm_model}
                    onValueChange={(value) => setSettings({ ...settings, llm_model: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {LLM_MODEL_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          <div className="flex flex-col">
                            <span className="font-medium">{option.label}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    {LLM_MODEL_OPTIONS.find(m => m.value === settings.llm_model)?.description}
                  </p>
                </div>

                <div className="grid gap-2">
                  <Label>Fallback Model</Label>
                  <Select
                    value={settings.llm_model_fallback}
                    onValueChange={(value) => setSettings({ ...settings, llm_model_fallback: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {LLM_MODEL_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          <div className="flex flex-col">
                            <span className="font-medium">{option.label}</span>
                          </div>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Used if the primary model is unavailable
                  </p>
                </div>

                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800">
                  <p className="text-xs text-blue-700 dark:text-blue-300">
                    All models are free tier from OpenRouter. Some models may require enabling data sharing in your OpenRouter settings.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Behavior Tab */}
        <TabsContent value="behavior">
          <div className="grid gap-6 md:grid-cols-2">
            {/* New Lead Settings Card - Full Width */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Users className="h-5 w-5" />
                  New Lead Settings
                </CardTitle>
                <CardDescription>Configure how AI handles newly created leads</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg border bg-muted/30">
                  <div className="space-y-1">
                    <Label htmlFor="auto_enable_new_leads" className="text-base font-medium">
                      Auto-enable AI for new leads
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      When enabled, AI will automatically start engaging with new leads as they come in from FUB.
                      When disabled, you must manually enable AI for each lead (via FUB "AI Follow-up" tag or dashboard).
                    </p>
                  </div>
                  <Switch
                    id="auto_enable_new_leads"
                    checked={settings.auto_enable_new_leads}
                    onCheckedChange={(checked) => setSettings({ ...settings, auto_enable_new_leads: checked })}
                  />
                </div>
                {!settings.auto_enable_new_leads && (
                  <Alert>
                    <Users className="h-4 w-4" />
                    <AlertDescription>
                      <strong>Manual opt-in mode:</strong> New leads will NOT receive AI messages until you add the "AI Follow-up" tag in FUB or enable them in the LeadSynergy dashboard.
                    </AlertDescription>
                  </Alert>
                )}
              </CardContent>
            </Card>

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

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Bell className="h-5 w-5" />
                  Agent Notifications
                </CardTitle>
                <CardDescription>Get instant SMS alerts when hot leads are detected</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="notification_person_id">Notification Lead ID (FUB Person ID)</Label>
                  <Input
                    id="notification_person_id"
                    type="text"
                    value={settings.notification_fub_person_id || ''}
                    onChange={(e) => {
                      let value = e.target.value
                      // Extract person ID from FUB URL if pasted
                      // Handles: https://saahomes.followupboss.com/2/people/view/3296
                      // Or: app.followupboss.com/app/people/12345678
                      const urlMatch = value.match(/people\/(?:view\/)?(\d+)/)
                      if (urlMatch) {
                        value = urlMatch[1]
                      }
                      // Only allow numbers
                      const numericValue = value.replace(/\D/g, '')
                      setSettings({
                        ...settings,
                        notification_fub_person_id: numericValue ? parseInt(numericValue) : null
                      })
                    }}
                    placeholder="e.g., 12345678 or paste FUB URL"
                  />
                  <p className="text-xs text-muted-foreground">
                    Enter the FUB Person ID or paste the full FUB URL - the ID will be extracted automatically
                  </p>
                </div>

                <Alert>
                  <Bell className="h-4 w-4" />
                  <AlertDescription>
                    <strong>How to set up instant notifications:</strong>
                    <ol className="mt-2 ml-4 space-y-1 list-decimal text-sm">
                      <li>Create a lead in FUB named "LeadSynergy Alerts" (or similar)</li>
                      <li>Set the phone number to your cell phone</li>
                      <li>Copy that lead's Person ID from the FUB URL (e.g., <code className="bg-muted px-1 rounded">app.followupboss.com/app/people/<strong>12345678</strong></code>)</li>
                      <li>Paste the ID above</li>
                    </ol>
                    <p className="mt-2 text-sm">
                      When a hot lead is detected, you'll receive an SMS instantly through FUB!
                    </p>
                  </AlertDescription>
                </Alert>
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

        {/* Credentials Tab - All API keys and login credentials in one place */}
        <TabsContent value="credentials">
          <div className="space-y-6">
            {/* FUB API Key Section */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Key className="h-5 w-5" />
                      Follow Up Boss API Key
                    </CardTitle>
                    <CardDescription>
                      Required for lead synchronization, webhooks, and data access
                    </CardDescription>
                  </div>
                  <Badge variant={fubApiKeyConfigured ? "default" : "secondary"}>
                    {fubApiKeyConfigured ? "Configured" : "Not Configured"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {apiKeyMessage && (
                  <Alert className={apiKeyMessage.type === 'success' ? 'bg-green-50 border-green-200' : ''} variant={apiKeyMessage.type === 'error' ? 'destructive' : 'default'}>
                    {apiKeyMessage.type === 'success' ? <CheckCircle className="h-4 w-4 text-green-600" /> : <AlertTriangle className="h-4 w-4" />}
                    <AlertDescription className={apiKeyMessage.type === 'success' ? 'text-green-800' : ''}>{apiKeyMessage.text}</AlertDescription>
                  </Alert>
                )}
                <div className="grid gap-2">
                  <Label htmlFor="fub-api-key">FUB API Key</Label>
                  <div className="relative">
                    <Input
                      id="fub-api-key"
                      type={showApiKey ? "text" : "password"}
                      value={fubApiKey}
                      onChange={(e) => setFubApiKey(e.target.value)}
                      placeholder={fubApiKeyConfigured ? "Enter new API key to update" : "Enter your Follow Up Boss API key"}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                      onClick={() => setShowApiKey(!showApiKey)}
                    >
                      {showApiKey ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-muted-foreground" />}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Find your API key in FUB under Admin → API
                  </p>
                </div>
                <Button onClick={handleSaveApiKey} disabled={isSavingApiKey || !fubApiKey}>
                  {isSavingApiKey ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Saving...</> : 'Save API Key'}
                </Button>
              </CardContent>
            </Card>

            <Separator />

            {/* Gmail Credentials Section */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Mail className="h-5 w-5" />
                      Gmail IMAP Access
                    </CardTitle>
                    <CardDescription>
                      Used to automatically retrieve FUB verification emails and 2FA codes
                    </CardDescription>
                  </div>
                  <Badge variant={gmailConfigured ? "default" : "secondary"}>
                    {gmailConfigured ? "Configured" : "Not Configured"}
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {gmailMessage && (
                  <Alert className={gmailMessage.type === 'success' ? 'bg-green-50 border-green-200' : ''} variant={gmailMessage.type === 'error' ? 'destructive' : 'default'}>
                    {gmailMessage.type === 'success' ? <CheckCircle className="h-4 w-4 text-green-600" /> : <AlertTriangle className="h-4 w-4" />}
                    <AlertDescription className={gmailMessage.type === 'success' ? 'text-green-800' : ''}>{gmailMessage.text}</AlertDescription>
                  </Alert>
                )}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="gmail-email">Gmail Email Address</Label>
                    <Input
                      id="gmail-email"
                      type="email"
                      value={gmailEmail}
                      onChange={(e) => setGmailEmail(e.target.value)}
                      placeholder="your-email@gmail.com"
                    />
                    <p className="text-xs text-muted-foreground">
                      The Gmail that receives FUB security emails
                    </p>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="gmail-app-password">
                      Google App Password
                      {gmailConfigured && <span className="ml-2 text-xs text-green-600 font-normal">(saved)</span>}
                    </Label>
                    <div className="relative">
                      <Input
                        id="gmail-app-password"
                        type={showGmailPassword ? "text" : "password"}
                        value={gmailAppPassword}
                        onChange={(e) => setGmailAppPassword(e.target.value)}
                        placeholder={gmailConfigured ? "••••••••••••" : "xxxx xxxx xxxx xxxx"}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                        onClick={() => setShowGmailPassword(!showGmailPassword)}
                      >
                        {showGmailPassword ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-muted-foreground" />}
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      <a href="https://myaccount.google.com/apppasswords" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                        Generate an App Password
                      </a>
                      {" "}(not your regular password)
                    </p>
                  </div>
                </div>
                <Alert>
                  <Mail className="h-4 w-4" />
                  <AlertDescription>
                    <strong>Why is this needed?</strong>
                    <p className="mt-1 text-sm">
                      When FUB detects a login from a new location (like our server), it sends a verification email.
                      We use Gmail IMAP to automatically read these emails and complete the login process.
                    </p>
                  </AlertDescription>
                </Alert>
                <Button onClick={handleSaveGmail} disabled={isSavingGmail || (!gmailEmail && !gmailAppPassword)}>
                  {isSavingGmail ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Saving...</> : 'Save Gmail Credentials'}
                </Button>
              </CardContent>
            </Card>

            <Separator />

            {/* FUB Browser Login Section */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Send className="h-5 w-5" />
                  FUB Browser Login (for SMS Sending)
                </CardTitle>
                <CardDescription>
                  Your FUB login credentials to enable AI-powered SMS sending via browser automation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {fubLoginMessage && (
                  <Alert className={fubLoginMessage.type === 'success' ? 'bg-green-50 border-green-200' : ''} variant={fubLoginMessage.type === 'error' ? 'destructive' : 'default'}>
                    {fubLoginMessage.type === 'success' ? <CheckCircle className="h-4 w-4 text-green-600" /> : <AlertTriangle className="h-4 w-4" />}
                    <AlertDescription className={fubLoginMessage.type === 'success' ? 'text-green-800' : ''}>{fubLoginMessage.text}</AlertDescription>
                  </Alert>
                )}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-4">
                    <div className="grid gap-2">
                      <Label htmlFor="fub_login_type">Login Method</Label>
                      <Select
                        value={fubLogin.fub_login_type}
                        onValueChange={(value: 'email' | 'google' | 'microsoft') => setFubLogin({ ...fubLogin, fub_login_type: value })}
                      >
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent>
                          <SelectItem value="email">Email & Password</SelectItem>
                          <SelectItem value="google">Google SSO</SelectItem>
                          <SelectItem value="microsoft">Microsoft SSO</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="fub_login_email">FUB Login Email</Label>
                      <Input
                        id="fub_login_email"
                        type="email"
                        value={fubLogin.fub_login_email}
                        onChange={(e) => setFubLogin({ ...fubLogin, fub_login_email: e.target.value })}
                        placeholder="your@email.com"
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="fub_login_password">
                        FUB Password
                        {fubLogin.has_password && <span className="ml-2 text-xs text-green-600 font-normal">(saved)</span>}
                      </Label>
                      <div className="relative">
                        <Input
                          id="fub_login_password"
                          type={showPassword ? "text" : "password"}
                          value={fubLogin.fub_login_password}
                          onChange={(e) => setFubLogin({ ...fubLogin, fub_login_password: e.target.value })}
                          placeholder={fubLogin.has_password ? "••••••••••••" : "Enter password"}
                        />
                        <Button type="button" variant="ghost" size="sm" className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent" onClick={() => setShowPassword(!showPassword)}>
                          {showPassword ? <EyeOff className="h-4 w-4 text-muted-foreground" /> : <Eye className="h-4 w-4 text-muted-foreground" />}
                        </Button>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {fubLogin.has_password ? "Leave blank to keep existing, or enter new" : "Your FUB account password"}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <Alert>
                      <Key className="h-4 w-4" />
                      <AlertDescription>
                        <strong>Why is this needed?</strong>
                        <p className="mt-1 text-sm">
                          FUB's API doesn't send SMS - we use browser automation to send real texts through the FUB web interface.
                        </p>
                      </AlertDescription>
                    </Alert>
                    <div className="flex gap-2 pt-4">
                      <Button onClick={handleSaveFubLogin} disabled={isSavingFubLogin || !fubLogin.fub_login_email}>
                        {isSavingFubLogin ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Saving...</> : 'Save FUB Login'}
                      </Button>
                      <Button variant="outline" onClick={handleTestFubLogin} disabled={isTestingFubLogin || (!fubLogin.has_password && !fubLogin.fub_login_password)}>
                        {isTestingFubLogin ? <><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Testing...</> : <><Send className="mr-2 h-4 w-4" />Test Login</>}
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
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
