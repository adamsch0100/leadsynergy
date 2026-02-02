"use client"

import { Suspense, useState, useEffect, useCallback } from "react"
import { useSearchParams } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Input } from "@/components/ui/input"
import {
  AlertTriangle,
  CheckCircle,
  Inbox,
  LifeBuoy,
  Loader2,
  Mail,
  Phone,
  Plus,
  RefreshCw,
  Send,
  Ticket,
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

export default function HelpPage() {
  return (
    <Suspense>
      <HelpPageContent />
    </Suspense>
  )
}

function HelpPageContent() {
  const searchParams = useSearchParams()
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Active tab
  const [activeTab, setActiveTab] = useState("my-tickets")

  // Tickets list
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [statusFilter, setStatusFilter] = useState<string>("all")

  // New ticket form
  const [newSubject, setNewSubject] = useState("")
  const [newCategory, setNewCategory] = useState("")
  const [newPriority, setNewPriority] = useState("normal")
  const [newDescription, setNewDescription] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Ticket detail
  const [selectedTicket, setSelectedTicket] = useState<SupportTicket | null>(null)
  const [ticketNotes, setTicketNotes] = useState<TicketNote[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [replyContent, setReplyContent] = useState("")
  const [isSubmittingReply, setIsSubmittingReply] = useState(false)

  // Load user
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Handle deep-link tab param
  useEffect(() => {
    const tabParam = searchParams.get("tab")
    if (tabParam === "new-ticket") {
      setActiveTab("new-ticket")
    }
  }, [searchParams])

  // Fetch tickets when user loads
  useEffect(() => {
    if (user) {
      fetchTickets()
    }
  }, [user])

  // Re-fetch when status filter changes
  useEffect(() => {
    if (user) {
      fetchTickets()
    }
  }, [statusFilter])

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
      params.set("limit", "100")

      const res = await fetch(`${API_BASE_URL}/api/support/tickets?${params}`, {
        headers: { "X-User-ID": user.id },
      })
      const data = await res.json()

      if (data.success) {
        setTickets(data.tickets || [])
      } else {
        setError(data.error || "Failed to load tickets")
      }
    } catch (err) {
      console.error("Error fetching tickets:", err)
      setError("Failed to connect to server")
    } finally {
      setIsLoading(false)
    }
  }, [user, statusFilter])

  const createTicket = async () => {
    if (!user || !newSubject.trim() || !newDescription.trim()) return
    setIsSubmitting(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/tickets`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({
          subject: newSubject.trim(),
          description: newDescription.trim(),
          priority: newPriority,
          category: newCategory || "other",
        }),
      })
      const data = await res.json()

      if (data.success) {
        setSuccessMessage(`Ticket #${data.ticket?.id} created successfully! We'll get back to you soon.`)
        setNewSubject("")
        setNewCategory("")
        setNewPriority("normal")
        setNewDescription("")
        setActiveTab("my-tickets")
        fetchTickets()
        setTimeout(() => setSuccessMessage(null), 5000)
      } else {
        setError(data.error || "Failed to create ticket")
      }
    } catch (err) {
      console.error("Error creating ticket:", err)
      setError("Failed to connect to server")
    } finally {
      setIsSubmitting(false)
    }
  }

  const fetchTicketDetail = async (ticket: SupportTicket) => {
    if (!user) return
    setSelectedTicket(ticket)
    setDetailOpen(true)
    setReplyContent("")

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

  const addReply = async () => {
    if (!user || !selectedTicket || !replyContent.trim()) return
    setIsSubmittingReply(true)

    try {
      const res = await fetch(`${API_BASE_URL}/api/support/tickets/${selectedTicket.id}/notes`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-User-ID": user.id,
        },
        body: JSON.stringify({
          content: replyContent.trim(),
          is_internal: false,
        }),
      })
      const data = await res.json()

      if (data.success) {
        setTicketNotes((prev) => [...prev, data.note])
        setReplyContent("")
        setSuccessMessage("Reply sent")
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to send reply")
      }
    } catch (err) {
      console.error("Error adding reply:", err)
      setError("Failed to send reply")
    } finally {
      setIsSubmittingReply(false)
    }
  }

  // Helpers — same as admin support-tickets page for visual consistency
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
    <SidebarWrapper role="agent">
      <div className="px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Help & Support</h1>
            <p className="text-muted-foreground">Get help, submit tickets, and track your requests</p>
          </div>
          <div className="flex items-center gap-2">
            <Button onClick={() => setActiveTab("new-ticket")}>
              <Plus className="mr-2 h-4 w-4" />
              New Ticket
            </Button>
            <Button variant="outline" size="icon" onClick={() => fetchTickets()} disabled={isLoading}>
              <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

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

        {/* Quick Contact Cards */}
        <div className="grid gap-4 md:grid-cols-3 mb-8">
          <Card>
            <CardHeader className="pb-3">
              <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-2">
                <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>
              <CardTitle className="text-lg">Email Support</CardTitle>
            </CardHeader>
            <CardContent>
              <a
                href="mailto:support@leadsynergy.io"
                className="text-primary hover:underline"
              >
                support@leadsynergy.io
              </a>
              <p className="text-sm text-muted-foreground mt-1">
                Response within 24 hours
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center mb-2">
                <Phone className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <CardTitle className="text-lg">Phone Support</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Available for Professional and Business plan customers.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <div className="h-10 w-10 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-2">
                <LifeBuoy className="h-5 w-5 text-purple-600 dark:text-purple-400" />
              </div>
              <CardTitle className="text-lg">Help Center</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Browse our documentation and FAQs for quick answers.
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="mb-6">
            <TabsTrigger value="my-tickets" className="flex items-center gap-2">
              <Ticket className="h-4 w-4" />
              My Tickets
              {tickets.length > 0 && (
                <Badge variant="secondary" className="ml-1 text-xs">{tickets.length}</Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="new-ticket" className="flex items-center gap-2">
              <Plus className="h-4 w-4" />
              New Ticket
            </TabsTrigger>
          </TabsList>

          {/* My Tickets Tab */}
          <TabsContent value="my-tickets">
            {/* Status Filter */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex flex-wrap gap-4 items-end">
                  <div className="w-48">
                    <Label className="text-sm font-medium mb-1 block">Filter by Status</Label>
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
                </div>
              </CardContent>
            </Card>

            {/* Tickets Table */}
            <Card>
              <CardHeader>
                <CardTitle>Your Tickets</CardTitle>
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
                    <p className="text-lg font-medium">No tickets yet</p>
                    <p className="text-sm mb-4">Submit a ticket to get help from our support team.</p>
                    <Button onClick={() => setActiveTab("new-ticket")}>
                      <Plus className="mr-2 h-4 w-4" />
                      Submit a Ticket
                    </Button>
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
          </TabsContent>

          {/* New Ticket Tab */}
          <TabsContent value="new-ticket">
            <Card>
              <CardHeader>
                <CardTitle>Submit a Support Ticket</CardTitle>
                <CardDescription>
                  Describe your issue and our team will respond as soon as possible.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-6 max-w-2xl">
                  <div className="space-y-2">
                    <Label htmlFor="subject">Subject</Label>
                    <Input
                      id="subject"
                      placeholder="Brief summary of your issue"
                      value={newSubject}
                      onChange={(e) => setNewSubject(e.target.value)}
                    />
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="category">Category</Label>
                      <Select value={newCategory} onValueChange={setNewCategory}>
                        <SelectTrigger>
                          <SelectValue placeholder="Select a category" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="technical">Technical Support</SelectItem>
                          <SelectItem value="billing">Billing</SelectItem>
                          <SelectItem value="feature_request">Feature Request</SelectItem>
                          <SelectItem value="account">Account</SelectItem>
                          <SelectItem value="other">Other</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="priority">Priority</Label>
                      <Select value={newPriority} onValueChange={setNewPriority}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="low">Low</SelectItem>
                          <SelectItem value="normal">Normal</SelectItem>
                          <SelectItem value="high">High</SelectItem>
                          <SelectItem value="urgent">Urgent</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      placeholder="Describe your issue in detail. Include any error messages, steps to reproduce, or screenshots if applicable."
                      rows={6}
                      value={newDescription}
                      onChange={(e) => setNewDescription(e.target.value)}
                    />
                  </div>

                  <Button
                    onClick={createTicket}
                    disabled={isSubmitting || !newSubject.trim() || !newDescription.trim()}
                    className="w-full sm:w-auto"
                  >
                    {isSubmitting ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="mr-2 h-4 w-4" />
                    )}
                    Submit Ticket
                  </Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
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
                  Submitted {formatDate(selectedTicket.created_at)}
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-6">
                {/* Status, Priority, Category */}
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
                  {selectedTicket.closed_at && (
                    <div>
                      <Label className="text-xs text-muted-foreground">Closed</Label>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {formatDate(selectedTicket.closed_at)}
                      </div>
                    </div>
                  )}
                </div>

                {/* Description */}
                <div>
                  <Label className="text-sm font-medium">Description</Label>
                  <div className="mt-2 p-4 bg-muted rounded-lg text-sm whitespace-pre-wrap">
                    {selectedTicket.description}
                  </div>
                </div>

                {/* Conversation Thread */}
                <div>
                  <Label className="text-sm font-medium mb-3 block">
                    Conversation ({ticketNotes.length})
                  </Label>
                  {ticketNotes.length === 0 ? (
                    <p className="text-sm text-muted-foreground py-4">
                      No replies yet. Our support team will respond soon.
                    </p>
                  ) : (
                    <div className="space-y-3 max-h-80 overflow-y-auto">
                      {ticketNotes.map((note) => {
                        const isOwnNote = note.user_id === user?.id
                        return (
                          <div
                            key={note.id}
                            className={`p-3 rounded-lg text-sm ${
                              isOwnNote
                                ? "bg-blue-50 border border-blue-200 dark:bg-blue-950 dark:border-blue-800"
                                : "bg-muted"
                            }`}
                          >
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-xs">
                                {isOwnNote ? "You" : "Support Team"}
                              </span>
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

                  {/* Reply */}
                  {selectedTicket.status === "closed" ? (
                    <div className="mt-4 p-3 rounded-lg bg-muted text-center text-sm text-muted-foreground">
                      <CheckCircle className="h-4 w-4 inline mr-1" />
                      This ticket is closed. Submit a new ticket if you need further assistance.
                    </div>
                  ) : (
                    <div className="mt-4 space-y-3">
                      <Textarea
                        placeholder="Type your reply..."
                        value={replyContent}
                        onChange={(e) => setReplyContent(e.target.value)}
                        rows={3}
                      />
                      <div className="flex justify-end">
                        <Button
                          size="sm"
                          onClick={addReply}
                          disabled={!replyContent.trim() || isSubmittingReply}
                        >
                          {isSubmittingReply ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <Send className="mr-2 h-4 w-4" />
                          )}
                          Send Reply
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </SidebarWrapper>
  )
}
