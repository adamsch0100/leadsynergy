"use client"

import { useState, useEffect, useCallback } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  Inbox,
  Loader2,
  Mail,
  MessageSquare,
  Plus,
  RefreshCw,
  Save,
  Send,
  Settings,
  Ticket,
  X,
  XCircle,
} from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

interface SupportTicket {
  id: number
  user_id: string
  subject: string
  description: string
  status: string
  priority: string
  category: string | null
  assigned_to: string | null
  created_at: string
  updated_at: string
  closed_at: string | null
}

interface TicketNote {
  id: number
  ticket_id: number
  user_id: string
  content: string
  is_internal: boolean
  created_at: string
}

interface TicketStats {
  total_tickets: number
  open_tickets: number
  in_progress: number
  waiting: number
  closed: number
  by_priority: Record<string, number>
  resolved_count: number
  avg_resolution_hours: number
  resolution_rate: number
}

export default function SupportTicketsPage() {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Data
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [stats, setStats] = useState<TicketStats | null>(null)
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({})

  // Filters
  const [statusFilter, setStatusFilter] = useState<string>("all")
  const [priorityFilter, setPriorityFilter] = useState<string>("all")

  // Ticket detail view
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null)
  const [ticketNotes, setTicketNotes] = useState<TicketNote[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [newNote, setNewNote] = useState("")
  const [isInternalNote, setIsInternalNote] = useState(false)
  const [isSubmittingNote, setIsSubmittingNote] = useState(false)

  // Status update
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false)

  // Notification settings
  const [notificationEmails, setNotificationEmails] = useState<string[]>([])
  const [newEmailInput, setNewEmailInput] = useState("")
  const [isSavingEmails, setIsSavingEmails] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  // Load user
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch data when user loads
  useEffect(() => {
    if (user) {
      fetchTickets()
      fetchStats()
      fetchNotificationSettings()
    }
  }, [user])

  // Re-fetch when filters change
  useEffect(() => {
    if (user) {
      fetchTickets()
    }
  }, [statusFilter, priorityFilter])

  // Auto-dismiss errors after 8 seconds
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 8000)
      return () => clearTimeout(timer)
    }
  }, [error])

  const fetchTickets = useCallback(async () => {
    if (!user) return
    setIsLoading(true)
    setError(null)

    try {
      const params = new URLSearchParams()
      if (statusFilter && statusFilter !== "all") params.set("status", statusFilter)
      if (priorityFilter && priorityFilter !== "all") params.set("priority", priorityFilter)
      params.set("limit", "100")

      const res = await fetch(`${API_BASE_URL}/api/support/admin/tickets?${params}`, {
        headers: { "X-User-ID": user.id },
      })
      const data = await res.json()

      if (data.success) {
        setTickets(data.tickets || [])
        setStatusCounts(data.counts || {})
      } else {
        setError(data.error || "Failed to load tickets")
      }
    } catch (err) {
      console.error("Error fetching tickets:", err)
      setError("Failed to connect to server")
    } finally {
      setIsLoading(false)
    }
  }, [user, statusFilter, priorityFilter])

  const fetchStats = async () => {
    if (!user) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/support/admin/stats`, {
        headers: { "X-User-ID": user.id },
      })
      const data = await res.json()
      if (data.success) {
        setStats(data.stats)
      }
    } catch (err) {
      console.error("Error fetching stats:", err)
    }
  }

  const fetchNotificationSettings = async () => {
    if (!user) return
    try {
      const res = await fetch(`${API_BASE_URL}/api/support/admin/notification-settings`, {
        headers: { "X-User-ID": user.id },
      })
      const data = await res.json()
      if (data.success) {
        setNotificationEmails(data.notification_emails || [])
      }
    } catch (err) {
      console.error("Error fetching notification settings:", err)
    }
  }

  const saveNotificationEmails = async () => {
    if (!user) return
    setIsSavingEmails(true)
    try {
      const res = await fetch(`${API_BASE_URL}/api/support/admin/notification-settings`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({ notification_emails: notificationEmails }),
      })
      const data = await res.json()
      if (data.success) {
        setSuccessMessage("Notification settings saved")
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to save notification settings")
      }
    } catch (err) {
      console.error("Error saving notification settings:", err)
      setError("Failed to save notification settings")
    } finally {
      setIsSavingEmails(false)
    }
  }

  const addNotificationEmail = () => {
    const email = newEmailInput.trim().toLowerCase()
    if (!email) return
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError("Please enter a valid email address")
      return
    }
    if (notificationEmails.includes(email)) {
      setError("This email is already in the list")
      return
    }
    setNotificationEmails((prev) => [...prev, email])
    setNewEmailInput("")
    setError(null)
  }

  const removeNotificationEmail = (email: string) => {
    setNotificationEmails((prev) => prev.filter((e) => e !== email))
  }

  const fetchTicketDetail = async (ticket: SupportTicket) => {
    if (!user) return
    setSelectedTicket(ticket)
    setDetailOpen(true)
    setNewNote("")
    setIsInternalNote(false)

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/tickets/${ticket.id}`, {
        headers: { "X-User-ID": user.id },
      })
      const data = await res.json()
      if (data.success) {
        setSelectedTicket(data.ticket)
        setTicketNotes(data.notes || [])
      }
    } catch (err) {
      console.error("Error fetching ticket detail:", err)
    }
  }

  const updateTicketStatus = async (ticketId: number, newStatus: string) => {
    if (!user) return
    setIsUpdatingStatus(true)

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/admin/tickets/${ticketId}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({ status: newStatus }),
      })
      const data = await res.json()

      if (data.success) {
        setSuccessMessage(`Ticket status updated to ${newStatus.replace(/_/g, " ")}`)
        setSelectedTicket(data.ticket)
        fetchTickets()
        fetchStats()
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to update status")
      }
    } catch (err) {
      console.error("Error updating status:", err)
      setError("Failed to update ticket status")
    } finally {
      setIsUpdatingStatus(false)
    }
  }

  const assignToMe = async (ticketId: number) => {
    if (!user) return

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/admin/tickets/${ticketId}/assign`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({ assigned_to: user.id }),
      })
      const data = await res.json()

      if (data.success) {
        setSuccessMessage("Ticket assigned to you")
        setSelectedTicket(data.ticket)
        fetchTickets()
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to assign ticket")
      }
    } catch (err) {
      console.error("Error assigning ticket:", err)
      setError("Failed to assign ticket")
    }
  }

  const addNote = async () => {
    if (!user || !selectedTicket || !newNote.trim()) return
    setIsSubmittingNote(true)

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/tickets/${selectedTicket.id}/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({
          content: newNote.trim(),
          is_internal: isInternalNote,
        }),
      })
      const data = await res.json()

      if (data.success) {
        setTicketNotes((prev) => [...prev, data.note])
        setNewNote("")
        setIsInternalNote(false)
        setSuccessMessage("Note added")
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to add note")
      }
    } catch (err) {
      console.error("Error adding note:", err)
      setError("Failed to add note")
    } finally {
      setIsSubmittingNote(false)
    }
  }

  // Helpers
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "N/A"
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "open":
        return <Badge variant="destructive">Open</Badge>
      case "in_progress":
        return <Badge className="bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-900 dark:text-blue-200 dark:border-blue-800">In Progress</Badge>
      case "waiting":
        return <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-200 dark:border-yellow-800">Waiting</Badge>
      case "closed":
        return <Badge variant="secondary">Closed</Badge>
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case "urgent":
        return <Badge variant="destructive">Urgent</Badge>
      case "high":
        return <Badge className="bg-orange-100 text-orange-800 border-orange-200 dark:bg-orange-900 dark:text-orange-200 dark:border-orange-800">High</Badge>
      case "normal":
        return <Badge variant="outline">Normal</Badge>
      case "low":
        return <Badge variant="secondary">Low</Badge>
      default:
        return <Badge variant="outline">{priority}</Badge>
    }
  }

  const getCategoryLabel = (category: string | null) => {
    if (!category) return "General"
    return category.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  }

  return (
    <SidebarWrapper role="admin">
      <div className="px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Support Tickets</h1>
            <p className="text-muted-foreground">Manage help requests and user issues</p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant={showSettings ? "default" : "outline"}
              size="icon"
              onClick={() => setShowSettings(!showSettings)}
              title="Notification settings"
            >
              <Settings className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => { fetchTickets(); fetchStats() }} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Notification Settings */}
        {showSettings && (
          <Card className="mb-6 border-blue-200 dark:border-blue-800">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg flex items-center gap-2">
                <Mail className="h-5 w-5" />
                Email Notifications
              </CardTitle>
              <CardDescription>
                Get notified by email when new support tickets are submitted. Add email addresses below.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {/* Current emails */}
                {notificationEmails.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {notificationEmails.map((email) => (
                      <Badge
                        key={email}
                        variant="secondary"
                        className="text-sm py-1 px-3 flex items-center gap-1"
                      >
                        {email}
                        <button
                          onClick={() => removeNotificationEmail(email)}
                          className="ml-1 hover:text-destructive"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                )}

                {/* Add email */}
                <div className="flex gap-2">
                  <Input
                    type="email"
                    placeholder="Enter email address..."
                    value={newEmailInput}
                    onChange={(e) => setNewEmailInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault()
                        addNotificationEmail()
                      }
                    }}
                    className="max-w-sm"
                  />
                  <Button variant="outline" size="sm" onClick={addNotificationEmail}>
                    <Plus className="mr-1 h-4 w-4" />
                    Add
                  </Button>
                  <Button size="sm" onClick={saveNotificationEmails} disabled={isSavingEmails}>
                    {isSavingEmails ? (
                      <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="mr-1 h-4 w-4" />
                    )}
                    Save
                  </Button>
                </div>

                {notificationEmails.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No notification emails configured. Add an email to receive alerts when tickets are created.
                  </p>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Alerts */}
        {error && (
          <Alert variant="destructive" className="mb-6">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        {successMessage && (
          <Alert className="mb-6 bg-green-50 border-green-200 dark:bg-green-950 dark:border-green-800">
            <CheckCircle className="h-4 w-4 text-green-600 dark:text-green-400" />
            <AlertDescription className="text-green-800 dark:text-green-200">{successMessage}</AlertDescription>
          </Alert>
        )}

        {/* Stats Cards */}
        {stats && (
          <div className="grid gap-4 md:grid-cols-5 mb-8">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Total Tickets</CardTitle>
                <Ticket className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total_tickets}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Open</CardTitle>
                <Inbox className="h-4 w-4 text-red-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-red-600">{stats.open_tickets}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">In Progress</CardTitle>
                <Loader2 className="h-4 w-4 text-blue-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-blue-600">{stats.in_progress}</div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Avg Resolution</CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">
                  {stats.avg_resolution_hours > 0 ? `${stats.avg_resolution_hours}h` : "--"}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">Resolution Rate</CardTitle>
                <CheckCircle className="h-4 w-4 text-green-500" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold text-green-600">
                  {stats.resolution_rate > 0 ? `${stats.resolution_rate}%` : "--"}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="mb-6">
          <CardContent className="pt-6">
            <div className="flex flex-wrap gap-4">
              <div className="w-48">
                <Label className="text-sm font-medium mb-1 block">Status</Label>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Statuses</SelectItem>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="waiting">Waiting</SelectItem>
                    <SelectItem value="closed">Closed</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="w-48">
                <Label className="text-sm font-medium mb-1 block">Priority</Label>
                <Select value={priorityFilter} onValueChange={setPriorityFilter}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Priorities</SelectItem>
                    <SelectItem value="urgent">Urgent</SelectItem>
                    <SelectItem value="high">High</SelectItem>
                    <SelectItem value="normal">Normal</SelectItem>
                    <SelectItem value="low">Low</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tickets Table */}
        <Card>
          <CardHeader>
            <CardTitle>Tickets</CardTitle>
            <CardDescription>
              {tickets.length} ticket{tickets.length !== 1 ? "s" : ""} found
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : tickets.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Inbox className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p className="text-lg font-medium">No tickets found</p>
                <p className="text-sm">Tickets will appear here when users submit help requests.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16">ID</TableHead>
                    <TableHead>Subject</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {tickets.map((ticket) => (
                    <TableRow
                      key={ticket.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => fetchTicketDetail(ticket)}
                    >
                      <TableCell className="font-mono text-sm">#{ticket.id}</TableCell>
                      <TableCell className="font-medium max-w-[300px] truncate">
                        {ticket.subject}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline">{getCategoryLabel(ticket.category)}</Badge>
                      </TableCell>
                      <TableCell>{getStatusBadge(ticket.status)}</TableCell>
                      <TableCell>{getPriorityBadge(ticket.priority)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(ticket.created_at)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(ticket.updated_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Ticket Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          {selectedTicket && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <span className="text-muted-foreground font-mono">#{selectedTicket.id}</span>
                  {selectedTicket.subject}
                </DialogTitle>
                <DialogDescription>
                  Created {formatDate(selectedTicket.created_at)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-6">
                {/* Status and Priority */}
                <div className="flex flex-wrap gap-4">
                  <div>
                    <Label className="text-xs text-muted-foreground">Status</Label>
                    <div className="mt-1">{getStatusBadge(selectedTicket.status)}</div>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Priority</Label>
                    <div className="mt-1">{getPriorityBadge(selectedTicket.priority)}</div>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Category</Label>
                    <div className="mt-1">
                      <Badge variant="outline">{getCategoryLabel(selectedTicket.category)}</Badge>
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs text-muted-foreground">Assigned</Label>
                    <div className="mt-1">
                      {selectedTicket.assigned_to ? (
                        <Badge variant="secondary">Assigned</Badge>
                      ) : (
                        <Badge variant="outline" className="text-orange-600">Unassigned</Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* Description */}
                <div>
                  <Label className="text-sm font-medium">Description</Label>
                  <div className="mt-2 p-4 bg-muted rounded-lg text-sm whitespace-pre-wrap">
                    {selectedTicket.description}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-wrap gap-2">
                  {!selectedTicket.assigned_to && (
                    <Button variant="outline" size="sm" onClick={() => assignToMe(selectedTicket.id)}>
                      Assign to Me
                    </Button>
                  )}
                  {selectedTicket.status !== "in_progress" && selectedTicket.status !== "closed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateTicketStatus(selectedTicket.id, "in_progress")}
                      disabled={isUpdatingStatus}
                    >
                      Mark In Progress
                    </Button>
                  )}
                  {selectedTicket.status !== "waiting" && selectedTicket.status !== "closed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateTicketStatus(selectedTicket.id, "waiting")}
                      disabled={isUpdatingStatus}
                    >
                      Mark Waiting
                    </Button>
                  )}
                  {selectedTicket.status !== "closed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-green-600 border-green-200 hover:bg-green-50"
                      onClick={() => updateTicketStatus(selectedTicket.id, "closed")}
                      disabled={isUpdatingStatus}
                    >
                      <CheckCircle className="mr-1 h-3 w-3" />
                      Close Ticket
                    </Button>
                  )}
                  {selectedTicket.status === "closed" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => updateTicketStatus(selectedTicket.id, "open")}
                      disabled={isUpdatingStatus}
                    >
                      Reopen
                    </Button>
                  )}
                </div>

                {/* Notes / Comments */}
                <div>
                  <Label className="text-sm font-medium mb-3 block">
                    Notes ({ticketNotes.length})
                  </Label>
                  {ticketNotes.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">No notes yet.</p>
                  ) : (
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                      {ticketNotes.map((note) => {
                        const isAdmin = note.user_id === user?.id
                        const isCustomer = selectedTicket && note.user_id === selectedTicket.user_id
                        const noteLabel = isAdmin ? "You" : isCustomer ? "Customer" : "Team"
                        return (
                        <div
                          key={note.id}
                          className={`p-3 rounded-lg text-sm ${
                            note.is_internal
                              ? "bg-yellow-50 border border-yellow-200 dark:bg-yellow-950 dark:border-yellow-800"
                              : isCustomer
                                ? "bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-800"
                                : "bg-muted"
                          }`}
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-xs">
                              {noteLabel}
                            </span>
                            {note.is_internal && (
                              <Badge variant="outline" className="text-xs py-0 text-yellow-700">
                                Internal
                              </Badge>
                            )}
                            <span className="text-xs text-muted-foreground">
                              {formatDate(note.created_at)}
                            </span>
                          </div>
                          <p className="whitespace-pre-wrap">{note.content}</p>
                        </div>
                        )
                      })}
                    </div>
                  )}

                  {/* Add Note */}
                  <div className="mt-4 space-y-3">
                    <Textarea
                      placeholder="Add a note or reply..."
                      value={newNote}
                      onChange={(e) => setNewNote(e.target.value)}
                      rows={3}
                    />
                    <div className="flex items-center justify-between">
                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={isInternalNote}
                          onChange={(e) => setIsInternalNote(e.target.checked)}
                          className="rounded"
                        />
                        Internal note (hidden from user)
                      </label>
                      <Button
                        size="sm"
                        onClick={addNote}
                        disabled={!newNote.trim() || isSubmittingNote}
                      >
                        {isSubmittingNote ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Send className="mr-2 h-4 w-4" />
                        )}
                        Add Note
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </SidebarWrapper>
  )
}
