"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ClipboardList,
  Eye,
  EyeOff,
  Loader2,
  Plus,
  RefreshCw,
  CheckCircle,
  Clock,
  AlertCircle,
} from "lucide-react"
import { apiFetch } from "@/lib/api"

interface SetupRequest {
  id: string
  user_id: string
  organization_id: string | null
  user_email: string
  user_name: string
  platforms_description: string
  detected_platforms: string[] | null
  status: "pending" | "in_progress" | "completed"
  admin_notes: string | null
  created_at: string
  updated_at: string
}

interface SupportedPlatform {
  id: string
  name: string
  requires_2fa: boolean
}

export default function SetupRequestsPage() {
  const [requests, setRequests] = useState<SetupRequest[]>([])
  const [platforms, setPlatforms] = useState<SupportedPlatform[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string>("all")

  // Detail/assign dialog
  const [selectedRequest, setSelectedRequest] = useState<SetupRequest | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [adminNotes, setAdminNotes] = useState("")
  const [saving, setSaving] = useState(false)

  // Assign source dialog
  const [assignOpen, setAssignOpen] = useState(false)
  const [assignPlatform, setAssignPlatform] = useState("")
  const [assignEmail, setAssignEmail] = useState("")
  const [assignPassword, setAssignPassword] = useState("")
  const [assignTfaEmail, setAssignTfaEmail] = useState("")
  const [assignTfaPassword, setAssignTfaPassword] = useState("")
  const [showPasswords, setShowPasswords] = useState(false)
  const [assigning, setAssigning] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setIsLoading(true)
    try {
      const [reqRes, platRes] = await Promise.all([
        apiFetch("/api/onboarding/admin/setup-requests"),
        apiFetch("/api/onboarding/admin/supported-platforms"),
      ])

      if (reqRes) {
        const data = await reqRes.json()
        if (data.success) setRequests(data.data || [])
      }
      if (platRes) {
        const data = await platRes.json()
        if (data.success) setPlatforms(data.data || [])
      }
    } catch (err) {
      console.error("Failed to load setup requests:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const openDetail = (req: SetupRequest) => {
    setSelectedRequest(req)
    setAdminNotes(req.admin_notes || "")
    setDetailOpen(true)
  }

  const updateRequestStatus = async (status: string) => {
    if (!selectedRequest) return
    setSaving(true)
    try {
      const res = await apiFetch(
        `/api/onboarding/admin/setup-requests/${selectedRequest.id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status, admin_notes: adminNotes }),
        }
      )
      if (res) {
        const data = await res.json()
        if (data.success) {
          setRequests((prev) =>
            prev.map((r) =>
              r.id === selectedRequest.id
                ? { ...r, status: status as SetupRequest["status"], admin_notes: adminNotes }
                : r
            )
          )
          setSelectedRequest((prev) =>
            prev ? { ...prev, status: status as SetupRequest["status"], admin_notes: adminNotes } : null
          )
        }
      }
    } finally {
      setSaving(false)
    }
  }

  const openAssign = () => {
    setAssignPlatform("")
    setAssignEmail("")
    setAssignPassword("")
    setAssignTfaEmail("")
    setAssignTfaPassword("")
    setShowPasswords(false)
    setAssignOpen(true)
  }

  const assignSource = async () => {
    if (!selectedRequest || !assignPlatform || !assignEmail) return
    setAssigning(true)
    try {
      const platform = platforms.find((p) => p.id === assignPlatform)
      const body: Record<string, any> = {
        user_id: selectedRequest.user_id,
        platform: assignPlatform,
        credentials: { email: assignEmail, password: assignPassword },
      }

      if (platform?.requires_2fa && assignTfaEmail) {
        body.two_factor_auth = {
          enabled: true,
          email: assignTfaEmail,
          app_password: assignTfaPassword,
        }
      }

      const res = await apiFetch("/api/onboarding/admin/assign-source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })

      if (res) {
        const data = await res.json()
        if (data.success) {
          setAssignOpen(false)
          // Append note about assignment
          const platformName = platform?.name || assignPlatform
          const noteAddition = `Assigned ${platformName} (${assignEmail})`
          const updatedNotes = adminNotes
            ? `${adminNotes}\n${noteAddition}`
            : noteAddition
          setAdminNotes(updatedNotes)
          // Auto-save notes
          await apiFetch(
            `/api/onboarding/admin/setup-requests/${selectedRequest.id}`,
            {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ admin_notes: updatedNotes, status: "in_progress" }),
            }
          )
          setRequests((prev) =>
            prev.map((r) =>
              r.id === selectedRequest.id
                ? { ...r, status: "in_progress", admin_notes: updatedNotes }
                : r
            )
          )
          setSelectedRequest((prev) =>
            prev ? { ...prev, status: "in_progress", admin_notes: updatedNotes } : null
          )
        }
      }
    } finally {
      setAssigning(false)
    }
  }

  const filteredRequests =
    statusFilter === "all"
      ? requests
      : requests.filter((r) => r.status === statusFilter)

  const statusBadge = (status: string) => {
    switch (status) {
      case "pending":
        return (
          <Badge variant="outline" className="bg-yellow-50 text-yellow-700 border-yellow-200">
            <Clock className="h-3 w-3 mr-1" />
            Pending
          </Badge>
        )
      case "in_progress":
        return (
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            <AlertCircle className="h-3 w-3 mr-1" />
            In Progress
          </Badge>
        )
      case "completed":
        return (
          <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200">
            <CheckCircle className="h-3 w-3 mr-1" />
            Completed
          </Badge>
        )
      default:
        return <Badge variant="outline">{status}</Badge>
    }
  }

  const pendingCount = requests.filter((r) => r.status === "pending").length

  return (
    <SidebarWrapper>
      <div className="flex-1 p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <ClipboardList className="h-6 w-6" />
              Setup Requests
              {pendingCount > 0 && (
                <Badge className="ml-2 bg-yellow-500">{pendingCount} pending</Badge>
              )}
            </h1>
            <p className="text-muted-foreground mt-1">
              Review new customer onboarding requests and assign lead source integrations
            </p>
          </div>
          <Button variant="outline" onClick={loadData} disabled={isLoading}>
            <RefreshCw className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-3">
          <Label className="text-sm">Filter:</Label>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Requests</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="completed">Completed</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <Card>
          <CardHeader>
            <CardTitle>Customer Onboarding Requests</CardTitle>
            <CardDescription>
              Customers describe their platforms during signup. Review their info and
              assign the appropriate integrations.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : filteredRequests.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                {statusFilter === "all"
                  ? "No setup requests yet. New customer onboarding requests will appear here."
                  : `No ${statusFilter.replace("_", " ")} requests.`}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Customer</TableHead>
                    <TableHead>Platform Info</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Submitted</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRequests.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{req.user_name || "Unknown"}</p>
                          <p className="text-sm text-muted-foreground">{req.user_email}</p>
                        </div>
                      </TableCell>
                      <TableCell className="max-w-xs">
                        <p className="text-sm truncate">{req.platforms_description}</p>
                        {req.detected_platforms && req.detected_platforms.length > 0 && (
                          <div className="flex gap-1 mt-1 flex-wrap">
                            {req.detected_platforms.map((p) => {
                              const plat = platforms.find((pl) => pl.id === p)
                              return (
                                <Badge key={p} variant="secondary" className="text-xs">
                                  {plat?.name || p}
                                </Badge>
                              )
                            })}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>{statusBadge(req.status)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {new Date(req.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => openDetail(req)}
                        >
                          Review
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Detail Dialog */}
        <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
          <DialogContent className="max-w-xl">
            <DialogHeader>
              <DialogTitle>Setup Request</DialogTitle>
              <DialogDescription>
                {selectedRequest?.user_name || "Customer"} &mdash;{" "}
                {selectedRequest?.user_email}
              </DialogDescription>
            </DialogHeader>

            {selectedRequest && (
              <div className="space-y-4">
                {/* Status */}
                <div className="flex items-center gap-2">
                  <Label className="text-sm font-medium">Status:</Label>
                  {statusBadge(selectedRequest.status)}
                </div>

                {/* Platform description */}
                <div className="space-y-1">
                  <Label className="text-sm font-medium">
                    Customer&apos;s Platform Description
                  </Label>
                  <div className="rounded-lg bg-muted p-3 text-sm whitespace-pre-wrap">
                    {selectedRequest.platforms_description}
                  </div>
                </div>

                {/* Auto-detected platforms */}
                {selectedRequest.detected_platforms &&
                  selectedRequest.detected_platforms.length > 0 && (
                    <div className="space-y-1">
                      <Label className="text-sm font-medium">
                        Auto-Detected Platforms
                      </Label>
                      <div className="flex gap-2 flex-wrap">
                        {selectedRequest.detected_platforms.map((p) => {
                          const plat = platforms.find((pl) => pl.id === p)
                          return (
                            <Badge key={p} className="bg-green-100 text-green-800 border-green-200">
                              {plat?.name || p}
                            </Badge>
                          )
                        })}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        These platforms were detected from the customer&apos;s description.
                        Use &quot;Assign Lead Source&quot; below to configure each one.
                      </p>
                    </div>
                  )}

                {/* Admin notes */}
                <div className="space-y-1">
                  <Label htmlFor="admin-notes" className="text-sm font-medium">
                    Admin Notes
                  </Label>
                  <Textarea
                    id="admin-notes"
                    value={adminNotes}
                    onChange={(e) => setAdminNotes(e.target.value)}
                    placeholder="Track what integrations you've assigned, any issues, etc."
                    rows={4}
                  />
                </div>

                {/* Assign Source Button */}
                <Button onClick={openAssign} className="w-full" variant="outline">
                  <Plus className="h-4 w-4 mr-2" />
                  Assign Lead Source
                </Button>
              </div>
            )}

            <DialogFooter className="flex-col sm:flex-row gap-2">
              {selectedRequest?.status !== "completed" && (
                <>
                  {selectedRequest?.status === "pending" && (
                    <Button
                      variant="outline"
                      onClick={() => updateRequestStatus("in_progress")}
                      disabled={saving}
                    >
                      {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                      Mark In Progress
                    </Button>
                  )}
                  <Button
                    onClick={() => updateRequestStatus("completed")}
                    disabled={saving}
                  >
                    {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                    Mark Completed
                  </Button>
                </>
              )}
              {selectedRequest?.status === "completed" && (
                <Button
                  variant="outline"
                  onClick={() => updateRequestStatus("in_progress")}
                  disabled={saving}
                >
                  Reopen
                </Button>
              )}
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Assign Source Dialog */}
        <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Assign Lead Source</DialogTitle>
              <DialogDescription>
                Configure a lead source integration for{" "}
                {selectedRequest?.user_name || selectedRequest?.user_email}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Platform</Label>
                <Select value={assignPlatform} onValueChange={setAssignPlatform}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select platform..." />
                  </SelectTrigger>
                  <SelectContent>
                    {platforms.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.name} {p.requires_2fa ? "(2FA)" : ""}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="assign-email">Platform Email / Username</Label>
                <Input
                  id="assign-email"
                  value={assignEmail}
                  onChange={(e) => setAssignEmail(e.target.value)}
                  placeholder="user@example.com"
                />
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="assign-password">Platform Password</Label>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 px-2"
                    onClick={() => setShowPasswords(!showPasswords)}
                  >
                    {showPasswords ? (
                      <EyeOff className="h-3 w-3" />
                    ) : (
                      <Eye className="h-3 w-3" />
                    )}
                  </Button>
                </div>
                <Input
                  id="assign-password"
                  type={showPasswords ? "text" : "password"}
                  value={assignPassword}
                  onChange={(e) => setAssignPassword(e.target.value)}
                  placeholder="Platform password"
                />
              </div>

              {/* 2FA fields if needed */}
              {platforms.find((p) => p.id === assignPlatform)?.requires_2fa && (
                <>
                  <div className="border-t pt-4 space-y-2">
                    <p className="text-sm font-medium">
                      Two-Factor Authentication (Email/IMAP)
                    </p>
                    <div className="space-y-2">
                      <Label htmlFor="tfa-email">Gmail Address</Label>
                      <Input
                        id="tfa-email"
                        value={assignTfaEmail}
                        onChange={(e) => setAssignTfaEmail(e.target.value)}
                        placeholder="gmail@gmail.com"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="tfa-password">Gmail App Password</Label>
                      <Input
                        id="tfa-password"
                        type={showPasswords ? "text" : "password"}
                        value={assignTfaPassword}
                        onChange={(e) => setAssignTfaPassword(e.target.value)}
                        placeholder="xxxx xxxx xxxx xxxx"
                      />
                    </div>
                  </div>
                </>
              )}
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={() => setAssignOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={assignSource}
                disabled={!assignPlatform || !assignEmail || assigning}
              >
                {assigning ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Assign Source
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </SidebarWrapper>
  )
}
