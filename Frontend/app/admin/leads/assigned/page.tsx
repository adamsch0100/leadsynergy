"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Clock, Phone, RefreshCw, AlertTriangle, UserCheck } from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

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
  tags: string
  price: number
  assigned_user_id?: string
  assigned_user_name?: string
}

interface FUBStage {
  id: string
  name: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function AssignedLeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [fubStages, setFubStages] = useState<FUBStage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [sourceFilter, setSourceFilter] = useState("all")
  const [uniqueSources, setUniqueSources] = useState<string[]>([])
  const [commissionRate, setCommissionRate] = useState(0.03)

  useEffect(() => {
    const loadUser = async () => {
      try {
        const supabase = createClient()
        const { data, error: authError } = await supabase.auth.getUser()
        if (authError) {
          console.error('Error loading user session:', authError)
          setError('Unable to load user session')
          setUser(null)
        } else {
          setUser(data.user ?? null)
        }
      } catch (err) {
        console.error('Unexpected error:', err)
        setError('Unable to load user session')
      } finally {
        setAuthLoading(false)
      }
    }
    loadUser()
  }, [])

  useEffect(() => {
    if (!authLoading && user) {
      fetchData()
      fetchCommissionRate()
    }
  }, [authLoading, user])

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
        // Filter to only assigned leads
        const assignedLeads = leadsData.data.filter((l: Lead) => l.assigned_user_id)
        setLeads(assignedLeads)
        const sources = [...new Set(assignedLeads.map((l: Lead) => l.source).filter(Boolean))]
        setUniqueSources(sources as string[])
      } else {
        throw new Error(leadsData.error || 'Failed to load leads')
      }

      if (stagesData.success && Array.isArray(stagesData.data)) {
        setFubStages(stagesData.data)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
      console.error('Error fetching data:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const getStageColor = (stageName: string) => {
    const name = stageName?.toLowerCase() || ''
    if (name.includes('lead') || name.includes('new')) return "bg-blue-50 text-blue-700 border-blue-200"
    if (name.includes('hot') || name.includes('a -')) return "bg-red-50 text-red-700 border-red-200"
    if (name.includes('warm') || name.includes('b -')) return "bg-yellow-50 text-yellow-700 border-yellow-200"
    if (name.includes('cold') || name.includes('c -')) return "bg-gray-50 text-gray-700 border-gray-200"
    if (name.includes('active') || name.includes('client')) return "bg-green-50 text-green-700 border-green-200"
    if (name.includes('pending')) return "bg-purple-50 text-purple-700 border-purple-200"
    if (name.includes('past')) return "bg-slate-50 text-slate-700 border-slate-200"
    if (name.includes('renter')) return "bg-orange-50 text-orange-700 border-orange-200"
    return "bg-gray-50 text-gray-700 border-gray-200"
  }

  const getStageName = (stageId: string) => {
    const stage = fubStages.find(s => s.id === stageId)
    return stage?.name || 'Unknown'
  }

  const getTimeAgo = (dateStr: string) => {
    if (!dateStr) return 'N/A'
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffMins < 60) return `${diffMins} minutes ago`
    if (diffHours < 24) return `${diffHours} hours ago`
    return `${diffDays} days ago`
  }

  const filteredLeads = sourceFilter === "all"
    ? leads
    : leads.filter(l => l.source === sourceFilter)

  const totalCommissionValue = filteredLeads.reduce((sum, l) => sum + ((l.price || 0) * commissionRate), 0)

  if (isLoading || authLoading) {
    return (
      <SidebarWrapper role="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-2 text-muted-foreground">Loading leads...</span>
        </div>
      </SidebarWrapper>
    )
  }

  return (
    <SidebarWrapper role="admin">
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Assigned Leads</h1>
          <p className="text-muted-foreground">
            Leads that have been assigned to team members ({filteredLeads.length} leads)
            - Commission Value: ${totalCommissionValue.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Label>Source:</Label>
            <Select value={sourceFilter} onValueChange={setSourceFilter}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="All Sources" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Sources</SelectItem>
                {uniqueSources.map(source => (
                  <SelectItem key={source} value={source}>{source}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button variant="outline" size="icon" onClick={fetchData} disabled={isLoading}>
            <RefreshCw className={`h-5 w-5 ${isLoading ? 'animate-spin' : ''}`} />
            <span className="sr-only">Refresh data</span>
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCheck className="h-5 w-5 text-green-600" />
            Assigned Leads
          </CardTitle>
          <CardDescription>Leads currently assigned to team members</CardDescription>
        </CardHeader>
        <CardContent>
          {filteredLeads.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No assigned leads found. Assign leads from the All Leads page.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Lead Name</TableHead>
                  <TableHead>Contact Info</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Assigned To</TableHead>
                  <TableHead>Stage</TableHead>
                  <TableHead>Last Update</TableHead>
                  <TableHead>Commission</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredLeads.map((lead) => (
                  <TableRow key={lead.id}>
                    <TableCell className="font-medium">
                      <div>{lead.first_name} {lead.last_name}</div>
                      <div className="text-xs text-muted-foreground">
                        FUB #{lead.fub_person_id}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col space-y-1">
                        {lead.phone && (
                          <div className="flex items-center gap-1 text-sm">
                            <Phone className="w-3 h-3" />
                            {lead.phone}
                          </div>
                        )}
                        {lead.email && (
                          <div className="text-xs text-muted-foreground">
                            {lead.email}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{lead.source || 'Unknown'}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary">{lead.assigned_user_name || 'Assigned'}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={getStageColor(lead.status)}>
                        {lead.status || getStageName(lead.stage_id)}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Clock className="w-4 h-4" />
                        {getTimeAgo(lead.updated_at)}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {lead.price > 0 ? `$${(lead.price * commissionRate).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}
