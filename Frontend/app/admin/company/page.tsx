"use client"

import type React from "react"
import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Upload, X, RefreshCw, CheckCircle, AlertTriangle, DollarSign } from "lucide-react"
import { createClient } from "@/lib/supabase/client"
import type { User } from "@supabase/supabase-js"

interface CompanySettings {
  name: string
  address: string
  phone: string
  website: string
  logo: File | null
  logoPreview: string | null
  commissionRate: number
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export default function CompanySettingsPage() {
  const [settings, setSettings] = useState<CompanySettings>({
    name: "",
    address: "",
    phone: "",
    website: "",
    logo: null,
    logoPreview: null,
    commissionRate: 3, // Default 3%
  })
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load user session
  useEffect(() => {
    const loadUser = async () => {
      const supabase = createClient()
      const { data } = await supabase.auth.getUser()
      setUser(data.user ?? null)
    }
    loadUser()
  }, [])

  // Fetch company settings
  useEffect(() => {
    if (user) {
      fetchSettings()
    }
  }, [user])

  const fetchSettings = async () => {
    if (!user) return
    setIsLoading(true)
    try {
      // Fetch company settings and commission rate in parallel
      const [companyRes, commissionRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/supabase/settings/company`, {
          headers: { 'X-User-ID': user.id }
        }),
        fetch(`${API_BASE_URL}/api/supabase/settings/commission-rate`, {
          headers: { 'X-User-ID': user.id }
        })
      ])

      const companyData = await companyRes.json()
      const commissionData = await commissionRes.json()

      if (companyData.success && companyData.data) {
        setSettings({
          name: companyData.data.name || "",
          address: companyData.data.address || "",
          phone: companyData.data.phone || "",
          website: companyData.data.website || "",
          logo: null,
          logoPreview: companyData.data.logo_url || null,
          commissionRate: commissionData.success && commissionData.data?.commission_rate !== undefined
            ? commissionData.data.commission_rate * 100 // Convert from decimal to percentage
            : 3,
        })
      }
    } catch (err) {
      console.error('Failed to fetch settings:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = e.target
    setSettings({ ...settings, [name]: value })
  }

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]

      // Validate file type
      const validTypes = ["image/jpeg", "image/png", "image/svg+xml"]
      if (!validTypes.includes(file.type)) {
        setError("Please upload a valid image file (JPG, PNG, or SVG)")
        return
      }

      // Validate file size (max 2MB)
      if (file.size > 2 * 1024 * 1024) {
        setError("File size should be less than 2MB")
        return
      }

      const reader = new FileReader()
      reader.onload = (event) => {
        setSettings({
          ...settings,
          logo: file,
          logoPreview: event.target?.result as string,
        })
      }
      reader.readAsDataURL(file)
    }
  }

  const handleRemoveLogo = () => {
    setSettings({
      ...settings,
      logo: null,
      logoPreview: null,
    })
  }

  const handleSave = async () => {
    if (!user) return
    setIsSaving(true)
    setError(null)
    setSuccessMessage(null)

    try {
      // Save company settings and commission rate in parallel
      const [companyRes, commissionRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/supabase/settings/company`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user.id
          },
          body: JSON.stringify({
            name: settings.name,
            address: settings.address,
            phone: settings.phone,
            website: settings.website,
            logo_url: settings.logoPreview
          })
        }),
        fetch(`${API_BASE_URL}/api/supabase/settings/commission-rate`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user.id
          },
          body: JSON.stringify({
            commission_rate: settings.commissionRate / 100 // Convert percentage to decimal
          })
        })
      ])

      const companyData = await companyRes.json()
      const commissionData = await commissionRes.json()

      if (companyData.success && commissionData.success) {
        setSuccessMessage('Company settings saved successfully!')
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(companyData.error || commissionData.error || 'Failed to save settings')
      }
    } catch (err) {
      setError('Failed to save settings')
    } finally {
      setIsSaving(false)
    }
  }

  if (isLoading) {
    return (
      <SidebarWrapper role="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </SidebarWrapper>
    )
  }

  return (
    <SidebarWrapper role="admin">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Company Settings</h1>
          <p className="text-muted-foreground">Manage your company information and branding</p>
        </div>
      </div>

      {successMessage && (
        <Alert className="mb-6 bg-green-50 border-green-200">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{successMessage}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-8 md:grid-cols-2 w-full">
        <Card>
          <CardHeader>
            <CardTitle>Company Information</CardTitle>
            <CardDescription>Update your company details and contact information</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Company Name</Label>
                <Input id="name" name="name" value={settings.name} onChange={handleInputChange} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="address">Address</Label>
                <Textarea id="address" name="address" value={settings.address} onChange={handleInputChange} rows={3} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="phone">Phone Number</Label>
                <Input id="phone" name="phone" value={settings.phone} onChange={handleInputChange} />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="website">Website</Label>
                <Input id="website" name="website" value={settings.website} onChange={handleInputChange} />
              </div>
            </form>
          </CardContent>
        </Card>

        <div className="space-y-8">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <DollarSign className="h-5 w-5" />
                Commission Settings
              </CardTitle>
              <CardDescription>Configure the default commission rate for lead value calculations</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid gap-2">
                  <Label htmlFor="commissionRate">Commission Rate (%)</Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="commissionRate"
                      name="commissionRate"
                      type="number"
                      min="0"
                      max="100"
                      step="0.1"
                      value={settings.commissionRate}
                      onChange={(e) => setSettings({ ...settings, commissionRate: parseFloat(e.target.value) || 0 })}
                      className="w-32"
                    />
                    <span className="text-muted-foreground">%</span>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    This percentage is used to calculate commission value from total home prices.
                    For example, a 3% commission on a $500,000 home = $15,000 commission.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Company Branding</CardTitle>
              <CardDescription>Upload your company logo and manage branding assets</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid gap-2">
                  <Label>Company Logo</Label>
                  <div className="flex flex-col items-center gap-4">
                    <div className="relative">
                      {settings.logoPreview ? (
                        <>
                          <img
                            src={settings.logoPreview}
                            alt="Company Logo"
                            className="h-32 w-32 rounded-md object-contain border"
                          />
                          <Button
                            variant="destructive"
                            size="icon"
                            className="absolute -top-2 -right-2 h-6 w-6 rounded-full"
                            onClick={handleRemoveLogo}
                          >
                            <X className="h-3 w-3" />
                            <span className="sr-only">Remove logo</span>
                          </Button>
                        </>
                      ) : (
                        <div className="h-32 w-32 rounded-md border-2 border-dashed border-gray-300 flex items-center justify-center">
                          <span className="text-sm text-muted-foreground">No logo</span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Input
                        id="logo"
                        type="file"
                        accept=".jpg,.jpeg,.png,.svg"
                        onChange={handleLogoChange}
                        className="hidden"
                      />
                      <Button type="button" variant="outline" onClick={() => document.getElementById("logo")?.click()}>
                        <Upload className="mr-2 h-4 w-4" />
                        Upload Logo
                      </Button>
                    </div>
                    <p className="text-xs text-muted-foreground">Accepted formats: JPG, PNG, SVG (max 2MB)</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="mt-8 flex justify-end">
        <Button onClick={handleSave} disabled={isSaving}>
          {isSaving ? (
            <>
              <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : (
            'Save Settings'
          )}
        </Button>
      </div>
    </SidebarWrapper>
  )
}
