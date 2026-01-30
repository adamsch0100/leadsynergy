"use client"

import { useEffect, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  Bot,
  MessageSquare,
  AlertTriangle,
  Play,
  Pause,
  UserPlus,
  FileText,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Activity,
  CalendarCheck,
  UserX,
  Lightbulb,
  ShieldAlert,
} from "lucide-react"
import { cn } from "@/lib/utils"

interface ActivityEvent {
  id: string
  person_id: number
  activity_type: string
  description: string
  activity_data?: Record<string, any>
  created_at: string
}

interface AIActivityFeedProps {
  userId?: string
  onLeadClick?: (personId: number) => void
  className?: string
  defaultOpen?: boolean
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function AIActivityFeed({
  userId,
  onLeadClick,
  className,
  defaultOpen = true
}: AIActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityEvent[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [error, setError] = useState<string | null>(null)

  const fetchActivities = async () => {
    try {
      setIsLoading(true)
      const headers: Record<string, string> = {}
      if (userId) {
        headers['X-User-ID'] = userId
      }

      const res = await fetch(`${API_BASE_URL}/api/ai-monitoring/activity-feed?limit=20`, {
        headers
      })
      const data = await res.json()

      if (data.success) {
        setActivities(data.activities || [])
        setError(null)
      } else {
        setError(data.error || 'Failed to load activities')
      }
    } catch (err) {
      setError('Failed to connect to server')
      console.error('Error fetching activities:', err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchActivities()
    // Refresh every 30 seconds
    const interval = setInterval(fetchActivities, 30000)
    return () => clearInterval(interval)
  }, [userId])

  const getActivityIcon = (activityType: string) => {
    const icons: Record<string, any> = {
      message_sent: MessageSquare,
      message_received: MessageSquare,
      state_changed: Activity,
      escalated: AlertTriangle,
      paused: Pause,
      resumed: Play,
      note_created: FileText,
      note_approved: FileText,
      deferred_followup_scheduled: CalendarCheck,
      stale_handoff_detected: UserX,
      nba_recommendation: Lightbulb,
      dropped_ball_alert: ShieldAlert,
    }
    return icons[activityType] || Bot
  }

  const getActivityColor = (activityType: string) => {
    const colors: Record<string, string> = {
      message_sent: "text-primary bg-primary/10",
      message_received: "text-blue-600 bg-blue-100",
      state_changed: "text-purple-600 bg-purple-100",
      escalated: "text-red-600 bg-red-100",
      paused: "text-yellow-600 bg-yellow-100",
      resumed: "text-green-600 bg-green-100",
      note_created: "text-cyan-600 bg-cyan-100",
      note_approved: "text-green-600 bg-green-100",
      deferred_followup_scheduled: "text-blue-600 bg-blue-100",
      stale_handoff_detected: "text-red-600 bg-red-100",
      nba_recommendation: "text-yellow-600 bg-yellow-100",
      dropped_ball_alert: "text-orange-600 bg-orange-100",
    }
    return colors[activityType] || "text-gray-600 bg-gray-100"
  }

  const formatTimeAgo = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMins / 60)

    if (diffMins < 1) return 'now'
    if (diffMins < 60) return `${diffMins}m`
    if (diffHours < 24) return `${diffHours}h`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className={className}>
      <div className="border rounded-lg bg-card">
        <CollapsibleTrigger asChild>
          <div className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-muted/50 transition-colors">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-primary" />
              <span className="font-medium">AI Activity Feed</span>
              {activities.length > 0 && (
                <Badge variant="secondary" className="text-xs">
                  {activities.length} recent
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={(e) => {
                  e.stopPropagation()
                  fetchActivities()
                }}
              >
                <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
              </Button>
              {isOpen ? (
                <ChevronUp className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              )}
            </div>
          </div>
        </CollapsibleTrigger>

        <CollapsibleContent>
          <div className="border-t">
            {error ? (
              <div className="px-4 py-3 text-sm text-red-600">
                {error}
              </div>
            ) : activities.length === 0 ? (
              <div className="px-4 py-6 text-center text-muted-foreground text-sm">
                No recent AI activity
              </div>
            ) : (
              <ScrollArea className="h-[200px]">
                <div className="divide-y">
                  {activities.map((activity) => {
                    const Icon = getActivityIcon(activity.activity_type)
                    const colorClass = getActivityColor(activity.activity_type)

                    return (
                      <div
                        key={activity.id}
                        className={cn(
                          "flex items-center gap-3 px-4 py-2 hover:bg-muted/50 transition-colors",
                          onLeadClick && "cursor-pointer"
                        )}
                        onClick={() => onLeadClick?.(activity.person_id)}
                      >
                        <div className={cn("p-1.5 rounded-full", colorClass)}>
                          <Icon className="h-3.5 w-3.5" />
                        </div>

                        <div className="flex-1 min-w-0">
                          <p className="text-sm truncate">{activity.description}</p>
                          <p className="text-xs text-muted-foreground">
                            Person #{activity.person_id}
                          </p>
                        </div>

                        <span className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatTimeAgo(activity.created_at)}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </ScrollArea>
            )}
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  )
}
