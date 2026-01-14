"use client"

import * as React from "react"
import { formatDistanceToNow } from "date-fns"
import { Bell, CheckCircle2, DollarSign, UserPlus } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Badge } from "@/components/ui/badge"

interface Notification {
  id: string
  title: string
  description: string
  timestamp: Date
  read: boolean
  type: "lead" | "commission" | "system"
}

interface NotificationsMenuProps {
  role: "admin" | "agent"
}

export function NotificationsMenu({ role }: NotificationsMenuProps) {
  const [notifications, setNotifications] = React.useState<Notification[]>([
    {
      id: "1",
      title: "New Lead Assigned",
      description: "John Smith has been assigned to you",
      timestamp: new Date(Date.now() - 1000 * 60 * 30), // 30 minutes ago
      read: false,
      type: "lead",
    },
    {
      id: "2",
      title: "Commission Update",
      description: "Your commission for 123 Main St has been approved",
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 2), // 2 hours ago
      read: false,
      type: "commission",
    },
    {
      id: "3",
      title: "New Agent Joined",
      description: "Sarah Johnson has joined the team",
      timestamp: new Date(Date.now() - 1000 * 60 * 60 * 24), // 1 day ago
      read: true,
      type: "system",
    },
  ])

  const unreadCount = notifications.filter((n) => !n.read).length

  const handleMarkAsRead = (notificationId: string) => {
    setNotifications((prev) =>
      prev.map((n) =>
        n.id === notificationId ? { ...n, read: true } : n
      )
    )
  }

  const getIcon = (type: Notification["type"]) => {
    switch (type) {
      case "lead":
        return <UserPlus className="h-4 w-4 text-blue-500" />
      case "commission":
        return <DollarSign className="h-4 w-4 text-green-500" />
      case "system":
        return <CheckCircle2 className="h-4 w-4 text-purple-500" />
    }
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="icon" className="relative">
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <Badge
              variant="default"
              className="absolute -right-1 -top-1 h-5 w-5 rounded-full p-0 flex items-center justify-center"
            >
              {unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-80" align="end">
        <DropdownMenuLabel className="font-normal">
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">Notifications</p>
            <p className="text-xs text-muted-foreground">
              {unreadCount} unread messages
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {notifications.length === 0 ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            No notifications
          </div>
        ) : (
          notifications.map((notification) => (
            <DropdownMenuItem
              key={notification.id}
              className="cursor-pointer"
              onClick={() => handleMarkAsRead(notification.id)}
            >
              <div className="flex items-start gap-3 py-2">
                <div className="mt-1">{getIcon(notification.type)}</div>
                <div className="flex-1 space-y-1">
                  <p className={`text-sm font-medium leading-none ${!notification.read ? "text-primary" : ""}`}>
                    {notification.title}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    {notification.description}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(notification.timestamp, { addSuffix: true })}
                  </p>
                </div>
              </div>
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}