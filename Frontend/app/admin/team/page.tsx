"use client"

import { useState, useEffect } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { SidebarWrapper } from "@/components/sidebar"
import { AlertTriangle, Download, Lock, Mail, Plus, RefreshCw, Shield, User2, Users } from "lucide-react"
import { useSubscription } from "@/contexts/subscription-context"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface TeamMember {
  id: string
  name: string
  email: string
  role: "admin" | "agent" | "manager"
  status: "active" | "pending"
  lastActive: string
  permissions: string[]
}

interface FUBUser {
  fub_id: string
  name: string
  email: string
  role: string
  phone: string
  active: boolean
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function TeamManagementPage() {
  const { subscription } = useSubscription()
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false)
  const [isFubSyncDialogOpen, setIsFubSyncDialogOpen] = useState(false)
  const [newMemberEmail, setNewMemberEmail] = useState("")
  const [newMemberRole, setNewMemberRole] = useState<"admin" | "agent" | "manager">("agent")
  const [showUpgradeAlert, setShowUpgradeAlert] = useState(false)
  const [team, setTeam] = useState<TeamMember[]>([])
  const [fubUsers, setFubUsers] = useState<FUBUser[]>([])
  const [selectedFubUsers, setSelectedFubUsers] = useState<Set<string>>(new Set())
  const [isLoading, setIsLoading] = useState(true)
  const [isSyncingFub, setIsSyncingFub] = useState(false)
  const [isInvitingFub, setIsInvitingFub] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [isInviting, setIsInviting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fubError, setFubError] = useState<string | null>(null)

  const teamLimit = subscription.plan === "free" ? 5 : subscription.plan === "pro" ? 20 : Infinity

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch team members
  useEffect(() => {
    if (user) {
      fetchTeamMembers()
    }
  }, [user])

  const fetchTeamMembers = async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/team-members`, {
        headers: { 'X-User-ID': user.id }
      })
      const data = await res.json()
      if (data.success && Array.isArray(data.data)) {
        // Transform API response to TeamMember format
        const members: TeamMember[] = data.data.map((m: any) => ({
          id: m.id,
          name: m.name || `${m.first_name || ''} ${m.last_name || ''}`.trim() || m.email?.split('@')[0] || 'Unknown',
          email: m.email,
          role: m.role || 'agent',
          status: m.status || 'active',
          lastActive: m.last_active || m.updated_at ? formatTimeAgo(m.updated_at) : 'Never',
          permissions: m.permissions || []
        }))
        setTeam(members)
      } else if (data.error) {
        // If no team members table or empty, show current user as admin
        const supabase = createClient()
        const { data: userData } = await supabase.from('users').select('*').eq('id', user.id).single()
        if (userData) {
          setTeam([{
            id: userData.id,
            name: userData.name || userData.email?.split('@')[0] || 'Admin',
            email: userData.email,
            role: userData.role || 'admin',
            status: 'active',
            lastActive: 'Now',
            permissions: ['manage_team', 'manage_leads', 'manage_settings']
          }])
        }
      }
    } catch (err) {
      console.error('Failed to fetch team:', err)
      setError('Failed to load team members')
    } finally {
      setIsLoading(false)
    }
  }

  const formatTimeAgo = (dateStr: string) => {
    if (!dateStr) return 'Never'
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

  const handleInviteMember = async () => {
    if (team.length >= teamLimit) {
      setShowUpgradeAlert(true)
      return
    }

    if (newMemberRole === "manager" && subscription.plan === "free") {
      setShowUpgradeAlert(true)
      return
    }

    if (!user || !newMemberEmail) return
    setIsInviting(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/team-members/invite`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({
          email: newMemberEmail,
          role: newMemberRole
        })
      })
      const data = await res.json()
      if (data.success) {
        setNewMemberEmail("")
        setIsInviteDialogOpen(false)
        fetchTeamMembers() // Refresh the list
      } else {
        setError(data.error || 'Failed to send invitation')
      }
    } catch (err) {
      setError('Failed to send invitation')
    } finally {
      setIsInviting(false)
    }
  }

  const handleSyncFromFub = async () => {
    if (!user) return
    setIsSyncingFub(true)
    setFubError(null)
    setFubUsers([])
    setSelectedFubUsers(new Set())

    try {
      const res = await fetch(`${API_BASE_URL}/api/supabase/team-members/sync-from-fub`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        }
      })
      const data = await res.json()
      if (data.success) {
        // Filter out users that are already on the team (by email)
        const existingEmails = new Set(team.map(m => m.email.toLowerCase()))
        const newUsers = (data.data || []).filter((u: FUBUser) =>
          u.email && !existingEmails.has(u.email.toLowerCase())
        )
        setFubUsers(newUsers)
        if (newUsers.length === 0 && data.data?.length > 0) {
          setFubError('All FUB team members are already on your team.')
        }
      } else {
        setFubError(data.error || 'Failed to sync from Follow Up Boss')
      }
    } catch (err) {
      setFubError('Failed to connect to Follow Up Boss')
    } finally {
      setIsSyncingFub(false)
    }
  }

  const handleToggleFubUser = (email: string) => {
    const newSelected = new Set(selectedFubUsers)
    if (newSelected.has(email)) {
      newSelected.delete(email)
    } else {
      newSelected.add(email)
    }
    setSelectedFubUsers(newSelected)
  }

  const handleInviteSelectedFub = async () => {
    if (!user || selectedFubUsers.size === 0) return
    setIsInvitingFub(true)
    setFubError(null)

    let successCount = 0
    let failCount = 0

    for (const email of selectedFubUsers) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/supabase/team-members/invite`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user.id
          },
          body: JSON.stringify({ email, role: 'agent' })
        })
        const data = await res.json()
        if (data.success) {
          successCount++
        } else {
          failCount++
        }
      } catch (err) {
        failCount++
      }
    }

    setIsInvitingFub(false)

    if (successCount > 0) {
      setIsFubSyncDialogOpen(false)
      setSelectedFubUsers(new Set())
      fetchTeamMembers()
    }

    if (failCount > 0) {
      setFubError(`Invited ${successCount} members. ${failCount} failed.`)
    }
  }

  const availableRoles = [
    {
      value: "agent",
      label: "Agent",
      description: "Can manage assigned leads and track commissions",
    },
    {
      value: "manager",
      label: "Team Manager",
      description: "Can manage team leads and view performance metrics",
      premiumOnly: true,
    },
    {
      value: "admin",
      label: "Administrator",
      description: "Full access to all system features",
      premiumOnly: true,
    },
  ]

  return (
    <SidebarWrapper role="admin">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Team Management</h1>
          <p className="text-muted-foreground">Manage your team members and their roles</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={fetchTeamMembers} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          </Button>

          {/* Sync from FUB Dialog */}
          <Dialog open={isFubSyncDialogOpen} onOpenChange={setIsFubSyncDialogOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" onClick={() => { setIsFubSyncDialogOpen(true); handleSyncFromFub(); }}>
                <Download className="mr-2 h-4 w-4" />
                Sync from FUB
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Import Team from Follow Up Boss</DialogTitle>
                <DialogDescription>
                  Select team members from your FUB account to invite to LeadSynergy
                </DialogDescription>
              </DialogHeader>

              {fubError && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{fubError}</AlertDescription>
                </Alert>
              )}

              {isSyncingFub ? (
                <div className="flex items-center justify-center py-8">
                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground mr-2" />
                  <span>Loading team members from FUB...</span>
                </div>
              ) : fubUsers.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {fubError ? '' : 'No new team members found in Follow Up Boss.'}
                </div>
              ) : (
                <div className="max-h-96 overflow-y-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">Select</TableHead>
                        <TableHead>Name</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Role</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {fubUsers.map((fubUser) => (
                        <TableRow key={fubUser.fub_id}>
                          <TableCell>
                            <Checkbox
                              checked={selectedFubUsers.has(fubUser.email)}
                              onCheckedChange={() => handleToggleFubUser(fubUser.email)}
                            />
                          </TableCell>
                          <TableCell className="font-medium">
                            <div className="flex items-center gap-2">
                              <Users className="h-4 w-4 text-muted-foreground" />
                              {fubUser.name || 'Unknown'}
                            </div>
                          </TableCell>
                          <TableCell>{fubUser.email}</TableCell>
                          <TableCell>
                            <Badge variant="outline">{fubUser.role || 'agent'}</Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsFubSyncDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleInviteSelectedFub}
                  disabled={selectedFubUsers.size === 0 || isInvitingFub}
                >
                  {isInvitingFub ? 'Inviting...' : `Invite ${selectedFubUsers.size} Selected`}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Add Team Member
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Team Member</DialogTitle>
                <DialogDescription>
                  Invite a new member to join your team
                </DialogDescription>
              </DialogHeader>

              {team.length >= teamLimit ? (
                <div className="py-6">
                  <Alert variant="warning" className="mb-4">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>
                      You've reached the maximum number of team members ({teamLimit}) for your current plan.
                    </AlertDescription>
                  </Alert>
                  <Button asChild className="w-full">
                    <Link href="/admin/billing">Upgrade Plan</Link>
                  </Button>
                </div>
              ) : (
                <div className="grid gap-4 py-4">
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                  <div className="grid gap-2">
                    <Label htmlFor="email">Email Address</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="email"
                        type="email"
                        className="pl-10"
                        value={newMemberEmail}
                        onChange={(e) => setNewMemberEmail(e.target.value)}
                        placeholder="colleague@example.com"
                      />
                    </div>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="role">Role</Label>
                    <Select
                      value={newMemberRole}
                      onValueChange={(value: "admin" | "agent" | "manager") => setNewMemberRole(value)}
                    >
                      <SelectTrigger id="role">
                        <SelectValue placeholder="Select role" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableRoles.map((role) => (
                          <SelectItem
                            key={role.value}
                            value={role.value}
                            disabled={role.premiumOnly && subscription.plan === "free"}
                          >
                            <div className="flex items-center justify-between w-full">
                              <span>{role.label}</span>
                              {role.premiumOnly && subscription.plan === "free" && (
                                <Lock className="h-4 w-4 ml-2" />
                              )}
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-sm text-muted-foreground">
                      {availableRoles.find((r) => r.value === newMemberRole)?.description}
                    </p>
                  </div>
                </div>
              )}

              <DialogFooter>
                <Button variant="outline" onClick={() => setIsInviteDialogOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleInviteMember}
                  disabled={!newMemberEmail || team.length >= teamLimit || isInviting}
                >
                  {isInviting ? 'Sending...' : 'Send Invitation'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {showUpgradeAlert && (
        <Alert variant="warning" className="mb-6">
          <AlertTitle>Premium Feature</AlertTitle>
          <AlertDescription className="mt-2">
            Team manager and admin roles are only available on Pro and Enterprise plans.
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

      <Card>
        <CardHeader>
          <CardTitle>Team Members</CardTitle>
          <CardDescription>
            {team.length} of {teamLimit === Infinity ? 'unlimited' : teamLimit} team members
            {subscription.plan === "free" && (
              <span className="ml-1">
                (<Link href="/admin/billing" className="text-primary hover:underline">Upgrade</Link> for more)
              </span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : team.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No team members yet. Invite your first team member above.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {team.map((member) => (
                  <TableRow key={member.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-2">
                        <User2 className="h-5 w-5 text-muted-foreground" />
                        {member.name}
                      </div>
                    </TableCell>
                    <TableCell>{member.email}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Badge variant={member.role === "admin" ? "default" : "outline"}>
                          <Shield className="mr-1 h-3 w-3" />
                          {member.role}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={member.status === "active" ? "default" : "secondary"}
                      >
                        {member.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{member.lastActive}</TableCell>
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
