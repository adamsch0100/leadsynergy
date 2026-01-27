"use client"

import { useState, useEffect } from "react"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Separator } from "@/components/ui/separator"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Bot,
  Pause,
  Play,
  AlertTriangle,
  MessageSquare,
  FileText,
  Activity,
  RefreshCw,
  User,
  Clock,
  TrendingUp,
  X
} from "lucide-react"
import { cn } from "@/lib/utils"
import { ConversationTimeline } from "./ConversationTimeline"
import { UpdateNotesManager } from "./UpdateNotesManager"

interface LeadAIPanelProps {
  personId: number | null
  leadName?: string
  isOpen: boolean
  onClose: () => void
  userId?: string
}

interface MonitoringData {
  person_id: number
  conversation: any
  messages: any[]
  ai_settings: any
  pending_notes: any[]
  all_notes: any[]
  recent_activity: any[]
  summary: {
    state: string
    score: number | null
    messages_sent: number
    messages_received: number
    ai_enabled: boolean | null
    pending_notes_count: number
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function LeadAIPanel({
  personId,
  leadName,
  isOpen,
  onClose,
  userId
}: LeadAIPanelProps) {
  const [data, setData] = useState<MonitoringData | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isActioning, setIsActioning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    if (!personId) return

    setIsLoading(true)
    setError(null)

    try {
      const headers: Record<string, string> = {}
      if (userId) {
        headers['X-User-ID'] = userId
        headers['X-User-Email'] = userId
      }

      const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/lead/${personId}/details`, {
        headers
      })
      const result = await res.json()

      if (result.success) {
        setData(result)
      } else {
        setError(result.error || 'Failed to load data')
      }
    } catch (err) {
      setError('Failed to connect to server')
      console.error('Error fetching monitoring data:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen && personId) {
      fetchData()
    }
  }, [isOpen, personId])

  const performAction = async (action: 'pause' | 'resume' | 'escalate') => {
    if (!personId) return

    setIsActioning(true)
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      }
      if (userId) {
        headers['X-User-ID'] = userId
        headers['X-User-Email'] = userId
      }

      const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/lead/${personId}/action`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ action })
      })
      const result = await res.json()

      if (result.success) {
        // Refresh data
        await fetchData()
      } else {
        setError(result.error || `Failed to ${action}`)
      }
    } catch (err) {
      setError(`Failed to ${action}`)
      console.error(`Error performing ${action}:`, err)
    } finally {
      setIsActioning(false)
    }
  }

  const approveNote = async (noteId: string) => {
    const headers: Record<string, string> = {}
    if (userId) {
      headers['X-User-ID'] = userId
      headers['X-User-Email'] = userId
    }

    const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/notes/${noteId}/approve`, {
      method: 'POST',
      headers
    })
    const result = await res.json()

    if (result.success) {
      await fetchData()
    } else {
      throw new Error(result.error || 'Failed to approve note')
    }
  }

  const dismissNote = async (noteId: string) => {
    const headers: Record<string, string> = {}
    if (userId) {
      headers['X-User-ID'] = userId
      headers['X-User-Email'] = userId
    }

    const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/notes/${noteId}/dismiss`, {
      method: 'POST',
      headers
    })
    const result = await res.json()

    if (result.success) {
      await fetchData()
    } else {
      throw new Error(result.error || 'Failed to dismiss note')
    }
  }

  const bulkApproveNotes = async (noteIds: string[]) => {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (userId) {
      headers['X-User-ID'] = userId
      headers['X-User-Email'] = userId
    }

    const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/notes/bulk-approve`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ note_ids: noteIds })
    })
    const result = await res.json()

    if (result.success) {
      await fetchData()
    } else {
      throw new Error(result.error || 'Failed to bulk approve notes')
    }
  }

  const getStateColor = (state: string) => {
    const colors: Record<string, string> = {
      initial: "bg-blue-100 text-blue-700",
      qualifying: "bg-yellow-100 text-yellow-700",
      scheduling: "bg-purple-100 text-purple-700",
      handed_off: "bg-green-100 text-green-700",
      completed: "bg-gray-100 text-gray-700",
      escalated: "bg-red-100 text-red-700",
      nurturing: "bg-cyan-100 text-cyan-700",
    }
    return colors[state] || "bg-gray-100 text-gray-700"
  }

  const isAIEnabled = data?.ai_settings?.ai_enabled === true

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-lg overflow-hidden flex flex-col">
        <SheetHeader>
          <div className="flex items-center justify-between">
            <div>
              <SheetTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5 text-primary" />
                AI Monitor: {leadName || `Person #${personId}`}
              </SheetTitle>
              <SheetDescription>
                View AI conversation and manage settings
              </SheetDescription>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={fetchData}
              disabled={isLoading}
            >
              <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
            </Button>
          </div>
        </SheetHeader>

        {error && (
          <div className="bg-red-50 text-red-700 px-3 py-2 rounded-md text-sm">
            {error}
          </div>
        )}

        {isLoading ? (
          <div className="space-y-4 py-4">
            <Skeleton className="h-20 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        ) : data ? (
          <>
            {/* Status Summary */}
            <div className="grid grid-cols-2 gap-3 py-4">
              <div className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Status</span>
                  <Badge className={cn("text-xs", getStateColor(data.summary.state))}>
                    {data.summary.state}
                  </Badge>
                </div>
              </div>

              <div className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Score</span>
                  <span className="font-semibold">
                    {data.summary.score !== null ? `${data.summary.score}/100` : '-'}
                  </span>
                </div>
              </div>

              <div className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    {data.summary.messages_sent} sent, {data.summary.messages_received} received
                  </span>
                </div>
              </div>

              <div className="bg-muted/50 rounded-lg p-3">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm">
                    {data.summary.pending_notes_count} pending notes
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-2 pb-4">
              {isAIEnabled ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => performAction('pause')}
                  disabled={isActioning}
                  className="text-yellow-600 border-yellow-300 hover:bg-yellow-50"
                >
                  <Pause className="h-4 w-4 mr-1" />
                  Pause AI
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => performAction('resume')}
                  disabled={isActioning}
                  className="text-green-600 border-green-300 hover:bg-green-50"
                >
                  <Play className="h-4 w-4 mr-1" />
                  Resume AI
                </Button>
              )}

              <Button
                variant="outline"
                size="sm"
                onClick={() => performAction('escalate')}
                disabled={isActioning || data.summary.state === 'escalated'}
                className="text-red-600 border-red-300 hover:bg-red-50"
              >
                <AlertTriangle className="h-4 w-4 mr-1" />
                Escalate
              </Button>
            </div>

            <Separator />

            {/* Tabs */}
            <Tabs defaultValue="conversation" className="flex-1 overflow-hidden flex flex-col">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="conversation">
                  <MessageSquare className="h-4 w-4 mr-1" />
                  Chat
                </TabsTrigger>
                <TabsTrigger value="notes">
                  <FileText className="h-4 w-4 mr-1" />
                  Notes
                  {data.summary.pending_notes_count > 0 && (
                    <Badge variant="secondary" className="ml-1 text-xs">
                      {data.summary.pending_notes_count}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="data">
                  <Activity className="h-4 w-4 mr-1" />
                  Data
                </TabsTrigger>
              </TabsList>

              <TabsContent value="conversation" className="flex-1 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-400px)]">
                  <ConversationTimeline messages={data.messages} />
                </ScrollArea>
              </TabsContent>

              <TabsContent value="notes" className="flex-1 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-400px)]">
                  <UpdateNotesManager
                    notes={data.all_notes}
                    onApprove={approveNote}
                    onDismiss={dismissNote}
                    onBulkApprove={bulkApproveNotes}
                  />
                </ScrollArea>
              </TabsContent>

              <TabsContent value="data" className="flex-1 overflow-hidden">
                <ScrollArea className="h-[calc(100vh-400px)]">
                  <div className="space-y-4 py-2">
                    {/* Extracted Data */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Extracted Data</h4>
                      {data.conversation?.qualification_data ? (
                        <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                          {Object.entries(data.conversation.qualification_data).map(([key, value]) => (
                            <div key={key} className="flex items-center justify-between text-sm">
                              <span className="text-muted-foreground capitalize">
                                {key.replace(/_/g, ' ')}
                              </span>
                              <span className="font-medium">
                                {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value)}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">No data extracted yet</p>
                      )}
                    </div>

                    {/* AI Settings */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">AI Settings</h4>
                      <div className="bg-muted/50 rounded-lg p-3 space-y-2">
                        <div className="flex items-center justify-between text-sm">
                          <span className="text-muted-foreground">AI Enabled</span>
                          <Badge variant={isAIEnabled ? "default" : "secondary"}>
                            {isAIEnabled ? 'ON' : 'OFF'}
                          </Badge>
                        </div>
                        {data.ai_settings?.auto_respond !== undefined && (
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-muted-foreground">Auto Respond</span>
                            <Badge variant={data.ai_settings.auto_respond ? "default" : "secondary"}>
                              {data.ai_settings.auto_respond ? 'ON' : 'OFF'}
                            </Badge>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Recent Activity */}
                    <div>
                      <h4 className="text-sm font-medium mb-2">Recent Activity</h4>
                      {data.recent_activity.length > 0 ? (
                        <div className="space-y-2">
                          {data.recent_activity.slice(0, 5).map((activity: any) => (
                            <div
                              key={activity.id}
                              className="flex items-center gap-2 text-sm bg-muted/50 rounded-lg p-2"
                            >
                              <Clock className="h-3 w-3 text-muted-foreground" />
                              <span className="flex-1 truncate">{activity.description}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">No recent activity</p>
                      )}
                    </div>
                  </div>
                </ScrollArea>
              </TabsContent>
            </Tabs>
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <Bot className="h-8 w-8 mb-2 opacity-50" />
            <p className="text-sm">Select a lead to view AI monitoring data</p>
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
