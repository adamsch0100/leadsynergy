"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Progress } from "@/components/ui/progress"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Building2,
  Clock,
  CreditCard,
  Link2,
  RefreshCw,
  Shield,
  SplitSquareHorizontal,
  Users,
  TrendingUp,
  DollarSign
} from "lucide-react"
import { useSubscription } from "@/contexts/subscription-context"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface Lead {
  id: string
  first_name: string
  last_name: string
  source: string
  email: string
  created_at: string
  updated_at: string
  status: string
  price: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AdminDashboard() {
  const { subscription } = useSubscription()
  const [leads, setLeads] = useState<Lead[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [user, setUser] = useState<User | null>(null)
  const [commissionRate, setCommissionRate] = useState(0.03) // Default 3%

  const daysUntilTrialEnds = subscription.trialEndsAt
    ? Math.ceil((subscription.trialEndsAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
    : 0

  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  useEffect(() => {
    if (user) {
      fetchLeads()
      fetchCommissionRate()
    }
  }, [user])

  const fetchCommissionRate = async () => {
    if (!user) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/settings/commission-rate`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && data.data?.commission_rate !== undefined) {
        setCommissionRate(data.data.commission_rate)
      }
    } catch (err) {
      console.error('Failed to fetch commission rate:', err)
    }
  }

  const fetchLeads = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/leads?limit=2000`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && Array.isArray(data.data)) {
        setLeads(data.data)
      }
    } catch (err) {
      console.error('Failed to fetch leads:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const getStageColor = (stageName: string) => {
    const name = stageName?.toLowerCase() || ''
    if (name.includes('lead') || name.includes('new')) return "bg-blue-50 text-blue-700 border-blue-200"
    if (name.includes('hot') || name.includes('a -')) return "bg-red-50 text-red-700 border-red-200"
    if (name.includes('warm') || name.includes('b -')) return "bg-yellow-50 text-yellow-700 border-yellow-200"
    if (name.includes('active') || name.includes('client')) return "bg-green-50 text-green-700 border-green-200"
    if (name.includes('pending')) return "bg-purple-50 text-purple-700 border-purple-200"
    return "bg-gray-50 text-gray-700 border-gray-200"
  }

  // Get recent leads (last 5)
  const recentLeads = [...leads]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 5)

  // Calculate stats - commission value is price * commission rate
  const totalCommissionValue = leads.reduce((sum, l) => sum + ((l.price || 0) * commissionRate), 0)
  const uniqueSources = new Set(leads.map(l => l.source).filter(Boolean)).size

  return (
    <SidebarWrapper role="admin">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Admin Dashboard</h1>
          <p className="text-muted-foreground">Manage your referral system settings and monitor performance</p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchLeads} disabled={isLoading}>
          <RefreshCw className={`h-5 w-5 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="sr-only">Refresh data</span>
        </Button>
      </div>

      {subscription.trialEndsAt && daysUntilTrialEnds > 0 && (
        <Alert className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            Your free trial ends in {daysUntilTrialEnds} days.{" "}
            {subscription.plan === "free" && (
              <Button variant="link" className="h-auto p-0" asChild>
                <Link href="/pricing">Upgrade now</Link>
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{leads.length}</div>
            <p className="text-xs text-muted-foreground">From {uniqueSources} sources</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Commission Value</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${totalCommissionValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}</div>
            <p className="text-xs text-muted-foreground">At {(commissionRate * 100).toFixed(1)}% commission</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Sources</CardTitle>
            <Link2 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{uniqueSources}</div>
            <p className="text-xs text-muted-foreground">Lead sources in use</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Plan</CardTitle>
            <CreditCard className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold capitalize">{subscription.plan}</div>
            <Button variant="link" className="h-auto p-0 text-xs" asChild>
              <Link href="/admin/billing">Manage Plan</Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Recent Leads */}
      <Card className="mb-8">
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Recent Leads</CardTitle>
            <CardDescription>Latest leads from Follow Up Boss</CardDescription>
          </div>
          <Button variant="outline" size="sm" asChild>
            <Link href="/admin/leads">View All Leads</Link>
          </Button>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : recentLeads.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No leads yet. Import leads from Follow Up Boss in Lead Sources.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Commission</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recentLeads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell className="font-medium">
                      <div>{lead.first_name} {lead.last_name}</div>
                      <div className="text-xs text-muted-foreground">{lead.email}</div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{lead.source || 'Unknown'}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={getStageColor(lead.status)}>
                        {lead.status || 'Unknown'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{formatDate(lead.created_at)}</TableCell>
                    <TableCell>{lead.price > 0 ? `$${(lead.price * commissionRate).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Feature Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {features.map((feature) => (
          <Link key={feature.title} href={feature.href}>
            <Card className="h-full transition-all hover:shadow-md">
              <CardHeader className="pb-2">
                <div className="mb-4 h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <feature.icon className="h-6 w-6 text-primary" />
                </div>
                <CardTitle>{feature.title}</CardTitle>
                <CardDescription>{feature.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">{feature.content}</p>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </SidebarWrapper>
  )
}

const features = [
  {
    icon: Link2,
    title: "Lead Sources",
    description: "Manage your lead sources",
    content: "Add, edit, and configure the various sources from which you receive real estate referrals.",
    href: "/admin/lead-sources",
  },
  {
    icon: BarChart3,
    title: "Stage Mapping",
    description: "Configure lead stage mappings",
    content: "Map lead source stages to your internal workflow for consistent tracking and reporting.",
    href: "/admin/stage-mapping",
  },
  {
    icon: Users,
    title: "Team Management",
    description: "Manage your team members",
    content: "Add agents, set permissions, and organize your team for optimal referral handling.",
    href: "/admin/team",
  },
  {
    icon: Shield,
    title: "System Settings",
    description: "Configure system-wide settings",
    content: "Manage core system configurations, security settings, and global preferences.",
    href: "/admin/system",
  },
]
