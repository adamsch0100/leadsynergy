"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SidebarWrapper } from "@/components/sidebar"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { Switch } from "@/components/ui/switch"

interface ProfileSettings {
  name: string
  email: string
  phone: string
  avatar: File | null
  avatarPreview: string | null
  notificationPreferences: {
    emailLeads: boolean
    emailCommissions: boolean
    smsLeads: boolean
    smsCommissions: boolean
  }
}

export default function AgentProfilePage() {
  const [settings, setSettings] = useState<ProfileSettings>({
    name: "Agent User",
    email: "agent@leadsynergy.io",
    phone: "+1 (555) 123-4567",
    avatar: null,
    avatarPreview: "/placeholder.svg?height=100&width=100",
    notificationPreferences: {
      emailLeads: true,
      emailCommissions: true,
      smsLeads: false,
      smsCommissions: false,
    },
  })

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setSettings((prev) => ({ ...prev, [name]: value }))
  }

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      // Validate file type
      if (!["image/jpeg", "image/png", "image/svg+xml"].includes(file.type)) {
        alert("Please upload a valid image file (JPG, PNG, or SVG)")
        return
      }

      // Validate file size (max 2MB)
      if (file.size > 2 * 1024 * 1024) {
        alert("File size should be less than 2MB")
        return
      }

      const reader = new FileReader()
      reader.onload = (event) => {
        setSettings({
          ...settings,
          avatar: file,
          avatarPreview: event.target?.result as string,
        })
      }
      reader.readAsDataURL(file)
    }
  }

  const handleToggleNotification = (key: keyof typeof settings.notificationPreferences) => {
    setSettings((prev) => ({
      ...prev,
      notificationPreferences: {
        ...prev.notificationPreferences,
        [key]: !prev.notificationPreferences[key],
      },
    }))
  }

  const handleSave = () => {
    // In a real app, this would save to the backend
    alert("Profile settings saved successfully!")
  }

  return (
    <SidebarWrapper role="agent">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Profile Settings</h1>
          <p className="text-muted-foreground">Manage your personal information and preferences</p>
        </div>
      </div>

      <div className="grid gap-8 max-w-2xl">
        <Card>
          <CardHeader>
            <CardTitle>Personal Information</CardTitle>
            <CardDescription>Update your profile details and contact information</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6">
              <div className="flex items-center gap-6">
                <Avatar className="h-24 w-24">
                  <AvatarImage src={settings.avatarPreview || ""} alt={settings.name} />
                  <AvatarFallback>AG</AvatarFallback>
                </Avatar>
                <div>
                  <Button variant="outline" className="mb-2" onClick={() => document.getElementById("avatar")?.click()}>
                    Change Avatar
                  </Button>
                  <input
                    type="file"
                    id="avatar"
                    className="hidden"
                    accept="image/jpeg,image/png,image/svg+xml"
                    onChange={handleAvatarChange}
                  />
                  <p className="text-sm text-muted-foreground">
                    Recommended: Square JPG, PNG, or SVG (max 2MB)
                  </p>
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="name">Full Name</Label>
                <Input id="name" name="name" value={settings.name} onChange={handleInputChange} />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="email">Email Address</Label>
                <Input id="email" name="email" type="email" value={settings.email} onChange={handleInputChange} />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="phone">Phone Number</Label>
                <Input id="phone" name="phone" type="tel" value={settings.phone} onChange={handleInputChange} />
              </div>
            </div>

            <Separator className="my-6" />

            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium">Notification Preferences</h3>
                <p className="text-sm text-muted-foreground">Choose how you want to receive notifications</p>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Email Notifications - New Leads</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive email notifications when new leads are assigned
                    </p>
                  </div>
                  <Switch
                    checked={settings.notificationPreferences.emailLeads}
                    onCheckedChange={() => handleToggleNotification("emailLeads")}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>Email Notifications - Commissions</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive email notifications about commission updates
                    </p>
                  </div>
                  <Switch
                    checked={settings.notificationPreferences.emailCommissions}
                    onCheckedChange={() => handleToggleNotification("emailCommissions")}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>SMS Notifications - New Leads</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive SMS notifications when new leads are assigned
                    </p>
                  </div>
                  <Switch
                    checked={settings.notificationPreferences.smsLeads}
                    onCheckedChange={() => handleToggleNotification("smsLeads")}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <Label>SMS Notifications - Commissions</Label>
                    <p className="text-sm text-muted-foreground">
                      Receive SMS notifications about commission updates
                    </p>
                  </div>
                  <Switch
                    checked={settings.notificationPreferences.smsCommissions}
                    onCheckedChange={() => handleToggleNotification("smsCommissions")}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <Button onClick={handleSave}>Save Changes</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </SidebarWrapper>
  )
}