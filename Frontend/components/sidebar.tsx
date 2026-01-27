"use client"

import type React from "react"
import { useState } from "react"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BarChart3,
  Bell,
  Bot,
  Building2,
  ChevronDown,
  Home,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Settings,
  Settings2,
  Shuffle,
  LinkIcon as Source,
  Users,
  CreditCard,
  User2,
  UserCheck,
  UserX,
} from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubItem,
  SidebarMenuSubButton,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ThemeToggle } from "@/components/ui/theme-toggle"
import { useRouter } from "next/navigation"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { NotificationsMenu } from "@/components/ui/notifications-menu"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"

interface SidebarWrapperProps {
  children: React.ReactNode
  role: "admin" | "agent"
}

export function SidebarWrapper({ children, role }: SidebarWrapperProps) {
  return (
    <SidebarProvider defaultOpen={true}>
      <div className="flex min-h-screen">
        <AppSidebar role={role} />
        <div className="flex-1 flex flex-col overflow-hidden">
          <header className="sticky top-0 z-30 h-16 border-b bg-background px-6 grid grid-cols-[auto_1fr_auto] items-center">
            <div className="flex items-center gap-4">
              <SidebarTrigger />
              <h1 className="text-xl font-semibold whitespace-nowrap">LeadSynergy</h1>
            </div>
            <div />
            <div className="flex items-center gap-4">
              <ThemeToggle />
              <NotificationsMenu role={role} />
              <UserDropdown role={role} />
            </div>
          </header>
          <main className="flex-1 overflow-auto">
            <div className="container mx-auto py-6">{children}</div>
          </main>
        </div>
      </div>
    </SidebarProvider>
  )
}

function UserDropdown({ role }: { role: "admin" | "agent" }) {
  const router = useRouter()

  const handleLogout = () => {
    // In a real app, perform logout actions (clear session, etc.)
    router.push("/login")
  }

  const handleOpenSettings = () => {
    router.push(role === "admin" ? "/admin/profile" : "/agent/profile")
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" className="relative h-10 w-10 rounded-full">
          <Avatar className="h-10 w-10">
            <AvatarFallback>{role === "admin" ? "AD" : "AG"}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-56" align="end" forceMount>
        <DropdownMenuLabel>
          <div className="flex flex-col space-y-1">
            <p className="text-sm font-medium leading-none">{role === "admin" ? "Admin User" : "Agent User"}</p>
            <p className="text-xs leading-none text-muted-foreground">
              {role === "admin" ? "admin@leadsynergy.io" : "agent@leadsynergy.io"}
            </p>
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={handleOpenSettings}>
          <Settings className="mr-2 h-4 w-4" />
          <span>Settings</span>
        </DropdownMenuItem>
        {role === "admin" && (
          <DropdownMenuItem asChild>
            <Link href="/admin/billing">
              <CreditCard className="mr-2 h-4 w-4" />
              <span>Billing & Subscription</span>
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuSeparator />
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <DropdownMenuItem onSelect={(e) => e.preventDefault()}>
              <LogOut className="mr-2 h-4 w-4" />
              <span>Log out</span>
            </DropdownMenuItem>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Are you sure you want to log out?</AlertDialogTitle>
              <AlertDialogDescription>
                You will be redirected to the login page.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleLogout}>Log out</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

function AppSidebar({ role }: { role: "admin" | "agent" }) {
  const pathname = usePathname()
  const router = useRouter()
  const [leadsOpen, setLeadsOpen] = useState(pathname.includes('/leads') || pathname.includes('/agent/leads'))
  const [aiAgentOpen, setAiAgentOpen] = useState(pathname.includes('/ai-agent'))

  const handleLogoutAndRedirect = () => {
    // In a real app, perform logout actions (clear session, etc.)
    router.push("/")
  }

  // AI Agent submenu items
  const aiAgentSubMenuItems = [
    {
      title: "AI Settings",
      href: "/admin/ai-agent/settings",
      icon: Settings2,
    },
    {
      title: "AI Analytics",
      href: "/admin/ai-agent/analytics",
      icon: BarChart3,
    },
  ]

  // Lead submenu items for admin
  const leadSubMenuItems = [
    {
      title: "All Leads",
      href: "/admin/leads",
      icon: BarChart3,
    },
    {
      title: "Assigned Leads",
      href: "/admin/leads/assigned",
      icon: UserCheck,
    },
    {
      title: "Unassigned Leads",
      href: "/admin/leads/unassigned",
      icon: UserX,
    },
  ]

  const adminMenuItems = [
    {
      title: "Dashboard",
      href: "/admin/dashboard",
      icon: LayoutDashboard,
    },
    // "Leads" will be rendered as a collapsible section
    {
      title: "Assignment Rules",
      href: "/admin/assignment-rules",
      icon: Shuffle,
    },
    {
      title: "Notifications",
      href: "/admin/notifications",
      icon: Bell,
    },
    {
      title: "Lead Sources",
      href: "/admin/lead-sources",
      icon: Source,
    },
    {
      title: "Team Management",
      href: "/admin/team",
      icon: Users,
    },
    {
      title: "Billing",
      href: "/admin/billing",
      icon: CreditCard,
    },
    {
      title: "Company Settings",
      href: "/admin/company",
      icon: Building2,
    },
    {
      title: "Profile Settings",
      href: "/admin/profile",
      icon: User2,
    },
  ]

  const agentMenuItems = [
    {
      title: "Dashboard",
      href: "/agent/dashboard",
      icon: LayoutDashboard,
    },
    {
      title: "My Leads",
      href: "/agent/leads",
      icon: BarChart3,
    },
    {
      title: "Notes",
      href: "/agent/notes",
      icon: MessageSquare,
    },
    {
      title: "Commissions",
      href: "/agent/commissions",
      icon: BarChart3,
    },
    {
      title: "Profile Settings",
      href: "/agent/profile",
      icon: User2,
    },
  ]

  const menuItems = role === "admin" ? adminMenuItems : agentMenuItems

  return (
    <Sidebar>
      <SidebarHeader className="border-b">
        <div className="flex items-center gap-2">
          <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
            <span className="text-white font-bold">LS</span>
          </div>
          <span className="text-xl font-bold">LeadSynergy</span>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarMenu>
          {role === "admin" ? (
            <>
              {/* Dashboard */}
              <SidebarMenuItem>
                <SidebarMenuButton asChild isActive={pathname === "/admin/dashboard"} tooltip="Dashboard" className="px-4 py-3">
                  <Link href="/admin/dashboard">
                    <LayoutDashboard className="h-5 w-5" />
                    <span className="ml-3">Dashboard</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>

              {/* Collapsible AI Agent Section */}
              <SidebarMenuItem>
                <Collapsible open={aiAgentOpen} onOpenChange={setAiAgentOpen}>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip="AI Agent"
                      className="px-4 py-3 w-full justify-between"
                      isActive={pathname.includes('/admin/ai-agent')}
                    >
                      <div className="flex items-center">
                        <Bot className="h-5 w-5" />
                        <span className="ml-3">AI Agent</span>
                      </div>
                      <ChevronDown className={`h-4 w-4 transition-transform ${aiAgentOpen ? 'rotate-180' : ''}`} />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      {aiAgentSubMenuItems.map((item) => (
                        <SidebarMenuSubItem key={item.href}>
                          <SidebarMenuSubButton asChild isActive={pathname === item.href}>
                            <Link href={item.href}>
                              <item.icon className="h-4 w-4" />
                              <span className="ml-3 text-sm">{item.title}</span>
                            </Link>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </Collapsible>
              </SidebarMenuItem>

              {/* Collapsible Leads Section */}
              <SidebarMenuItem>
                <Collapsible open={leadsOpen} onOpenChange={setLeadsOpen}>
                  <CollapsibleTrigger asChild>
                    <SidebarMenuButton
                      tooltip="Leads"
                      className="px-4 py-3 w-full justify-between"
                      isActive={pathname.includes('/admin/leads')}
                    >
                      <div className="flex items-center">
                        <BarChart3 className="h-5 w-5" />
                        <span className="ml-3">Leads</span>
                      </div>
                      <ChevronDown className={`h-4 w-4 transition-transform ${leadsOpen ? 'rotate-180' : ''}`} />
                    </SidebarMenuButton>
                  </CollapsibleTrigger>
                  <CollapsibleContent>
                    <SidebarMenuSub>
                      {leadSubMenuItems.map((item) => (
                        <SidebarMenuSubItem key={item.href}>
                          <SidebarMenuSubButton asChild isActive={pathname === item.href}>
                            <Link href={item.href}>
                              <item.icon className="h-4 w-4" />
                              <span className="ml-3 text-sm">{item.title}</span>
                            </Link>
                          </SidebarMenuSubButton>
                        </SidebarMenuSubItem>
                      ))}
                    </SidebarMenuSub>
                  </CollapsibleContent>
                </Collapsible>
              </SidebarMenuItem>

              {/* Rest of admin menu items */}
              {adminMenuItems.slice(1).map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton asChild isActive={pathname === item.href} tooltip={item.title} className="px-4 py-3">
                    <Link href={item.href}>
                      <item.icon className="h-5 w-5" />
                      <span className="ml-3">{item.title}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </>
          ) : (
            /* Agent menu - no collapsible needed */
            menuItems.map((item) => (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton asChild isActive={pathname === item.href} tooltip={item.title} className="px-4 py-3">
                  <Link href={item.href}>
                    <item.icon className="h-5 w-5" />
                    <span className="ml-3">{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))
          )}
        </SidebarMenu>
      </SidebarContent>
      <SidebarFooter className="border-t">
        <div className="p-2">
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" className="w-full justify-start">
                <Home className="mr-2 h-5 w-5" />
                Back to Home
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Are you sure you want to log out?</AlertDialogTitle>
                <AlertDialogDescription>
                  You will be redirected to the home page.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Cancel</AlertDialogCancel>
                <AlertDialogAction onClick={handleLogoutAndRedirect}>Log out</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </SidebarFooter>
    </Sidebar>
  )
}
