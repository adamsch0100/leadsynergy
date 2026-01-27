"use client"

import { cn } from "@/lib/utils"
import { Badge } from "@/components/ui/badge"
import { MessageSquare, Bot, User, Clock, AlertTriangle } from "lucide-react"

interface Message {
  id: string
  person_id: number
  direction: "inbound" | "outbound"
  message_content: string
  created_at: string
  detected_intent?: string
  sentiment?: string
  error_message?: string
}

interface ConversationTimelineProps {
  messages: Message[]
  className?: string
}

export function ConversationTimeline({ messages, className }: ConversationTimelineProps) {
  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    })
  }

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const today = new Date()
    const yesterday = new Date(today)
    yesterday.setDate(yesterday.getDate() - 1)

    if (date.toDateString() === today.toDateString()) {
      return 'Today'
    } else if (date.toDateString() === yesterday.toDateString()) {
      return 'Yesterday'
    } else {
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  // Group messages by date
  const messagesByDate: { [date: string]: Message[] } = {}
  messages.forEach(msg => {
    const dateKey = new Date(msg.created_at).toDateString()
    if (!messagesByDate[dateKey]) {
      messagesByDate[dateKey] = []
    }
    messagesByDate[dateKey].push(msg)
  })

  const getSentimentColor = (sentiment?: string) => {
    if (!sentiment) return ''
    if (sentiment.includes('positive')) return 'text-green-600'
    if (sentiment.includes('negative')) return 'text-red-600'
    return 'text-gray-600'
  }

  if (messages.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center py-8 text-muted-foreground", className)}>
        <MessageSquare className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No conversation history yet</p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", className)}>
      {Object.entries(messagesByDate).map(([dateKey, msgs]) => (
        <div key={dateKey} className="space-y-2">
          {/* Date separator */}
          <div className="flex items-center gap-2 py-1">
            <div className="h-px flex-1 bg-border" />
            <span className="text-xs text-muted-foreground px-2">
              {formatDate(msgs[0].created_at)}
            </span>
            <div className="h-px flex-1 bg-border" />
          </div>

          {/* Messages for this date */}
          {msgs.map((message) => (
            <div
              key={message.id}
              className={cn(
                "flex gap-2",
                message.direction === "outbound" ? "flex-row" : "flex-row-reverse"
              )}
            >
              {/* Avatar */}
              <div
                className={cn(
                  "flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center",
                  message.direction === "outbound"
                    ? "bg-primary/10 text-primary"
                    : "bg-blue-100 text-blue-600"
                )}
              >
                {message.direction === "outbound" ? (
                  <Bot className="h-4 w-4" />
                ) : (
                  <User className="h-4 w-4" />
                )}
              </div>

              {/* Message bubble */}
              <div
                className={cn(
                  "max-w-[80%] rounded-lg px-3 py-2",
                  message.direction === "outbound"
                    ? "bg-primary/10 text-foreground"
                    : "bg-blue-50 text-foreground"
                )}
              >
                <p className="text-sm whitespace-pre-wrap">{message.message_content}</p>

                {/* Message metadata */}
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" />
                    {formatTime(message.created_at)}
                  </span>

                  {message.detected_intent && (
                    <Badge variant="outline" className="text-xs py-0 h-5">
                      {message.detected_intent}
                    </Badge>
                  )}

                  {message.sentiment && (
                    <span className={cn("text-xs", getSentimentColor(message.sentiment))}>
                      {message.sentiment}
                    </span>
                  )}

                  {message.error_message && (
                    <Badge variant="destructive" className="text-xs py-0 h-5">
                      <AlertTriangle className="h-3 w-3 mr-1" />
                      Error
                    </Badge>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
