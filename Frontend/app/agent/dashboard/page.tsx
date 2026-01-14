"use client"

import { useState, useEffect } from "react"
import { BarChart3, Clock, DollarSign, RefreshCw, Users, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"
import Link from "next/link"

interface Lead {
  id: string
  first_name: string
  last_name: string
  source: string
  phone: string
  email: string
  created_at: string
  updated_at: string
  stage_id: string
  status: string
  fub_person_id: string
  price: number
}

interface FUBStage {
  id: string
  name: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AgentDashboard() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [fubStages, setFubStages] = useState<FUBStage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      try {
        const supabase = createClient()
        const { data, error: authError } = await supabase.auth.getUser()
        if (authError) {
          setError('Unable to load user session')
          setUser(null)
        } else {
          setUser(data.user ?? null)
        }
      } catch (err) {
        setError('Unable to load user session')
      } finally {
        setAuthLoading(false)
      }
    }
    loadUser()
  }, [])

  // Fetch data
  useEffect(() => {
    if (!authLoading && user) {
      fetchData()
    }
  }, [authLoading, user])

  const fetchData = async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)

    try {
      const [leadsRes, stagesRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/supabase/leads?limit=2000`, {
          headers: { 'X-User-ID': user.id }
        }),
        fetch(`${API_BASE_URL}/api/supabase/fub-stages`)
      ])

      const leadsData = await leadsRes.json()
      const stagesData = await stagesRes.json()

      if (leadsData.success && Array.isArray(leadsData.data)) {
        setLeads(leadsData.data)
      }
      if (stagesData.success && Array.isArray(stagesData.data)) {
        setFubStages(stagesData.data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setIsLoading(false)
    }
  }

  // Calculate stats from real data
  const stats = [
    {
      title: "Total Leads",
      value: leads.length.toString(),
      description: "Total leads in your database",
      icon: Users,
    },
    {
      title: "New Leads",
      value: leads.filter(l => l.status?.toLowerCase().includes('lead') || l.stage_id === '2').length.toString(),
      description: "Leads in 'Lead' stage",
      icon: Clock,
    },
    {
      title: "Active Clients",
      value: leads.filter(l => l.status?.toLowerCase().includes('active') || l.stage_id === '12').length.toString(),
      description: "Active client engagements",
      icon: BarChart3,
    },
    {
      title: "Total Value",
      value: `$${leads.reduce((sum, l) => sum + (l.price || 0), 0).toLocaleString()}`,
      description: "Combined lead values",
      icon: DollarSign,
    },
  ]

  const getStageColor = (stageName: string) => {
    const name = stageName?.toLowerCase() || ''
    if (name.includes('lead') || name.includes('new')) return "bg-blue-50 text-blue-700 border-blue-200"
    if (name.includes('hot') || name.includes('a -')) return "bg-red-50 text-red-700 border-red-200"
    if (name.includes('warm') || name.includes('b -')) return "bg-yellow-50 text-yellow-700 border-yellow-200"
    if (name.includes('cold') || name.includes('c -')) return "bg-gray-50 text-gray-700 border-gray-200"
    if (name.includes('active') || name.includes('client')) return "bg-green-50 text-green-700 border-green-200"
    if (name.includes('pending')) return "bg-purple-50 text-purple-700 border-purple-200"
    return "bg-gray-50 text-gray-700 border-gray-200"
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  // Get recent leads (last 10)
  const recentLeads = [...leads]
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
    .slice(0, 10)

  if (isLoading || authLoading) {
    return (
      <SidebarWrapper role="agent">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading dashboard...</span>
        </div>
      </SidebarWrapper>
    )
  }

  return (
    <SidebarWrapper role="agent">
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Agent Dashboard</h1>
          <p className="text-muted-foreground">Manage your leads and track your performance</p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchData} disabled={isLoading}>
          <RefreshCw className={`h-5 w-5 ${isLoading ? 'animate-spin' : ''}`} />
          <span className="sr-only">Refresh data</span>
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 mb-8">
        {stats.map((stat) => (
          <Card key={stat.title}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">{stat.title}</CardTitle>
              <stat.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stat.value}</div>
              <p className="text-xs text-muted-foreground">{stat.description}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Leads</CardTitle>
              <CardDescription>Your most recently updated leads from Follow Up Boss</CardDescription>
            </div>
            <Button variant="outline" size="sm" asChild>
              <Link href="/agent/leads">View All Leads</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {recentLeads.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No leads found. Import leads from the Lead Sources page.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Lead Name</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Price</TableHead>
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
                      <TableCell className="text-sm">{formatDate(lead.created_at)}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={getStageColor(lead.status)}>
                          {lead.status || 'Unknown'}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm">
                        {lead.price > 0 ? `$${lead.price.toLocaleString()}` : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </SidebarWrapper>
  )
}
