"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { HelpCircle, Ticket, Plus, Mail } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

export function HelpWidget() {
  const pathname = usePathname()

  // Don't show widget on the help page itself
  if (pathname === "/agent/help") return null

  return (
    <div className="fixed bottom-6 right-6 z-50 hidden sm:block">
      <Popover>
        <PopoverTrigger asChild>
          <Button
            size="lg"
            className="h-14 w-14 rounded-full shadow-lg hover:shadow-xl transition-shadow"
          >
            <HelpCircle className="h-6 w-6" />
            <span className="sr-only">Help & Support</span>
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" side="top" sideOffset={12} className="w-72 p-0">
          <div className="p-4 border-b">
            <h3 className="font-semibold">Need Help?</h3>
            <p className="text-sm text-muted-foreground">We&apos;re here to assist you</p>
          </div>
          <div className="p-2">
            <Link href="/agent/help?tab=new-ticket">
              <button className="w-full flex items-center gap-3 p-3 rounded-md hover:bg-muted text-left transition-colors">
                <Plus className="h-4 w-4 text-primary flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">Submit a Ticket</p>
                  <p className="text-xs text-muted-foreground">Get help with an issue</p>
                </div>
              </button>
            </Link>
            <Link href="/agent/help">
              <button className="w-full flex items-center gap-3 p-3 rounded-md hover:bg-muted text-left transition-colors">
                <Ticket className="h-4 w-4 text-primary flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">View My Tickets</p>
                  <p className="text-xs text-muted-foreground">Track your support requests</p>
                </div>
              </button>
            </Link>
            <div className="my-1 border-t" />
            <a href="mailto:support@leadsynergy.io">
              <button className="w-full flex items-center gap-3 p-3 rounded-md hover:bg-muted text-left transition-colors">
                <Mail className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium">Email Support</p>
                  <p className="text-xs text-muted-foreground">support@leadsynergy.io</p>
                </div>
              </button>
            </a>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  )
}
