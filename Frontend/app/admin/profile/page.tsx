"use client"

import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { SidebarWrapper } from "@/components/sidebar"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Loader2, CheckCircle } from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import { apiFetch } from "@/lib/api"

interface ProfileSettings {
  name: string
  email: string
  phone: string
  avatar: File | null
  avatarPreview: string | null
}

export default function AdminProfilePage() {
  const [settings, setSettings] = useState<ProfileSettings>({
    name: "",
    email: "",
    phone: "",
    avatar: null,
    avatarPreview: null,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState("")

  useEffect(() => {
    loadProfile()
  }, [])

  const loadProfile = async () => {
    setIsLoading(true)
    try {
      const supabase = createClient()
      const { data: { user } } = await supabase.auth.getUser()

      if (user) {
        setSettings({
          name: user.user_metadata?.full_name || user.user_metadata?.name || "",
          email: user.email || "",
          phone: user.phone || user.user_metadata?.phone || "",
          avatar: null,
          avatarPreview: user.user_metadata?.avatar_url || null,
        })
      }
    } catch (err) {
      console.error("Failed to load profile:", err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setSettings((prev) => ({ ...prev, [name]: value }))
    setSaveMessage("")
  }

  const handleAvatarChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!["image/jpeg", "image/png", "image/svg+xml"].includes(file.type)) {
        alert("Please upload a valid image file (JPG, PNG, or SVG)")
        return
      }

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

  const handleSave = async () => {
    setIsSaving(true)
    setSaveMessage("")
    try {
      const supabase = createClient()

      // Update user metadata in Supabase Auth
      const { error } = await supabase.auth.updateUser({
        data: {
          full_name: settings.name,
          phone: settings.phone,
        },
      })

      if (error) {
        setSaveMessage(`Error: ${error.message}`)
        return
      }

      // Also update user_profiles table if it exists
      const { data: { user } } = await supabase.auth.getUser()
      if (user) {
        await apiFetch("/api/supabase/user/profile", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            full_name: settings.name,
            phone: settings.phone,
          }),
        })
      }

      setSaveMessage("Profile saved successfully")
    } catch {
      setSaveMessage("Error: Failed to save profile")
    } finally {
      setIsSaving(false)
    }
  }

  const initials = settings.name
    ? settings.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "?"

  if (isLoading) {
    return (
      <SidebarWrapper role="admin">
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </SidebarWrapper>
    )
  }

  return (
    <SidebarWrapper role="admin">
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
                  <AvatarFallback>{initials}</AvatarFallback>
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
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={settings.email}
                  disabled
                  className="bg-muted"
                />
                <p className="text-xs text-muted-foreground">
                  Email cannot be changed here. Contact support if you need to update it.
                </p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="phone">Phone Number</Label>
                <Input id="phone" name="phone" type="tel" value={settings.phone} onChange={handleInputChange} />
              </div>

              {saveMessage && (
                <Alert variant={saveMessage.startsWith("Error") ? "destructive" : "default"}>
                  {!saveMessage.startsWith("Error") && <CheckCircle className="h-4 w-4" />}
                  <AlertDescription>{saveMessage}</AlertDescription>
                </Alert>
              )}

              <div className="flex justify-end">
                <Button onClick={handleSave} disabled={isSaving}>
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Save Changes
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </SidebarWrapper>
  )
}
