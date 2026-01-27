"use client"

import type React from "react"
import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Alert, AlertDescription } from "@/components/ui/alert"
import {
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  MessageSquare,
  Users,
  Calendar,
  Clock,
  CheckCircle2,
  XCircle,
  BarChart3,
  Activity,
  Target,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"
import { AIActivityFeed, LeadAIPanel } from "@/components/ai-monitor"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"

interface MetricsSummary {
  total_conversations: number
  total_messages: number
  unique_leads: number
  response_rate: number
  qualification_rate: number
  appointment_rate: number
  handoff_rate: number
  optout_rate: number
  avg_lead_score: number
  avg_response_time_minutes: number
}

interface ConversionFunnel {
  total_leads: number
  contacted: number
  responded: number
  qualified: number
  scheduled: number
  appointments_booked: number
  conversion_rate: number
}

interface DailyMetric {
  date: string
  conversations: number
  messages_sent: number
  responses_received: number
  appointments: number
}

interface ABTestResult {
  template_id: string
  template_category: string
  variant_name: string
  total_sent: number
  responses: number
  response_rate: number
  appointments: number
  appointment_rate: number
  optouts: number
  optout_rate: number
}

interface IntentDistribution {
  intent: string
  count: number
  percentage: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AIAnalyticsPage() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [period, setPeriod] = useState<string>("30d")

  const [summary, setSummary] = useState<MetricsSummary | null>(null)
  const [funnel, setFunnel] = useState<ConversionFunnel | null>(null)
  const [dailyMetrics, setDailyMetrics] = useState<DailyMetric[]>([])
  const [abTests, setAbTests] = useState<ABTestResult[]>([])
  const [intents, setIntents] = useState<IntentDistribution[]>([])
  const [reviewQueue, setReviewQueue] = useState<any[]>([])
  const [reviewCounts, setReviewCounts] = useState<any>({})
  const [selectedPersonId, setSelectedPersonId] = useState<number | null>(null)
  const [isMonitorPanelOpen, setIsMonitorPanelOpen] = useState(false)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  const fetchAnalytics = useCallback(async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/ai-analytics/dashboard?period=${period}`, {
        headers: { 'X-User-ID': user.id }
      })

      const data = await response.json()

      if (data.success) {
        setSummary(data.summary || null)
        setFunnel(data.funnel || null)
        setDailyMetrics(data.daily_metrics || [])
        setAbTests(data.ab_tests || [])
        setIntents(data.intents || [])
      } else {
        setError(data.error || 'Failed to load analytics')
      }
    } catch (err) {
      setError('Failed to fetch analytics data')
      console.error('Analytics fetch error:', err)
    } finally {
      setIsLoading(false)
    }
  }, [user, period])

  const fetchReviewQueue = useCallback(async () => {
    if (!user) return
    try {
      const response = await fetch(`${API_BASE_URL}/api/ai-monitoring/review-queue`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await response.json()
      if (data.success) {
        setReviewQueue(data.review_queue || [])
        setReviewCounts(data.counts || {})
      }
    } catch (err) {
      console.error('Failed to fetch review queue:', err)
    }
  }, [user])

  useEffect(() => {
    if (user) {
      fetchAnalytics()
      fetchReviewQueue()
    }
  }, [user, period, fetchAnalytics, fetchReviewQueue])

  const openLeadMonitor = (personId: number) => {
    setSelectedPersonId(personId)
    setIsMonitorPanelOpen(true)
  }

  const MetricCard = ({
    title,
    value,
    subtitle,
    icon: Icon,
    trend,
    trendLabel,
    className = "",
  }: {
    title: string
    value: string | number
    subtitle?: string
    icon: React.ElementType
    trend?: number
    trendLabel?: string
    className?: string
  }) => (
    <Card className={className}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold mt-1">{value}</p>
            {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
          </div>
          <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
            <Icon className="h-5 w-5 text-primary" />
          </div>
        </div>
        {trend !== undefined && (
          <div className="flex items-center gap-1 mt-3 text-sm">
            {trend >= 0 ? (
              <ArrowUpRight className="h-4 w-4 text-green-500" />
            ) : (
              <ArrowDownRight className="h-4 w-4 text-red-500" />
            )}
            <span className={trend >= 0 ? "text-green-500" : "text-red-500"}>
              {Math.abs(trend)}%
            </span>
            {trendLabel && <span className="text-muted-foreground">{trendLabel}</span>}
          </div>
        )}
      </CardContent>
    </Card>
  )

  const FunnelBar = ({
    label,
    count,
    maxCount,
    color,
  }: {
    label: string
    count: number
    maxCount: number
    color: string
  }) => {
    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0
    return (
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span>{label}</span>
          <span className="font-medium">{count.toLocaleString()}</span>
        </div>
        <div className="h-3 bg-muted rounded-full overflow-hidden">
          <div
            className={`h-full ${color} rounded-full transition-all duration-500`}
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>
    )
  }

  if (isLoading && !summary) {
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
            <BarChart3 className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">AI Agent Analytics</h1>
            <p className="text-muted-foreground">Track AI performance and conversion metrics</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="outline" onClick={fetchAnalytics} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Key Metrics */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mb-8">
        <MetricCard
          title="Total Conversations"
          value={summary?.total_conversations?.toLocaleString() || "0"}
          subtitle={`${summary?.unique_leads || 0} unique leads`}
          icon={MessageSquare}
        />
        <MetricCard
          title="Response Rate"
          value={`${summary?.response_rate?.toFixed(1) || 0}%`}
          subtitle="Leads that replied"
          icon={Activity}
        />
        <MetricCard
          title="Appointment Rate"
          value={`${summary?.appointment_rate?.toFixed(1) || 0}%`}
          subtitle="Leads that booked"
          icon={Calendar}
        />
        <MetricCard
          title="Avg Lead Score"
          value={summary?.avg_lead_score?.toFixed(0) || "0"}
          subtitle="Out of 100"
          icon={Target}
        />
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="monitor" className="relative">
            Monitor
            {reviewCounts.total > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 px-1.5 text-xs">
                {reviewCounts.total}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="funnel">Conversion Funnel</TabsTrigger>
          <TabsTrigger value="abtests">A/B Tests</TabsTrigger>
          <TabsTrigger value="intents">Intent Analysis</TabsTrigger>
        </TabsList>

        {/* Monitor Tab */}
        <TabsContent value="monitor" className="space-y-6">
          {/* Activity Feed */}
          <AIActivityFeed
            userId={user?.id}
            onLeadClick={openLeadMonitor}
            defaultOpen={true}
          />

          {/* Review Queue */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Review Queue
              </CardTitle>
              <CardDescription>
                Leads requiring attention: {reviewCounts.escalated || 0} escalated, {reviewCounts.pending_notes || 0} with pending notes
              </CardDescription>
            </CardHeader>
            <CardContent>
              {reviewQueue.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <CheckCircle2 className="h-8 w-8 mb-2 opacity-50" />
                  <p>No leads require review</p>
                  <p className="text-xs mt-1">All AI conversations are running smoothly</p>
                </div>
              ) : (
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {reviewQueue.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-3 rounded-lg border bg-card hover:bg-muted/50 cursor-pointer transition-colors"
                        onClick={() => openLeadMonitor(item.person_id)}
                      >
                        <div className="flex items-center gap-3">
                          <div className={`w-2 h-2 rounded-full ${
                            item.priority === 'high' ? 'bg-red-500' :
                            item.priority === 'medium' ? 'bg-yellow-500' : 'bg-gray-400'
                          }`} />
                          <div>
                            <p className="font-medium text-sm">Person #{item.person_id}</p>
                            <p className="text-xs text-muted-foreground">{item.reason}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant={item.type === 'escalated' ? 'destructive' : 'secondary'}>
                            {item.type === 'escalated' ? 'Escalated' : 'Pending Notes'}
                          </Badge>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              openLeadMonitor(item.person_id)
                            }}
                          >
                            View
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </CardContent>
          </Card>

          {/* Quick Stats */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-red-100 flex items-center justify-center">
                    <AlertTriangle className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reviewCounts.escalated || 0}</p>
                    <p className="text-xs text-muted-foreground">Escalated</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-yellow-100 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-yellow-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reviewCounts.pending_notes || 0}</p>
                    <p className="text-xs text-muted-foreground">Pending Notes</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-blue-100 flex items-center justify-center">
                    <Users className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="text-2xl font-bold">{reviewCounts.total || 0}</p>
                    <p className="text-xs text-muted-foreground">Total in Queue</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Performance Metrics</CardTitle>
                <CardDescription>Key conversion and engagement rates</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="h-4 w-4 text-green-500" />
                      <span className="text-sm">Qualification Rate</span>
                    </div>
                    <span className="font-medium">{summary?.qualification_rate?.toFixed(1) || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-blue-500" />
                      <span className="text-sm">Handoff Rate</span>
                    </div>
                    <span className="font-medium">{summary?.handoff_rate?.toFixed(1) || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <XCircle className="h-4 w-4 text-red-500" />
                      <span className="text-sm">Opt-out Rate</span>
                    </div>
                    <span className="font-medium">{summary?.optout_rate?.toFixed(1) || 0}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Clock className="h-4 w-4 text-orange-500" />
                      <span className="text-sm">Avg Response Time</span>
                    </div>
                    <span className="font-medium">{summary?.avg_response_time_minutes?.toFixed(1) || 0} min</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Message Volume</CardTitle>
                <CardDescription>Total messages sent by AI agent</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-center h-48">
                  <div className="text-center">
                    <p className="text-5xl font-bold">{summary?.total_messages?.toLocaleString() || 0}</p>
                    <p className="text-muted-foreground mt-2">Total Messages Sent</p>
                    <p className="text-sm text-muted-foreground">
                      {summary?.total_conversations
                        ? `~${(summary.total_messages / summary.total_conversations).toFixed(1)} per conversation`
                        : ''}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Daily Activity Chart Placeholder */}
          <Card>
            <CardHeader>
              <CardTitle>Daily Activity</CardTitle>
              <CardDescription>Messages and conversations over time</CardDescription>
            </CardHeader>
            <CardContent>
              {dailyMetrics.length > 0 ? (
                <div className="space-y-4">
                  {dailyMetrics.slice(-7).map((day) => (
                    <div key={day.date} className="flex items-center gap-4">
                      <span className="text-sm w-24 text-muted-foreground">
                        {new Date(day.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
                      </span>
                      <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary/60 rounded-full"
                          style={{ width: `${Math.min((day.messages_sent / Math.max(...dailyMetrics.map(d => d.messages_sent), 1)) * 100, 100)}%` }}
                        />
                      </div>
                      <span className="text-sm font-medium w-16 text-right">{day.messages_sent}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-48 text-muted-foreground">
                  <p>No daily data available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Funnel Tab */}
        <TabsContent value="funnel">
          <Card>
            <CardHeader>
              <CardTitle>Conversion Funnel</CardTitle>
              <CardDescription>Track leads through the sales process</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {funnel ? (
                <>
                  <div className="space-y-4">
                    <FunnelBar
                      label="Total Leads"
                      count={funnel.total_leads}
                      maxCount={funnel.total_leads}
                      color="bg-blue-500"
                    />
                    <FunnelBar
                      label="Contacted by AI"
                      count={funnel.contacted}
                      maxCount={funnel.total_leads}
                      color="bg-indigo-500"
                    />
                    <FunnelBar
                      label="Responded"
                      count={funnel.responded}
                      maxCount={funnel.total_leads}
                      color="bg-violet-500"
                    />
                    <FunnelBar
                      label="Qualified"
                      count={funnel.qualified}
                      maxCount={funnel.total_leads}
                      color="bg-purple-500"
                    />
                    <FunnelBar
                      label="Scheduling"
                      count={funnel.scheduled}
                      maxCount={funnel.total_leads}
                      color="bg-fuchsia-500"
                    />
                    <FunnelBar
                      label="Appointments Booked"
                      count={funnel.appointments_booked}
                      maxCount={funnel.total_leads}
                      color="bg-green-500"
                    />
                  </div>
                  <div className="pt-4 border-t">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">Overall Conversion Rate</span>
                      <span className="text-2xl font-bold text-green-500">
                        {funnel.conversion_rate?.toFixed(1) || 0}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      From first contact to appointment booked
                    </p>
                  </div>
                </>
              ) : (
                <div className="flex items-center justify-center h-48 text-muted-foreground">
                  <p>No funnel data available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* A/B Tests Tab */}
        <TabsContent value="abtests">
          <Card>
            <CardHeader>
              <CardTitle>A/B Test Results</CardTitle>
              <CardDescription>Compare performance of different message variants</CardDescription>
            </CardHeader>
            <CardContent>
              {abTests.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-2 text-sm font-medium">Template</th>
                        <th className="text-left py-3 px-2 text-sm font-medium">Variant</th>
                        <th className="text-right py-3 px-2 text-sm font-medium">Sent</th>
                        <th className="text-right py-3 px-2 text-sm font-medium">Response Rate</th>
                        <th className="text-right py-3 px-2 text-sm font-medium">Appt Rate</th>
                        <th className="text-right py-3 px-2 text-sm font-medium">Opt-out Rate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {abTests.map((test, idx) => (
                        <tr key={idx} className="border-b last:border-0">
                          <td className="py-3 px-2 text-sm">{test.template_id}</td>
                          <td className="py-3 px-2 text-sm">{test.variant_name}</td>
                          <td className="py-3 px-2 text-sm text-right">{test.total_sent}</td>
                          <td className="py-3 px-2 text-sm text-right">
                            <span className={test.response_rate > 30 ? "text-green-500" : ""}>
                              {test.response_rate?.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-3 px-2 text-sm text-right">
                            <span className={test.appointment_rate > 10 ? "text-green-500" : ""}>
                              {test.appointment_rate?.toFixed(1)}%
                            </span>
                          </td>
                          <td className="py-3 px-2 text-sm text-right">
                            <span className={test.optout_rate > 5 ? "text-red-500" : ""}>
                              {test.optout_rate?.toFixed(1)}%
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                  <Zap className="h-8 w-8 mb-2 opacity-50" />
                  <p>No A/B test data available yet</p>
                  <p className="text-xs mt-1">Results will appear after messages are sent using templates</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Intent Analysis Tab */}
        <TabsContent value="intents">
          <Card>
            <CardHeader>
              <CardTitle>Intent Distribution</CardTitle>
              <CardDescription>What leads are asking about</CardDescription>
            </CardHeader>
            <CardContent>
              {intents.length > 0 ? (
                <div className="space-y-4">
                  {intents.map((intent) => (
                    <div key={intent.intent} className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="capitalize">{intent.intent.replace(/_/g, ' ')}</span>
                        <span className="text-muted-foreground">
                          {intent.count} ({intent.percentage?.toFixed(1)}%)
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full"
                          style={{ width: `${intent.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-muted-foreground">
                  <TrendingUp className="h-8 w-8 mb-2 opacity-50" />
                  <p>No intent data available yet</p>
                  <p className="text-xs mt-1">Intent distribution will appear after AI conversations</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Lead AI Monitor Panel */}
      <LeadAIPanel
        personId={selectedPersonId}
        isOpen={isMonitorPanelOpen}
        onClose={() => {
          setIsMonitorPanelOpen(false)
          setSelectedPersonId(null)
        }}
        userId={user?.id}
      />
    </SidebarWrapper>
  )
}
