"use client"

import { useState, useEffect, useRef } from "react"
import { Check, Plus, RefreshCw, Trash, X, AlertTriangle, Lock, Eye, EyeOff, Merge, ArrowRight, Map as MapIcon, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
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
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Checkbox } from "@/components/ui/checkbox"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import Link from "next/link"
import { useSubscription } from "@/contexts/subscription-context"
import type { User } from "@supabase/supabase-js"
import { createClient } from "@/lib/supabase/client"

interface LeadSource {
  id: string
  source_name: string
  is_active: boolean
  fee_percentage?: number
  assignment_strategy?: string
  metadata?: {
    credentials?: {
      email?: string
      password?: string
    }
    login_method?: 'email' | 'google'
    min_sync_interval_hours?: number
    platform_name?: string
    [key: string]: any
  }
  options?: Record<string, any> | null
  fub_stage_mapping?: Record<string, string | { buyer: string; seller: string }> | null
  created_at?: string
  updated_at?: string
  sync_interval_days?: number | null
  last_sync_at?: string | null
  same_status_note?: string
  next_sync_at?: string | null
  auto_discovered?: boolean
  user_id?: string
}

interface LeadSourceAlias {
  id: string
  alias_name: string
  canonical_source_id: string
  canonical_source_name?: string
  user_id: string
  created_at: string
}

interface MergeResult {
  canonical_source_id: string
  canonical_source_name: string
  aliases_created: string[]
  leads_updated: number
  sources_deactivated: string[]
  errors: { source_name: string; error: string }[]
}

interface ActiveSync {
  syncId: string
  sourceName: string
  sourceId: string
  status: any
  messages: string[]
  eventSource?: EventSource
  pollInterval?: NodeJS.Timeout
}

interface LastSyncResult {
  sourceId: string
  sourceName: string
  completedAt: Date
  status: 'completed' | 'failed' | 'cancelled'
  processed?: number
  total?: number
  newLeads?: number
  updatedLeads?: number
  errors?: number
  // Full result data for viewing detailed results
  fullResults?: any
}

// Lead sources that support Google OAuth login
const GOOGLE_LOGIN_SOURCES = new Set(["Redfin"])

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5001'

const STANDBY_SOURCES = new Set(["Fast Expert"])

const SYNC_INTERVAL_OPTIONS = [
  { value: 'never', label: 'Never (manual updates only)' },
  { value: '1', label: 'Every 1 day' },
  { value: '3', label: 'Every 3 days' },
  { value: '7', label: 'Every 7 days' },
  { value: '14', label: 'Every 14 days' },
  { value: '21', label: 'Every 21 days' },
  { value: '30', label: 'Every 30 days' },
  { value: '45', label: 'Every 45 days' },
  { value: '60', label: 'Every 60 days' },
]

// Stage mapping interfaces and helpers
interface FUBStage {
  id: string
  name: string
}

interface PlatformOption {
  value: string
  label: string
}

interface StageMapping {
  buyer: string
  seller: string
}

const normalizeValue = (value: unknown) =>
  typeof value === "string" ? value.replace(/\s+/g, " ").trim() : ""

const addOptionIfValid = (
  collection: PlatformOption[],
  value: string,
  label: string
) => {
  const normalizedValue = normalizeValue(value)
  if (!normalizedValue) return

  if (!collection.some(option => option.value === normalizedValue)) {
    collection.push({ value: normalizedValue, label: label.trim() || normalizedValue })
  }
}

const buildOptionsFromData = (rawOptions: any): PlatformOption[] => {
  const results: PlatformOption[] = []

  if (!rawOptions) {
    return results
  }

  if (Array.isArray(rawOptions)) {
    rawOptions.forEach(option => {
      if (typeof option === "string") {
        const trimmed = normalizeValue(option)
        if (trimmed) {
          addOptionIfValid(results, trimmed, trimmed)
        }
      } else if (option && typeof option === "object") {
        const value = normalizeValue(option.value ?? "")
        const label = option.label ?? option.name ?? value
        if (value) {
          addOptionIfValid(results, value, label ?? value)
        }
      }
    })
    return results
  }

  if (typeof rawOptions === "object") {
    // Check if this is a buyer/seller structure
    if (rawOptions.buyer || rawOptions.seller) {
      // Handle buyer/seller nested options
      if (rawOptions.buyer && typeof rawOptions.buyer === "object") {
        Object.entries(rawOptions.buyer).forEach(([category, subOptions]) => {
          if (Array.isArray(subOptions)) {
            subOptions.forEach(subValue => {
              if (typeof subValue === "string") {
                const sub = normalizeValue(subValue)
                if (sub) {
                  addOptionIfValid(results, `Buyer - ${category} - ${sub}`, `Buyer - ${category} - ${sub}`)
                }
              }
            })
          }
        })
      }
      if (rawOptions.seller && typeof rawOptions.seller === "object") {
        Object.entries(rawOptions.seller).forEach(([category, subOptions]) => {
          if (Array.isArray(subOptions)) {
            subOptions.forEach(subValue => {
              if (typeof subValue === "string") {
                const sub = normalizeValue(subValue)
                if (sub) {
                  addOptionIfValid(results, `Seller - ${category} - ${sub}`, `Seller - ${category} - ${sub}`)
                }
              }
            })
          }
        })
      }
      return results
    }

    Object.entries(rawOptions).forEach(([key, value]) => {
      const main = normalizeValue(key)
      if (!main) return

      if (Array.isArray(value)) {
        value.forEach(subValue => {
          if (typeof subValue !== "string") return
          const sub = normalizeValue(subValue)
          if (!sub) return
          const combinedValue = `${main}::${sub}`
          addOptionIfValid(results, combinedValue, `${main} • ${sub}`)
        })
      } else if (typeof value === "string") {
        const description = normalizeValue(value)
        addOptionIfValid(results, main, description ? `${main} • ${description}` : main)
      } else if (value && typeof value === "object") {
        const nestedLabel = normalizeValue((value as any).label ?? (value as any).name ?? "")
        const nestedValue = normalizeValue((value as any).value ?? main)
        if (nestedValue) {
          addOptionIfValid(
            results,
            nestedValue,
            nestedLabel ? `${main} • ${nestedLabel}` : nestedValue
          )
        }
        if ((value as any).options) {
          buildOptionsFromData((value as any).options).forEach(option =>
            addOptionIfValid(results, option.value, option.label)
          )
        }
      }
    })
  }

  return results
}

const getSourceOptions = (source: LeadSource | undefined): PlatformOption[] => {
  if (!source) return []
  const rawOptions = source.options ?? source.metadata?.options
  return buildOptionsFromData(rawOptions)
}

// Filter options based on buyer/seller type
const filterOptionsByType = (options: PlatformOption[], type: 'buyer' | 'seller'): PlatformOption[] => {
  const prefix = type === 'buyer' ? 'Buyer - ' : 'Seller - '
  const hasTypedOptions = options.some(opt => opt.label.startsWith('Buyer - ') || opt.label.startsWith('Seller - '))

  if (!hasTypedOptions) {
    // Platform doesn't have buyer/seller specific options, return all
    return options
  }

  // Filter to only show options for the specified type
  return options.filter(opt => opt.label.startsWith(prefix))
}

export default function LeadSourcesPage() {
  const { subscription } = useSubscription()
  const [sources, setSources] = useState<LeadSource[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [isCredentialsDialogOpen, setIsCredentialsDialogOpen] = useState(false)
  const [isSyncDialogOpen, setIsSyncDialogOpen] = useState(false)
  const [isSameStatusNoteDialogOpen, setIsSameStatusNoteDialogOpen] = useState(false)
  const [selectedSource, setSelectedSource] = useState<LeadSource | null>(null)
  const [selectedSyncSource, setSelectedSyncSource] = useState<LeadSource | null>(null)
  const [selectedSyncOption, setSelectedSyncOption] = useState<string>('never')
  const [showPassword, setShowPassword] = useState(false)
  const [sameStatusNote, setSameStatusNote] = useState<string>("")
  const [isSavingSameStatusNote, setIsSavingSameStatusNote] = useState(false)
  
  const [newSource, setNewSource] = useState({
    name: "",
    feePercentage: 0,
  })
  
  const [credentials, setCredentials] = useState({
    email: "",
    password: "",
    login_method: "email" as 'email' | 'google',
  })
  const [isSavingCredentials, setIsSavingCredentials] = useState(false)
  const [isSavingSync, setIsSavingSync] = useState(false)
  const [syncingSourceId, setSyncingSourceId] = useState<string | null>(null)
  const [syncResults, setSyncResults] = useState<any>(null)
  const [isSyncResultsDialogOpen, setIsSyncResultsDialogOpen] = useState(false)
  const [syncResultsSourceId, setSyncResultsSourceId] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<any>(null)
  const [syncMessages, setSyncMessages] = useState<string[]>([])
  const [isSyncProgressDialogOpen, setIsSyncProgressDialogOpen] = useState(false)
  const [currentSyncId, setCurrentSyncId] = useState<string | null>(null)
  const [isImporting, setIsImporting] = useState(false)
  const [importResults, setImportResults] = useState<any>(null)
  const [isImportResultsDialogOpen, setIsImportResultsDialogOpen] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [authLoading, setAuthLoading] = useState(true)
  const [syncSourceName, setSyncSourceName] = useState<string | null>(null)

  // Merge sources state
  const [isMergeDialogOpen, setIsMergeDialogOpen] = useState(false)
  const [selectedSourcesForMerge, setSelectedSourcesForMerge] = useState<Set<string>>(new Set())
  const [canonicalSourceId, setCanonicalSourceId] = useState<string | null>(null)
  const [isMerging, setIsMerging] = useState(false)
  const [mergeResult, setMergeResult] = useState<MergeResult | null>(null)
  const [isMergeResultDialogOpen, setIsMergeResultDialogOpen] = useState(false)
  const [aliases, setAliases] = useState<LeadSourceAlias[]>([])
  const [isViewAliasesDialogOpen, setIsViewAliasesDialogOpen] = useState(false)

  // Stage mapping state
  const [isMappingDialogOpen, setIsMappingDialogOpen] = useState(false)
  const [selectedMappingSource, setSelectedMappingSource] = useState<LeadSource | null>(null)
  const [fubStages, setFubStages] = useState<FUBStage[]>([])
  const [mappings, setMappings] = useState<Record<string, StageMapping>>({})
  const [isSavingMappings, setIsSavingMappings] = useState(false)

  // Track multiple active syncs and last results
  const [activeSyncs, setActiveSyncs] = useState<Map<string, ActiveSync>>(new Map())
  const [lastSyncResults, setLastSyncResults] = useState<Map<string, LastSyncResult>>(new Map())

  // Ref to keep EventSource alive even when dialog is closed
  const eventSourceRef = useRef<EventSource | null>(null)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Load the current Supabase user session
  useEffect(() => {
    const loadUser = async () => {
      try {
        const supabase = createClient()
        const { data, error: authError } = await supabase.auth.getUser()

        if (authError) {
          console.error('Error loading user session:', authError)
          setError('Unable to load user session')
          setUser(null)
        } else {
          setUser(data.user ?? null)
          if (!data.user) {
            setError('User session not found. Please log in again.')
          }
        }
      } catch (userError) {
        console.error('Unexpected error loading user session:', userError)
        setError('Unable to load user session')
        setUser(null)
      } finally {
        setAuthLoading(false)
      }
    }

    loadUser()
  }, [])

  useEffect(() => {
    if (!authLoading && !user) {
      setIsLoading(false)
    }
  }, [authLoading, user])

  // Fetch lead sources, aliases, and check for active syncs once the user session is available
  useEffect(() => {
    if (!authLoading && user) {
      fetchSources()
      fetchAliases()
      checkActiveSyncs()
    }
  }, [authLoading, user])

  // Check for any active syncs and reconnect to them
  const checkActiveSyncs = async () => {
    if (!user) return

    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/active-syncs`, {
        headers: {
          'X-User-ID': user.id
        }
      })

      const data = await response.json()

      if (data.success && data.data && data.data.length > 0) {
        // Found active syncs - reconnect to the first one (most recent)
        const activeSync = data.data[0]
        const syncId = activeSync.sync_id
        const sourceId = activeSync.source_id
        const sourceName = activeSync.source_name

        console.log(`Reconnecting to active sync: ${syncId} for ${sourceName}`)

        // Update state to show sync is in progress
        setCurrentSyncId(syncId)
        setSyncingSourceId(sourceId)
        setSyncSourceName(sourceName)
        setSyncStatus(activeSync)
        setSyncMessages(activeSync.messages?.map((m: any) => m.message) || [])

        // Show notification about reconnecting
        setSuccessMessage(`Reconnected to active sync for ${sourceName}`)
        setTimeout(() => setSuccessMessage(null), 3000)

        // Start polling to track progress
        pollSyncStatus(syncId, sourceId, sourceName)
      }
    } catch (err) {
      console.error('Error checking for active syncs:', err)
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [])

  const fetchSources = async (showLoading: boolean = true) => {
    if (!user) {
      setIsLoading(false)
      setError('User session not found. Please log in again.')
      return
    }

    // Only show loading spinner on initial load, not on refetches
    if (showLoading) {
      setIsLoading(true)
    }
    setError(null)
    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources`, {
        headers: {
          'X-User-ID': user.id
        }
      })
      const data = await response.json()
      
      if (data.success && Array.isArray(data.data)) {
        // Parse JSON fields if they're strings (from database)
        const parsedSources = data.data.map((source: any) => {
          if (source.metadata && typeof source.metadata === 'string') {
            try {
              source.metadata = JSON.parse(source.metadata)
            } catch (e) {
              console.warn('Failed to parse metadata for source:', source.id, e)
              source.metadata = {}
            }
          }
          // Parse options field
          if (source.options && typeof source.options === 'string') {
            try {
              source.options = JSON.parse(source.options)
            } catch (e) {
              console.warn('Failed to parse options for source:', source.id, e)
              source.options = null
            }
          }
          // Parse fub_stage_mapping field
          if (source.fub_stage_mapping && typeof source.fub_stage_mapping === 'string') {
            try {
              source.fub_stage_mapping = JSON.parse(source.fub_stage_mapping)
            } catch (e) {
              console.warn('Failed to parse fub_stage_mapping for source:', source.id, e)
              source.fub_stage_mapping = null
            }
          }
          if (typeof source.sync_interval_days === 'string') {
            const parsedInterval = parseInt(source.sync_interval_days, 10)
            source.sync_interval_days = Number.isNaN(parsedInterval) ? null : parsedInterval
          }

          if (source.sync_interval_days !== null && typeof source.sync_interval_days !== 'number') {
            source.sync_interval_days = null
          }

          return source
        })
        setSources(parsedSources)
      } else {
        throw new Error(data.error || 'Failed to load lead sources')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load lead sources')
      console.error('Error fetching lead sources:', err)
    } finally {
      setIsLoading(false)
    }
  }

  const handleAddSource = async () => {
    if (!newSource.name.trim()) {
      setError("Source name is required")
      return
    }

    try {
      setError(null)
      // For now, we'll just refresh - in future, implement POST endpoint if needed
      // For MVP, lead sources should be added via database/script
      setSuccessMessage("Please add lead sources through the database or contact admin")
      setIsAddDialogOpen(false)
      setNewSource({ name: "", feePercentage: 0 })
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to add lead source')
    }
  }

  const handleToggleStatus = async (source: LeadSource) => {
    if (!user) {
      setError('User session not found. Please log in again.')
      return
    }

    try {
      setError(null)
      const newStatus = !source.is_active
      
      // Update locally optimistically
      setSources(sources.map(s => 
        s.id === source.id ? { ...s, is_active: newStatus } : s
      ))

      // Call API to update status
      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${source.id}/status`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ is_active: newStatus })
      })

      const data = await response.json()
      
      if (!data.success) {
        // Revert on error
        setSources(sources.map(s => 
          s.id === source.id ? { ...s, is_active: source.is_active } : s
        ))
        throw new Error(data.error || 'Failed to update status')
      }

      setSuccessMessage(`Source ${newStatus ? 'activated' : 'deactivated'} successfully`)
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update status')
      // Refresh to get correct state (silent - no loading spinner)
      fetchSources(false)
    }
  }

  const handleConfigureCredentials = (source: LeadSource) => {
    if (isStandbySource(source)) {
      setSuccessMessage(`${source.source_name} automation is not yet available.`)
      setTimeout(() => setSuccessMessage(null), 3000)
      return
    }
    setSelectedSource(source)
    // Load existing credentials if available
    const existingCredentials = source.metadata?.credentials
    const existingLoginMethod = source.metadata?.login_method
    setCredentials({
      email: existingCredentials?.email || "",
      password: existingCredentials?.password || "",
      login_method: existingLoginMethod || (GOOGLE_LOGIN_SOURCES.has(source.source_name) ? "google" : "email"),
    })
    setIsCredentialsDialogOpen(true)
  }

  const handleConfigureSync = (source: LeadSource) => {
    if (isStandbySource(source)) {
      setSuccessMessage(`${source.source_name} automation is not yet available.`)
      setTimeout(() => setSuccessMessage(null), 3000)
      return
    }
    setSelectedSyncSource(source)
    setSelectedSyncOption(source.sync_interval_days ? String(source.sync_interval_days) : 'never')
    setIsSyncDialogOpen(true)
  }

  const handleSyncDialogChange = (open: boolean) => {
    setIsSyncDialogOpen(open)
    if (!open) {
      setSelectedSyncSource(null)
      setSelectedSyncOption('never')
    }
  }

  const handleOpenSameStatusNoteDialog = (source: LeadSource) => {
    setSelectedSource(source)
    setSameStatusNote(source.same_status_note || "Same as previous update. Continuing to communicate and assist the referral as best as possible.")
    setIsSameStatusNoteDialogOpen(true)
  }

  const handleSaveCredentials = async () => {
    if (!credentials.email || !credentials.password) {
      setError("Email and password are required")
      return
    }

    if (!selectedSource || !user) {
      setError('User session not found. Please log in again.')
      return
    }

    setIsSavingCredentials(true)
    setError(null)

    try {
      // Save credentials
      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedSource.id}/credentials`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({
          email: credentials.email,
          password: credentials.password
        })
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to save credentials')
      }

      // Save login method in metadata (for sources that support it)
      if (GOOGLE_LOGIN_SOURCES.has(selectedSource.source_name)) {
        const currentMetadata = selectedSource.metadata || {}
        const updatedMetadata = {
          ...currentMetadata,
          login_method: credentials.login_method
        }

        await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedSource.id}`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'X-User-ID': user.id
          },
          body: JSON.stringify({ metadata: updatedMetadata })
        })
      }

      setSuccessMessage("Credentials saved successfully")
      setIsCredentialsDialogOpen(false)
      setCredentials({ email: "", password: "", login_method: "email" })
      setSelectedSource(null)

      // Refresh sources to get updated data (silent - no loading spinner)
      await fetchSources(false)

      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save credentials')
    } finally {
      setIsSavingCredentials(false)
    }
  }

  const handleSaveSameStatusNote = async () => {
    if (!selectedSource || !user) {
      setError('User session not found. Please log in again.')
      return
    }

    setIsSavingSameStatusNote(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedSource.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ same_status_note: sameStatusNote })
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to save same status note')
      }

      setSuccessMessage('Same status note updated successfully')
      setIsSameStatusNoteDialogOpen(false)
      setSelectedSource(null)
      setSameStatusNote("")
      
      // Refresh sources to get updated data (silent - no loading spinner)
      await fetchSources(false)

      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save same status note')
    } finally {
      setIsSavingSameStatusNote(false)
    }
  }

  const handleSaveSyncSettings = async () => {
    if (!selectedSyncSource) return
    if (!user) {
      setError('User session not found. Please log in again.')
      return
    }

    setIsSavingSync(true)
    setError(null)

    const intervalValue = selectedSyncOption === 'never' ? null : Number(selectedSyncOption)
    
    // Get min_sync_interval_hours from metadata
    const minSyncIntervalHours = selectedSyncSource.metadata?.min_sync_interval_hours || 24

    try {
      // Update sync settings (interval) and metadata (min_sync_interval_hours)
      const syncResponse = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedSyncSource.id}/sync-settings`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ sync_interval_days: intervalValue })
      })

      // Also update metadata with min_sync_interval_hours
      const currentMetadata = selectedSyncSource.metadata || {}
      const updatedMetadata = {
        ...currentMetadata,
        min_sync_interval_hours: minSyncIntervalHours
      }
      
      const metadataResponse = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedSyncSource.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({ metadata: updatedMetadata })
      })
      
      // Wait for both responses
      const syncData = await syncResponse.json()
      const metadataData = await metadataResponse.json()
      
      // Use sync data as primary response
      const data = syncData

      if (!data.success) {
        throw new Error(data.error || 'Failed to save sync settings')
      }

      setSuccessMessage('Sync schedule updated successfully')
      setIsSyncDialogOpen(false)
      setSelectedSyncSource(null)

      // Refresh sources (silent - no loading spinner)
      await fetchSources(false)

      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save sync settings')
    } finally {
      setIsSavingSync(false)
    }
  }

  const handleCancelSync = async () => {
    if (!currentSyncId) return

    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/sync-status/${currentSyncId}/cancel`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user?.id || ''
        }
      })

      const data = await response.json()

      if (!data.success) {
        setError(data.error || 'Failed to cancel sync')
      } else {
        setSyncMessages(prev => [...prev, 'Cancellation requested...'])
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel sync')
    }
  }

  // Cleanup function for sync connections
  const cleanupSyncConnections = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
      pollIntervalRef.current = null
    }
  }

  // Poll sync status as fallback if SSE fails
  const pollSyncStatus = async (syncId: string, sourceId?: string, sourceName?: string) => {
    // Clear any existing poll interval
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current)
    }

    pollIntervalRef.current = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/supabase/sync-status/${syncId}`)
        const data = await response.json()

        if (data.success && data.data) {
          const status = data.data
          setSyncStatus(status)
          setSyncMessages(status.messages?.map((m: any) => m.message) || [])

          if (status.status === 'completed' || status.status === 'failed' || status.status === 'cancelled') {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current)
              pollIntervalRef.current = null
            }
            // Save last sync result if we have source info
            if (sourceId && sourceName) {
              saveLastSyncResult(sourceId, sourceName, status, status.status as 'completed' | 'failed' | 'cancelled')
            }
            setIsSyncProgressDialogOpen(false)
            // Don't auto-open results dialog - results show in Sync Status column
            setCurrentSyncId(null)
            setSyncingSourceId(null)
            setSyncSourceName(null)
            if (sourceName) {
              const successCount = status?.successful || 0
              const failCount = status?.failed || 0
              if (status.status === 'completed') {
                setSuccessMessage(`Sync complete for ${sourceName}: ${successCount} updated, ${failCount} failed. Click status for details.`)
              } else if (status.status === 'cancelled') {
                setSuccessMessage(`Sync cancelled for ${sourceName}`)
              } else {
                setError(`Sync failed for ${sourceName}`)
              }
              setTimeout(() => { setSuccessMessage(null); setError(null) }, 5000)
            }
            // Refresh sources (silent - no loading spinner)
            fetchSources(false)
          }
        }
      } catch (e) {
        console.error('Error polling sync status:', e)
      }
    }, 2000) // Poll every 2 seconds

    // Cleanup after 10 minutes
    setTimeout(() => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
        pollIntervalRef.current = null
      }
    }, 600000)
  }

  // Function to re-open progress dialog and reconnect to stream
  const handleViewSyncProgress = () => {
    if (currentSyncId) {
      setIsSyncProgressDialogOpen(true)
      // If we don't have an active connection, start polling
      if (!eventSourceRef.current && !pollIntervalRef.current) {
        pollSyncStatus(currentSyncId)
      }
    }
  }

  const handleUpdateNow = async (source: LeadSource) => {
    if (!user) {
      setError('User session not found. Please log in again.')
      return
    }

    if (isStandbySource(source)) {
      setSuccessMessage(`${source.source_name} automation is not yet available.`)
      setTimeout(() => setSuccessMessage(null), 3000)
      return
    }

    if (!hasCredentials(source)) {
      setError(`Please configure credentials for ${source.source_name} before syncing.`)
      setTimeout(() => setError(null), 5000)
      return
    }

    // Cleanup any existing connections
    cleanupSyncConnections()

    setSyncingSourceId(source.id)
    setSyncSourceName(source.source_name)
    setError(null)
    setSyncMessages([])
    setSyncStatus(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${source.id}/sync-now`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        }
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to trigger sync')
      }

      // Get sync_id from response
      const syncId = data.sync_id
      if (syncId) {
        setCurrentSyncId(syncId)
        setIsSyncProgressDialogOpen(true)

        // Connect to SSE stream for real-time updates
        const eventSource = new EventSource(
          `${API_BASE_URL}/api/supabase/sync-status/${syncId}/stream`
        )
        eventSourceRef.current = eventSource

        eventSource.onmessage = (event) => {
          try {
            const update = JSON.parse(event.data)

            if (update.type === 'status') {
              setSyncStatus(update.data)
              // Check if status indicates cancellation
              if (update.data?.status === 'cancelled') {
                setSyncMessages(prev => [...prev, 'Sync cancelled by user'])
                saveLastSyncResult(source.id, source.source_name, update.data, 'cancelled')
                cleanupSyncConnections()
                setIsSyncProgressDialogOpen(false)
                setCurrentSyncId(null)
                setSyncingSourceId(null)
                setSyncSourceName(null)
                setSuccessMessage(`Sync cancelled for ${source.source_name}`)
                setTimeout(() => setSuccessMessage(null), 3000)
                // Refresh sources (silent - no loading spinner)
                fetchSources(false)
              }
            } else if (update.type === 'message') {
              setSyncMessages(prev => [...prev, update.data.message])
            } else if (update.type === 'complete') {
              setSyncStatus(update.data)
              saveLastSyncResult(source.id, source.source_name, update.data, 'completed')
              cleanupSyncConnections()
              setIsSyncProgressDialogOpen(false)
              // Don't auto-open results dialog - results show in Sync Status column (clickable for details)
              setCurrentSyncId(null)
              setSyncingSourceId(null)
              setSyncSourceName(null)
              const successCount = update.data?.successful || 0
              const failCount = update.data?.failed || 0
              setSuccessMessage(`Sync complete for ${source.source_name}: ${successCount} updated, ${failCount} failed. Click status for details.`)
              setTimeout(() => setSuccessMessage(null), 5000)
              // Refresh sources (silent - no loading spinner)
              fetchSources(false)
            } else if (update.type === 'error') {
              setError(update.message || 'Sync error occurred')
              saveLastSyncResult(source.id, source.source_name, update.data, 'failed')
              cleanupSyncConnections()
              setIsSyncProgressDialogOpen(false)
              setCurrentSyncId(null)
              setSyncingSourceId(null)
              setSyncSourceName(null)
            }
          } catch (e) {
            console.error('Error parsing SSE message:', e)
          }
        }

        eventSource.onerror = (error) => {
          console.error('SSE connection error:', error)
          // Fallback to polling if SSE fails
          if (eventSourceRef.current) {
            eventSourceRef.current.close()
            eventSourceRef.current = null
          }
          pollSyncStatus(syncId, source.id, source.source_name)
        }
      } else {
        // Fallback if no sync_id (old response format)
        saveLastSyncResult(source.id, source.source_name, data.data, 'completed')
        setSyncingSourceId(null)
        setSyncSourceName(null)
        setSuccessMessage(`Sync complete for ${source.source_name}. Click status for details.`)
        setTimeout(() => setSuccessMessage(null), 5000)
        // Refresh sources (silent - no loading spinner)
        await fetchSources(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger sync')
      setTimeout(() => setError(null), 5000)
      cleanupSyncConnections()
      setIsSyncProgressDialogOpen(false)
      setCurrentSyncId(null)
      setSyncingSourceId(null)
      setSyncSourceName(null)
    }
  }

  const isStandbySource = (source?: LeadSource | null) => {
    if (!source) return false
    return STANDBY_SOURCES.has(source.source_name?.trim())
  }

  const hasCredentials = (source: LeadSource | null) => {
    if (!source || isStandbySource(source)) return false
    return !!(source.metadata?.credentials?.email && source.metadata?.credentials?.password)
  }

  const getSyncScheduleLabel = (source: LeadSource) => {
    if (isStandbySource(source)) {
      return 'Standby (service pending)'
    }
    if (!source.sync_interval_days) {
      return 'Manual updates'
    }

    const option = SYNC_INTERVAL_OPTIONS.find(opt => opt.value === String(source.sync_interval_days))
    return option ? option.label : `Every ${source.sync_interval_days} days`
  }

  const formatDateTime = (value?: string | null) => {
    if (!value) return null
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return null
    }
    return date.toLocaleString()
  }

  // Save last sync result for a source
  const saveLastSyncResult = (sourceId: string, sourceName: string, resultData: any, status: 'completed' | 'failed' | 'cancelled') => {
    setLastSyncResults(prev => {
      const newMap = new Map(prev)
      // Backend returns: successful, failed, skipped, total_leads, processed, filter_summary, details
      const successful = resultData?.successful || 0
      const failed = resultData?.failed || 0
      const skipped = resultData?.skipped || resultData?.filter_summary?.skipped_recently_synced || 0
      const totalLeads = resultData?.total_leads || resultData?.filter_summary?.total_leads || 0

      newMap.set(sourceId, {
        sourceId,
        sourceName,
        completedAt: new Date(),
        status,
        processed: resultData?.processed || successful + failed,
        total: totalLeads,
        newLeads: successful, // "successful" in sync context means updated/synced
        updatedLeads: skipped, // Show skipped count as reference
        errors: failed,
        fullResults: resultData, // Store full results for detailed view
      })
      return newMap
    })
  }

  // View last sync results for a source
  const handleViewLastSyncResults = (sourceId: string) => {
    const lastResult = lastSyncResults.get(sourceId)
    if (lastResult?.fullResults) {
      setSyncResults(lastResult.fullResults)
      setSyncResultsSourceId(sourceId)
      setIsSyncResultsDialogOpen(true)
    }
  }

  // Format relative time for last sync
  const formatRelativeTime = (date: Date) => {
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  const handleImportLeads = async () => {
    setIsImporting(true)
    setError(null)

    try {
      if (!user) {
        throw new Error('User session not found. Please log in again.')
      }

      const response = await fetch(`${API_BASE_URL}/api/supabase/import-fub-leads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        }
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to import leads')
      }

      setImportResults(data.data)
      setIsImportResultsDialogOpen(true)
      setSuccessMessage(`Successfully imported ${data.data.inserted} new leads and updated ${data.data.updated} existing leads`)
      setTimeout(() => setSuccessMessage(null), 5000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to import leads')
      setTimeout(() => setError(null), 5000)
    } finally {
      setIsImporting(false)
    }
  }

  // Merge sources functions
  const handleOpenMergeDialog = async () => {
    setSelectedSourcesForMerge(new Set())
    setCanonicalSourceId(null)
    // Fetch aliases so we know which sources are already merged
    await fetchAliases()
    setIsMergeDialogOpen(true)
  }

  // Helper to check if a source has been merged into another
  const getMergedIntoSource = (sourceName: string): string | null => {
    const alias = aliases.find(a => a.alias_name === sourceName)
    return alias?.canonical_source_name || null
  }

  const handleToggleSourceForMerge = (sourceId: string) => {
    const newSelected = new Set(selectedSourcesForMerge)
    if (newSelected.has(sourceId)) {
      newSelected.delete(sourceId)
      // If we removed the canonical source, reset it
      if (canonicalSourceId === sourceId) {
        setCanonicalSourceId(null)
      }
    } else {
      newSelected.add(sourceId)
    }
    setSelectedSourcesForMerge(newSelected)
  }

  const handleMergeSources = async () => {
    if (!user) {
      setError('User session not found. Please log in again.')
      return
    }

    if (selectedSourcesForMerge.size < 2) {
      setError('Please select at least 2 sources to merge')
      return
    }

    if (!canonicalSourceId) {
      setError('Please select a primary (canonical) source')
      return
    }

    setIsMerging(true)
    setError(null)

    try {
      const response = await fetch(`${API_BASE_URL}/api/lead-sources/merge`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.id
        },
        body: JSON.stringify({
          source_ids: Array.from(selectedSourcesForMerge),
          canonical_source_id: canonicalSourceId
        })
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to merge sources')
      }

      setMergeResult(data.data)
      setIsMergeResultDialogOpen(true)
      setSuccessMessage(`Successfully merged ${data.data.sources_deactivated.length} sources into ${data.data.canonical_source_name}`)
      setTimeout(() => setSuccessMessage(null), 5000)

      // Refresh sources list, aliases, and reset selection for next merge (silent - no loading spinner)
      await fetchSources(false)
      await fetchAliases()
      setSelectedSourcesForMerge(new Set())
      setCanonicalSourceId(null)
      // Keep merge dialog open so user can do another merge
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to merge sources')
    } finally {
      setIsMerging(false)
    }
  }

  const fetchAliases = async () => {
    if (!user) return

    try {
      const response = await fetch(`${API_BASE_URL}/api/lead-sources/mappings`, {
        headers: {
          'X-User-ID': user.id
        }
      })

      const data = await response.json()

      if (data.success && Array.isArray(data.data)) {
        setAliases(data.data)
      }
    } catch (err) {
      console.error('Error fetching aliases:', err)
    }
  }

  // Fetch FUB stages for mapping dialog
  const fetchFubStages = async () => {
    if (!user?.id) {
      console.error('Cannot fetch FUB stages: user not loaded')
      return
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/supabase/fub-stages`, {
        headers: {
          'X-User-ID': user.id
        }
      })
      const data = await response.json()

      if (data.success && Array.isArray(data.data)) {
        console.log(`Fetched ${data.data.length} FUB stages:`, data.data.map((s: FUBStage) => s.name))
        setFubStages(data.data)
      } else {
        console.error('Failed to fetch FUB stages:', data.error || 'Unknown error')
      }
    } catch (err) {
      console.error('Error fetching FUB stages:', err)
    }
  }

  // Load mappings when opening the mapping dialog
  const loadMappingsForSource = (source: LeadSource) => {
    const formattedMappings: Record<string, StageMapping> = {}

    if (source && source.fub_stage_mapping) {
      // Convert existing mappings to the new format (buyer/seller)
      fubStages.forEach(stage => {
        const existing = source.fub_stage_mapping?.[stage.name]
        if (existing) {
          if (typeof existing === 'string') {
            // Old format - use same value for both buyer and seller
            formattedMappings[stage.name] = { buyer: existing, seller: existing }
          } else if (typeof existing === 'object' && existing.buyer !== undefined) {
            // New format
            formattedMappings[stage.name] = { buyer: existing.buyer || '', seller: existing.seller || '' }
          } else {
            formattedMappings[stage.name] = { buyer: '', seller: '' }
          }
        } else {
          formattedMappings[stage.name] = { buyer: '', seller: '' }
        }
      })
    } else {
      // Initialize empty mappings for all FUB stages
      fubStages.forEach(stage => {
        formattedMappings[stage.name] = { buyer: '', seller: '' }
      })
    }
    setMappings(formattedMappings)
  }

  // Open mapping dialog for a source
  const handleOpenMappingDialog = async (source: LeadSource) => {
    setSelectedMappingSource(source)

    // Fetch FUB stages if not already loaded
    if (fubStages.length === 0) {
      await fetchFubStages()
    }

    setIsMappingDialogOpen(true)
  }

  // Effect to load mappings when FUB stages are loaded and dialog is open
  useEffect(() => {
    if (selectedMappingSource && fubStages.length > 0 && isMappingDialogOpen) {
      loadMappingsForSource(selectedMappingSource)
    }
  }, [selectedMappingSource, fubStages, isMappingDialogOpen])

  // Handle mapping change
  const handleMappingChange = (fubStageName: string, type: 'buyer' | 'seller', platformStage: string) => {
    const value = normalizeValue(platformStage)
    setMappings(prev => ({
      ...prev,
      [fubStageName]: {
        ...prev[fubStageName],
        [type]: value
      }
    }))
  }

  // Save mappings
  const handleSaveMappings = async () => {
    if (!selectedMappingSource || !user) {
      setError("Please select a source and ensure you're logged in")
      return
    }

    setIsSavingMappings(true)
    setError(null)

    try {
      // Filter out empty mappings (where both buyer and seller are empty)
      const cleanedMappings: Record<string, { buyer: string; seller: string }> = {}
      Object.entries(mappings).forEach(([stage, mapping]) => {
        if (mapping.buyer.trim() || mapping.seller.trim()) {
          cleanedMappings[stage] = {
            buyer: mapping.buyer.trim(),
            seller: mapping.seller.trim()
          }
        }
      })

      const response = await fetch(`${API_BASE_URL}/api/supabase/lead-sources/${selectedMappingSource.id}/mappings`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          'X-User-ID': user.id
        },
        body: JSON.stringify({
          fub_stage_mapping: cleanedMappings
        }),
      })

      const data = await response.json()

      if (data.success) {
        setSuccessMessage("Stage mappings saved successfully!")
        // Update the source in our local state
        setSources(prev => prev.map(s =>
          s.id === selectedMappingSource.id
            ? { ...s, fub_stage_mapping: cleanedMappings }
            : s
        ))
        setIsMappingDialogOpen(false)
        setTimeout(() => setSuccessMessage(null), 3000)
      } else {
        setError(data.error || "Failed to save mappings")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save mappings")
      console.error("Error saving mappings:", err)
    } finally {
      setIsSavingMappings(false)
    }
  }

  const handleViewAliases = async () => {
    await fetchAliases()
    setIsViewAliasesDialogOpen(true)
  }

  const handleDeleteAlias = async (aliasId: string) => {
    if (!user) return

    try {
      const response = await fetch(`${API_BASE_URL}/api/lead-sources/mappings/${aliasId}`, {
        method: 'DELETE',
        headers: {
          'X-User-ID': user.id
        }
      })

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Failed to delete alias')
      }

      setSuccessMessage('Alias deleted successfully')
      setTimeout(() => setSuccessMessage(null), 3000)

      // Refresh aliases
      await fetchAliases()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete alias')
    }
  }

  const getSourceNameById = (sourceId: string) => {
    const source = sources.find(s => s.id === sourceId)
    return source?.source_name || 'Unknown'
  }

  // Sort sources: active first, then inactive, merged sources at bottom
  const sortedSources = [...sources].sort((a, b) => {
    const aMerged = !!aliases.find(al => al.alias_name === a.source_name)
    const bMerged = !!aliases.find(al => al.alias_name === b.source_name)

    // Merged sources go to bottom
    if (aMerged && !bMerged) return 1
    if (!aMerged && bMerged) return -1

    // Active sources go to top
    if (a.is_active && !b.is_active) return -1
    if (!a.is_active && b.is_active) return 1

    // Then sort by name
    return a.source_name.localeCompare(b.source_name)
  })

  return (
    <SidebarWrapper role="admin">
      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {successMessage && (
        <Alert className="mb-6 border-green-500 bg-green-50">
          <Check className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">{successMessage}</AlertDescription>
        </Alert>
      )}

      {/* Persistent Sync Banner - shows when sync is running */}
      {currentSyncId && syncSourceName && (
        <Alert className="mb-6 border-blue-500 bg-blue-50">
          <div className="flex items-center justify-between w-full">
            <div className="flex items-center gap-3">
              <RefreshCw className="h-5 w-5 text-blue-600 animate-spin" />
              <div className="flex flex-col">
                <AlertDescription className="text-blue-800 font-medium">
                  Syncing {syncSourceName}
                  {syncStatus?.processed !== undefined && syncStatus?.total_leads ? (
                    <span className="ml-2">
                      — {syncStatus.processed}/{syncStatus.total_leads} leads ({((syncStatus.processed / syncStatus.total_leads) * 100).toFixed(0)}%)
                    </span>
                  ) : (
                    <span className="ml-2">— Starting...</span>
                  )}
                </AlertDescription>
                {syncStatus?.current_lead && (
                  <span className="text-sm text-blue-600">Processing: {syncStatus.current_lead}</span>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3">
              {syncStatus?.total_leads > 0 && (
                <div className="w-40 bg-blue-200 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{
                      width: `${((syncStatus.processed || 0) / syncStatus.total_leads) * 100}%`
                    }}
                  ></div>
                </div>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={handleViewSyncProgress}
                className="border-blue-500 text-blue-700 hover:bg-blue-100"
              >
                Details
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleCancelSync}
              >
                <X className="h-3 w-3 mr-1" />
                Stop
              </Button>
            </div>
          </div>
        </Alert>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Lead Sources</h1>
          <p className="text-muted-foreground">Manage your lead sources and their credentials</p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="default"
            onClick={handleImportLeads}
            disabled={isImporting || isLoading}
          >
            {isImporting ? (
              <>
                <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Importing...
              </>
            ) : (
              <>
                <Plus className="mr-2 h-4 w-4" />
                Import Leads from FUB
              </>
            )}
          </Button>
          <Button
            variant="outline"
            onClick={handleOpenMergeDialog}
            disabled={isLoading || sources.length < 2}
          >
            <Merge className="mr-2 h-4 w-4" />
            Merge Duplicates
          </Button>
          <Button
            variant="ghost"
            onClick={handleViewAliases}
            disabled={isLoading}
          >
            View Mappings
          </Button>
          <Button variant="outline" onClick={fetchSources} disabled={isLoading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle>Lead Sources</CardTitle>
          <CardDescription>Configure your lead sources and their credentials</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-muted-foreground">Loading lead sources...</span>
            </div>
          ) : sources.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No lead sources found. Contact admin to add lead sources.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[180px]">Source</TableHead>
                    <TableHead className="w-[100px]">Status</TableHead>
                    <TableHead className="w-[120px]">Credentials</TableHead>
                    <TableHead className="w-[140px]">Schedule</TableHead>
                    <TableHead className="w-[200px]">Sync Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedSources.map((source) => {
                    const standby = isStandbySource(source)
                    const isSyncing = syncingSourceId === source.id
                    const isMergedSource = !!getMergedIntoSource(source.source_name)
                    return (
                      <TableRow key={source.id} className={`${isSyncing ? "bg-blue-50/50" : ""} ${isMergedSource ? "opacity-60" : ""}`}>
                        <TableCell className="font-medium">
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-2">
                              {source.source_name}
                              {standby && (
                                <Badge variant="secondary" className="text-[9px] px-1">
                                  Standby
                                </Badge>
                              )}
                              {getMergedIntoSource(source.source_name) && (
                                <span className="text-xs text-green-600 flex items-center gap-1">
                                  <ArrowRight className="h-3 w-3" />
                                  {getMergedIntoSource(source.source_name)}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {source.fee_percentage > 0 && (
                                <span className="text-xs text-muted-foreground">
                                  {source.fee_percentage}% fee
                                </span>
                              )}
                              {/* Stage mapping indicator */}
                              {source.options && Object.keys(source.options).length > 0 && (
                                !source.fub_stage_mapping || Object.keys(source.fub_stage_mapping).length === 0 ? (
                                  <Link href="/admin/stage-mapping" className="flex items-center gap-1 text-amber-600 hover:text-amber-700">
                                    <AlertTriangle className="h-3 w-3" />
                                    <span className="text-[10px]">Needs Mapping</span>
                                  </Link>
                                ) : (
                                  <span className="text-[10px] text-green-600 flex items-center gap-1">
                                    <Check className="h-3 w-3" />
                                    Mapped
                                  </span>
                                )
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={source.is_active}
                              onCheckedChange={() => handleToggleStatus(source)}
                              disabled={standby || !!getMergedIntoSource(source.source_name)}
                            />
                            <span className={`text-xs ${source.is_active ? 'text-green-600' : 'text-muted-foreground'}`}>
                              {standby ? "Standby" : getMergedIntoSource(source.source_name) ? "Merged" : source.is_active ? "Active" : "Off"}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {standby ? (
                            <span className="text-xs text-yellow-600">N/A</span>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleConfigureCredentials(source)}
                              className="h-7 px-2 text-xs"
                            >
                              {hasCredentials(source) ? (
                                <>
                                  <Check className="h-3 w-3 text-green-600 mr-1" />
                                  Set
                                </>
                              ) : (
                                <>
                                  <AlertTriangle className="h-3 w-3 text-yellow-600 mr-1" />
                                  Required
                                </>
                              )}
                            </Button>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-0.5">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleConfigureSync(source)}
                              className="h-6 px-2 text-xs justify-start"
                              disabled={standby}
                            >
                              {getSyncScheduleLabel(source)}
                            </Button>
                            {!standby && source.last_sync_at && (
                              <span className="text-[10px] text-muted-foreground pl-2">
                                Last: {formatDateTime(source.last_sync_at)}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {/* Sync Status Column - shows progress when syncing, or last result */}
                          {isSyncing && syncStatus ? (
                            <div className="flex flex-col gap-1">
                              <div className="flex items-center gap-2">
                                <div className="flex-1">
                                  <div className="flex justify-between text-xs mb-1">
                                    <span className="text-blue-600 font-medium">
                                      {syncStatus.processed || 0}/{syncStatus.total_leads || 0}
                                    </span>
                                    <span className="text-muted-foreground">
                                      {syncStatus.total_leads > 0
                                        ? `${((syncStatus.processed || 0) / syncStatus.total_leads * 100).toFixed(0)}%`
                                        : '0%'}
                                    </span>
                                  </div>
                                  <div className="w-full bg-gray-200 rounded-full h-1.5">
                                    <div
                                      className="bg-blue-600 h-1.5 rounded-full transition-all duration-300"
                                      style={{
                                        width: `${syncStatus.total_leads > 0 ? ((syncStatus.processed || 0) / syncStatus.total_leads) * 100 : 0}%`
                                      }}
                                    ></div>
                                  </div>
                                </div>
                              </div>
                              {syncStatus.current_lead && (
                                <span className="text-[10px] text-blue-600 truncate" title={syncStatus.current_lead}>
                                  {syncStatus.current_lead}
                                </span>
                              )}
                            </div>
                          ) : lastSyncResults.get(source.id) ? (
                            <button
                              onClick={() => handleViewLastSyncResults(source.id)}
                              className="flex flex-col gap-0.5 text-left hover:bg-muted/50 rounded px-1.5 py-0.5 -mx-1.5 -my-0.5 transition-colors cursor-pointer"
                              title="Click to view detailed results"
                            >
                              <div className="flex items-center gap-1.5">
                                {lastSyncResults.get(source.id)?.status === 'completed' ? (
                                  <Check className="h-3 w-3 text-green-600" />
                                ) : lastSyncResults.get(source.id)?.status === 'failed' ? (
                                  <X className="h-3 w-3 text-red-500" />
                                ) : (
                                  <X className="h-3 w-3 text-yellow-500" />
                                )}
                                <span className={`text-xs ${
                                  lastSyncResults.get(source.id)?.status === 'completed' ? 'text-green-600' :
                                  lastSyncResults.get(source.id)?.status === 'failed' ? 'text-red-500' : 'text-yellow-600'
                                }`}>
                                  {lastSyncResults.get(source.id)?.status === 'completed' ? 'Done' :
                                   lastSyncResults.get(source.id)?.status === 'failed' ? 'Failed' : 'Cancelled'}
                                </span>
                                <span className="text-[10px] text-muted-foreground">
                                  {formatRelativeTime(lastSyncResults.get(source.id)!.completedAt)}
                                </span>
                              </div>
                              <div className="text-[10px] text-muted-foreground">
                                {lastSyncResults.get(source.id)?.newLeads || 0} synced{lastSyncResults.get(source.id)?.errors ? `, ${lastSyncResults.get(source.id)?.errors} failed` : ''}
                              </div>
                            </button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenSameStatusNoteDialog(source)}
                              className="h-8 px-2 text-xs"
                              disabled={standby}
                            >
                              Note
                            </Button>
                            {source.options && Object.keys(source.options).length > 0 && (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleOpenMappingDialog(source)}
                                className="h-8 px-2 text-xs"
                                disabled={standby}
                              >
                                <MapIcon className="h-3 w-3 mr-1" />
                                Mapping
                              </Button>
                            )}
                            {isSyncing ? (
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={handleCancelSync}
                                className="h-8 px-3"
                              >
                                <X className="h-3 w-3 mr-1" />
                                Stop
                              </Button>
                            ) : (
                              <Button
                                variant="default"
                                size="sm"
                                onClick={() => handleUpdateNow(source)}
                                disabled={standby || !hasCredentials(source)}
                                className="h-8 px-3"
                              >
                                <RefreshCw className="h-3 w-3 mr-1" />
                                Sync
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Credentials Configuration Dialog */}
      <Dialog open={isCredentialsDialogOpen} onOpenChange={setIsCredentialsDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure Credentials</DialogTitle>
            <DialogDescription>
              Enter login credentials for {selectedSource?.source_name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            {/* Login Method Selection - only for sources that support Google OAuth */}
            {selectedSource && GOOGLE_LOGIN_SOURCES.has(selectedSource.source_name) && (
              <div className="grid gap-2">
                <Label>Login Method</Label>
                <RadioGroup
                  value={credentials.login_method}
                  onValueChange={(value: 'email' | 'google') =>
                    setCredentials({ ...credentials, login_method: value })
                  }
                  className="flex gap-4"
                >
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="google" id="login-google" />
                    <Label htmlFor="login-google" className="font-normal cursor-pointer">
                      Sign in with Google (Recommended)
                    </Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <RadioGroupItem value="email" id="login-email" />
                    <Label htmlFor="login-email" className="font-normal cursor-pointer">
                      Email & Password
                    </Label>
                  </div>
                </RadioGroup>
                {credentials.login_method === 'google' && (
                  <Alert className="mt-2">
                    <AlertDescription className="text-sm">
                      Uses Google OAuth to log in. Enter your Google account email and password.
                      If you have 2FA disabled on your Google account, this works automatically.
                    </AlertDescription>
                  </Alert>
                )}
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="email">
                {credentials.login_method === 'google' ? 'Google Account Email' : 'Email'}
              </Label>
              <Input
                id="email"
                type="email"
                value={credentials.email}
                onChange={(e) => setCredentials({ ...credentials, email: e.target.value })}
                placeholder="email@example.com"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="password">
                {credentials.login_method === 'google' ? 'Google Account Password' : 'Password'}
              </Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={credentials.password}
                  onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                  placeholder="Enter password"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <Eye className="h-4 w-4 text-muted-foreground" />
                  )}
                </Button>
              </div>
            </div>
            {selectedSource && hasCredentials(selectedSource) && (
              <Alert>
                <AlertDescription>
                  Credentials are already configured. Enter new credentials to update them.
                </AlertDescription>
              </Alert>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCredentialsDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveCredentials} disabled={isSavingCredentials}>
              {isSavingCredentials ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Credentials"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Schedule Dialog */}
      <Dialog open={isSyncDialogOpen} onOpenChange={handleSyncDialogChange}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure Sync Schedule</DialogTitle>
            <DialogDescription>
              Choose how often {selectedSyncSource?.source_name} should be updated automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <RadioGroup value={selectedSyncOption} onValueChange={setSelectedSyncOption}>
              {SYNC_INTERVAL_OPTIONS.map(option => (
                <div key={option.value} className="flex items-center space-x-2">
                  <RadioGroupItem value={option.value} id={`sync-${option.value}`} />
                  <Label htmlFor={`sync-${option.value}`}>{option.label}</Label>
                </div>
              ))}
            </RadioGroup>
            {selectedSyncSource && (
              <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground space-y-2">
                <p>
                  Last sync: {formatDateTime(selectedSyncSource.last_sync_at) ?? 'No history'}
                </p>
                <p>
                  Next scheduled: {formatDateTime(selectedSyncSource.next_sync_at) ?? 'Not scheduled'}
                </p>
                <div className="pt-2 border-t">
                  <Label htmlFor="minSyncInterval" className="text-xs font-medium">
                    Minimum Hours Between Syncs (prevents duplicate updates)
                  </Label>
                  <Input
                    id="minSyncInterval"
                    type="number"
                    min="1"
                    max="168"
                    value={selectedSyncSource.metadata?.min_sync_interval_hours || 24}
                    onChange={(e) => {
                      const hours = parseInt(e.target.value) || 24
                      setSelectedSyncSource({
                        ...selectedSyncSource,
                        metadata: {
                          ...selectedSyncSource.metadata,
                          min_sync_interval_hours: hours
                        }
                      })
                    }}
                    className="mt-1"
                    placeholder="24"
                  />
                  <p className="text-xs text-muted-foreground mt-1">
                    Leads synced within this time (hours) will be skipped on next sync. Default: 24 hours.
                  </p>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsSyncDialogOpen(false)} disabled={isSavingSync}>
              Cancel
            </Button>
            <Button onClick={handleSaveSyncSettings} disabled={isSavingSync}>
              {isSavingSync ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Sync Settings'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Same Status Note Dialog */}
      <Dialog open={isSameStatusNoteDialogOpen} onOpenChange={setIsSameStatusNoteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Configure Same Status Note</DialogTitle>
            <DialogDescription>
              Set the default note text to use when the lead status hasn't changed for {selectedSource?.source_name}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="sameStatusNote">Default Note</Label>
              <Input
                id="sameStatusNote"
                type="text"
                value={sameStatusNote}
                onChange={(e) => setSameStatusNote(e.target.value)}
                placeholder="Same as previous update. Continuing to communicate and assist the referral as best as possible."
              />
            </div>
            <Alert>
              <AlertDescription>
                This note will be used when updating a lead whose status hasn't changed, making the updates appear more natural and human-like.
              </AlertDescription>
            </Alert>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsSameStatusNoteDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveSameStatusNote} disabled={isSavingSameStatusNote}>
              {isSavingSameStatusNote ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Note"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Progress Dialog - Real-time updates */}
      <Dialog open={isSyncProgressDialogOpen} onOpenChange={(open) => {
        // Only allow closing via our button, not by clicking outside
        if (!open && currentSyncId) {
          // Just hide the dialog, don't clear state - sync continues
          setIsSyncProgressDialogOpen(false)
        } else {
          setIsSyncProgressDialogOpen(open)
        }
      }}>
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {syncSourceName ? `${syncSourceName} Sync in Progress` : 'Sync in Progress'}
            </DialogTitle>
            <DialogDescription>
              Real-time updates from the sync process. You can hide this dialog and the sync will continue in the background.
            </DialogDescription>
          </DialogHeader>
          {syncStatus && (
            <div className="grid gap-4 py-4">
              {/* Progress Stats */}
              <div className="grid grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Total Leads</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{syncStatus.total_leads || 0}</div>
                    {syncStatus.filter_summary && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {syncStatus.filter_summary.skipped_recently_synced || 0} skipped
                      </div>
                    )}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-green-600">Successful</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-600">{syncStatus.successful || 0}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-red-600">Failed</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-red-600">{syncStatus.failed || 0}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-blue-600">Processed</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-blue-600">{syncStatus.processed || 0}</div>
                    {syncStatus.total_leads > 0 && (
                      <div className="text-xs text-muted-foreground mt-1">
                        {((syncStatus.processed / syncStatus.total_leads) * 100).toFixed(1)}%
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Progress Bar */}
              {syncStatus.total_leads > 0 && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-muted-foreground">
                    <span>Progress</span>
                    <span>{syncStatus.processed || 0} / {syncStatus.total_leads}</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                      style={{
                        width: `${((syncStatus.processed || 0) / syncStatus.total_leads) * 100}%`
                      }}
                    ></div>
                  </div>
                </div>
              )}

              {/* Current Lead */}
              {syncStatus.current_lead && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Currently Processing</AlertTitle>
                  <AlertDescription>{syncStatus.current_lead}</AlertDescription>
                </Alert>
              )}

              {/* Messages Log */}
              <div className="space-y-2">
                <h4 className="text-sm font-medium">Activity Log</h4>
                <div className="rounded-md border bg-muted/30 p-3 max-h-64 overflow-y-auto">
                  {syncMessages.length > 0 ? (
                    <div className="space-y-1 text-sm font-mono">
                      {syncMessages.map((msg, idx) => (
                        <div key={idx} className="text-muted-foreground">
                          {msg}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-sm text-muted-foreground">Waiting for updates...</div>
                  )}
                </div>
              </div>
            </div>
          )}
          <DialogFooter className="flex justify-between">
            <Button 
              variant="destructive" 
              onClick={handleCancelSync}
              disabled={!syncStatus || (syncStatus.status !== 'running' && syncStatus.status !== 'in_progress')}
            >
              <X className="mr-2 h-4 w-4" />
              Stop Sync
            </Button>
            <Button variant="outline" onClick={() => {
              // Just hide dialog - sync continues in background
              setIsSyncProgressDialogOpen(false)
            }}>
              Hide (Sync continues in background)
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sync Results Dialog */}
      <Dialog open={isSyncResultsDialogOpen} onOpenChange={(open) => {
        setIsSyncResultsDialogOpen(open)
        if (!open) {
          setSyncingSourceId(null)
          setSyncResultsSourceId(null)
        }
      }}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Sync Results</DialogTitle>
            <DialogDescription>
              Results of the immediate sync operation
            </DialogDescription>
          </DialogHeader>
          {syncResults && (
            <div className="grid gap-4 py-4">
              {/* Error banner when all leads failed or there's a sync error */}
              {(syncResults.failed === syncResults.total_leads && syncResults.total_leads > 0) && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Sync Failed</AlertTitle>
                  <AlertDescription>
                    {/* Check for common error patterns */}
                    {syncResults.details?.[0]?.error?.includes('login') || syncResults.details?.[0]?.error?.includes('Login') ? (
                      <p>Failed to login to the platform. Please check your credentials in the Credentials settings.</p>
                    ) : syncResults.error ? (
                      <p>{syncResults.error}</p>
                    ) : syncResults.details?.[0]?.error ? (
                      <p>{syncResults.details[0].error}</p>
                    ) : (
                      <p>All leads failed to sync. Check the details below for more information.</p>
                    )}
                  </AlertDescription>
                </Alert>
              )}

              {/* Sync-level error (not per-lead) */}
              {syncResults.error && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Sync Error</AlertTitle>
                  <AlertDescription>{syncResults.error}</AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Leads</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{syncResults.total_leads}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-green-600">Updated</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-600">{syncResults.successful}</div>
                    <div className="text-xs text-muted-foreground">
                      {syncResults.total_leads > 0 ? `${((syncResults.successful / syncResults.total_leads) * 100).toFixed(1)}%` : '0%'}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-amber-600">Skipped</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-amber-600">{syncResults.skipped || 0}</div>
                    <div className="text-xs text-muted-foreground">
                      Already up-to-date
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-red-600">Failed</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-red-600">{syncResults.failed}</div>
                    <div className="text-xs text-muted-foreground">
                      {syncResults.total_leads > 0 ? `${((syncResults.failed / syncResults.total_leads) * 100).toFixed(1)}%` : '0%'}
                    </div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-blue-600">Processing Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-blue-600">
                      {syncResults.details && syncResults.details.length > 0
                        ? `${syncResults.details.reduce((acc: number, detail: any) => acc + (detail.processing_time || 0), 0).toFixed(1)}s`
                        : 'N/A'
                      }
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {syncResults.details && syncResults.details.length > 0 && syncResults.successful > 0
                        ? `${(syncResults.details.reduce((acc: number, detail: any) => acc + (detail.processing_time || 0), 0) / syncResults.successful).toFixed(1)}s avg`
                        : ''
                      }
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* Progress Bar */}
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-muted-foreground">
                  <span>Effective Success Rate</span>
                  <span>{syncResults.successful + (syncResults.skipped || 0)} / {syncResults.total_leads} leads current</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-600 h-2 rounded-full transition-all duration-300"
                    style={{
                      width: `${syncResults.total_leads > 0 ? ((syncResults.successful + (syncResults.skipped || 0)) / syncResults.total_leads) * 100 : 0}%`
                    }}
                  ></div>
                </div>
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span className="text-green-600">✓ {syncResults.successful} updated</span>
                  <span className="text-amber-600">⏭ {syncResults.skipped || 0} skipped</span>
                  <span className="text-red-600">✗ {syncResults.failed} failed</span>
                </div>
              </div>

              {/* Warning for missing stage mappings */}
              {syncResults.filter_summary?.skipped_no_mapping > 0 && (
                <Alert variant="destructive" className="border-amber-500 bg-amber-50">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  <AlertTitle className="text-amber-800">Stage Mapping Required</AlertTitle>
                  <AlertDescription className="text-amber-700">
                    <p className="mb-2">
                      <strong>{syncResults.filter_summary.skipped_no_mapping}</strong> lead{syncResults.filter_summary.skipped_no_mapping !== 1 ? 's were' : ' was'} skipped because no stage mapping exists for their FUB status.
                    </p>
                    {syncResults.skipped_no_mapping && syncResults.skipped_no_mapping.length > 0 && (
                      <div className="mb-3">
                        <p className="text-sm font-medium mb-1">Missing FUB stage mappings:</p>
                        <ul className="text-sm list-disc list-inside space-y-0.5">
                          {[...new Set(syncResults.skipped_no_mapping.map((s: any) => s.reason?.replace('No mapping for FUB status: ', '') || s.fub_status || 'Unknown'))].map((status: string, idx: number) => (
                            <li key={idx} className="text-amber-800">{status}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    <p className="text-sm mb-3">
                      To sync these leads, you need to configure stage mappings that tell the system how to translate FUB statuses to platform-specific statuses.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-amber-600 text-amber-700 hover:bg-amber-100"
                      onClick={() => {
                        const source = sources.find(s => s.id === syncResultsSourceId)
                        if (source) {
                          setIsSyncResultsDialogOpen(false)
                          handleOpenMappingDialog(source)
                        }
                      }}
                    >
                      Configure Stage Mappings
                      <ArrowRight className="ml-2 h-4 w-4" />
                    </Button>
                  </AlertDescription>
                </Alert>
              )}

              {syncResults.details && syncResults.details.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium mb-2">Detailed Results:</h4>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {syncResults.details.map((detail: any, index: number) => (
                      <div
                        key={index}
                        className={`p-3 rounded-md border ${
                          detail.status === 'success'
                            ? 'bg-green-50 border-green-200'
                            : detail.status === 'skipped'
                            ? 'bg-amber-50 border-amber-200'
                            : 'bg-red-50 border-red-200'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="font-medium">{detail.name}</div>
                            <div className="text-sm text-muted-foreground">
                              Lead ID: {detail.fub_person_id}
                              {detail.processing_time && (
                                <span className="ml-2">• {detail.processing_time}s</span>
                              )}
                            </div>
                            {detail.error && (
                              <div className="text-sm text-red-600 mt-1">{detail.error}</div>
                            )}
                            {detail.reason && (
                              <div className="text-sm text-amber-600 mt-1">{detail.reason}</div>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={detail.status === 'success' ? 'default' : detail.status === 'skipped' ? 'secondary' : 'destructive'}>
                              {detail.status === 'success' ? (
                                <Check className="mr-1 h-3 w-3" />
                              ) : detail.status === 'skipped' ? (
                                <span className="mr-1">⏭</span>
                              ) : (
                                <X className="mr-1 h-3 w-3" />
                              )}
                              {detail.status}
                            </Badge>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setIsSyncResultsDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Import Results Dialog */}
      <Dialog open={isImportResultsDialogOpen} onOpenChange={setIsImportResultsDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Import Results</DialogTitle>
            <DialogDescription>
              Results of the FUB lead import operation
            </DialogDescription>
          </DialogHeader>
          {importResults && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Total Fetched</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{importResults.total_fetched}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-muted-foreground">Filtered (Active Sources)</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{importResults.total_filtered}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-green-600">Inserted</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-green-600">{importResults.inserted}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium text-blue-600">Updated</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold text-blue-600">{importResults.updated}</div>
                  </CardContent>
                </Card>
                {importResults.errors > 0 && (
                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-sm font-medium text-red-600">Errors</CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold text-red-600">{importResults.errors}</div>
                    </CardContent>
                  </Card>
                )}
              </div>
              
              {importResults.details && importResults.details.length > 0 && importResults.details.length <= 50 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium mb-2">Sample Results (showing {Math.min(50, importResults.details.length)} of {importResults.details.length}):</h4>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {importResults.details.slice(0, 50).map((detail: any, index: number) => (
                      <div
                        key={index}
                        className={`p-3 rounded-md border ${
                          detail.action === 'inserted'
                            ? 'bg-green-50 border-green-200'
                            : detail.action === 'updated'
                            ? 'bg-blue-50 border-blue-200'
                            : 'bg-red-50 border-red-200'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1">
                            <div className="font-medium">{detail.name}</div>
                            <div className="text-sm text-muted-foreground">
                              Source: {detail.source} | FUB ID: {detail.fub_person_id}
                            </div>
                            {detail.error && (
                              <div className="text-sm text-red-600 mt-1">{detail.error}</div>
                            )}
                          </div>
                          <Badge variant={detail.action === 'error' ? 'destructive' : 'default'}>
                            {detail.action === 'inserted' && <Plus className="mr-1 h-3 w-3" />}
                            {detail.action === 'updated' && <RefreshCw className="mr-1 h-3 w-3" />}
                            {detail.action === 'error' && <X className="mr-1 h-3 w-3" />}
                            {detail.action}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setIsImportResultsDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Merge Sources Dialog */}
      <Dialog open={isMergeDialogOpen} onOpenChange={setIsMergeDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Merge Duplicate Sources</DialogTitle>
            <DialogDescription>
              Merge one set of duplicates at a time. Select sources with the same name (e.g., both &quot;ReferralExchange&quot; entries),
              pick the primary, and merge. After merging, you can select another set without closing this dialog.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">Select sources to merge:</Label>
              <div className="border rounded-md max-h-64 overflow-y-auto">
                {sources.map((source) => {
                  const mergedInto = getMergedIntoSource(source.source_name)
                  const isMergedSource = !!mergedInto

                  return (
                    <div
                      key={source.id}
                      className={`flex items-center justify-between p-3 border-b last:border-b-0 hover:bg-muted/50 ${
                        selectedSourcesForMerge.has(source.id) ? 'bg-blue-100 dark:bg-blue-900/30' : ''
                      } ${isMergedSource ? 'opacity-60' : ''}`}
                    >
                      <div className="flex items-center gap-3">
                        <Checkbox
                          id={`merge-${source.id}`}
                          checked={selectedSourcesForMerge.has(source.id)}
                          onCheckedChange={() => handleToggleSourceForMerge(source.id)}
                          disabled={isMergedSource}
                        />
                        <Label htmlFor={`merge-${source.id}`} className={`cursor-pointer ${isMergedSource ? 'cursor-not-allowed' : ''}`}>
                          <span className="font-medium text-foreground">{source.source_name}</span>
                          {isMergedSource && (
                            <span className="ml-2 text-xs text-green-600 flex items-center gap-1 inline-flex">
                              <ArrowRight className="h-3 w-3" />
                              {mergedInto}
                            </span>
                          )}
                          {source.auto_discovered && !isMergedSource && (
                            <Badge variant="secondary" className="ml-2 text-[9px]">Auto-discovered</Badge>
                          )}
                          {!source.is_active && !isMergedSource && (
                            <Badge variant="outline" className="ml-2 text-[9px]">Inactive</Badge>
                          )}
                        </Label>
                      </div>
                      {selectedSourcesForMerge.has(source.id) && selectedSourcesForMerge.size >= 2 && !isMergedSource && (
                        <Button
                          variant={canonicalSourceId === source.id ? "default" : "outline"}
                          size="sm"
                          onClick={() => setCanonicalSourceId(source.id)}
                        >
                          {canonicalSourceId === source.id ? (
                            <>
                              <Check className="mr-1 h-3 w-3" />
                              Primary
                            </>
                          ) : (
                            "Set as Primary"
                          )}
                        </Button>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>

            {selectedSourcesForMerge.size >= 2 && (
              <Alert>
                <AlertDescription>
                  <strong>{selectedSourcesForMerge.size} sources selected.</strong>
                  {canonicalSourceId ? (
                    <span className="ml-1">
                      All leads will be merged into <strong>{getSourceNameById(canonicalSourceId)}</strong>.
                    </span>
                  ) : (
                    <span className="ml-1 text-amber-600">Please select which source should be the primary.</span>
                  )}
                </AlertDescription>
              </Alert>
            )}

            {selectedSourcesForMerge.size >= 2 && canonicalSourceId && (
              <div className="rounded-md border bg-muted/30 p-4">
                <h4 className="font-medium mb-2">Merge Preview:</h4>
                <div className="space-y-2 text-sm">
                  {Array.from(selectedSourcesForMerge)
                    .filter(id => id !== canonicalSourceId)
                    .map(id => (
                      <div key={id} className="flex items-center gap-2">
                        <span className="text-muted-foreground">{getSourceNameById(id)}</span>
                        <ArrowRight className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium text-green-600">{getSourceNameById(canonicalSourceId)}</span>
                      </div>
                    ))}
                </div>
                <p className="text-xs text-muted-foreground mt-3">
                  Existing leads with the above source names will be updated to &quot;{getSourceNameById(canonicalSourceId)}&quot;.
                  The merged sources will be deactivated.
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsMergeDialogOpen(false)} disabled={isMerging}>
              Cancel
            </Button>
            <Button
              onClick={handleMergeSources}
              disabled={isMerging || selectedSourcesForMerge.size < 2 || !canonicalSourceId}
            >
              {isMerging ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Merging...
                </>
              ) : (
                <>
                  <Merge className="mr-2 h-4 w-4" />
                  Merge Sources
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Merge Results Dialog */}
      <Dialog open={isMergeResultDialogOpen} onOpenChange={setIsMergeResultDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Merge Complete</DialogTitle>
            <DialogDescription>
              Sources have been successfully merged.
            </DialogDescription>
          </DialogHeader>
          {mergeResult && (
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Primary Source</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="font-bold text-green-600">{mergeResult.canonical_source_name}</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Leads Updated</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{mergeResult.leads_updated}</div>
                  </CardContent>
                </Card>
              </div>

              {mergeResult.aliases_created.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Aliases Created:</h4>
                  <div className="flex flex-wrap gap-2">
                    {mergeResult.aliases_created.map((alias, idx) => (
                      <Badge key={idx} variant="secondary">{alias}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {mergeResult.sources_deactivated.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium mb-2">Sources Deactivated:</h4>
                  <div className="flex flex-wrap gap-2">
                    {mergeResult.sources_deactivated.map((source, idx) => (
                      <Badge key={idx} variant="outline">{source}</Badge>
                    ))}
                  </div>
                </div>
              )}

              {mergeResult.errors.length > 0 && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Some errors occurred:</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4 mt-2">
                      {mergeResult.errors.map((err, idx) => (
                        <li key={idx}>{err.source_name}: {err.error}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setIsMergeResultDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Aliases Dialog */}
      <Dialog open={isViewAliasesDialogOpen} onOpenChange={setIsViewAliasesDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Source Mappings</DialogTitle>
            <DialogDescription>
              These are the alias mappings created from merging duplicate sources.
              Future imports will automatically use the canonical source name.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {aliases.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                No alias mappings found. Use &quot;Merge Duplicates&quot; to create mappings.
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Alias Name</TableHead>
                    <TableHead>Maps To</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {aliases.map((alias) => (
                    <TableRow key={alias.id}>
                      <TableCell className="font-medium">{alias.alias_name}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <ArrowRight className="h-4 w-4 text-muted-foreground" />
                          <span className="text-green-600 font-medium">
                            {alias.canonical_source_name || 'Unknown'}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {new Date(alias.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteAlias(alias.id)}
                        >
                          <Trash className="h-4 w-4 text-red-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
          <DialogFooter>
            <Button onClick={() => setIsViewAliasesDialogOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Stage Mapping Dialog */}
      <Dialog open={isMappingDialogOpen} onOpenChange={(open) => {
        setIsMappingDialogOpen(open)
        if (!open) {
          setSelectedMappingSource(null)
          setMappings({})
        }
      }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Stage Mapping - {selectedMappingSource?.source_name}</DialogTitle>
            <DialogDescription>
              Map Follow Up Boss stages to {selectedMappingSource?.source_name} statuses for buyer and seller leads.
              {(() => {
                const options = getSourceOptions(selectedMappingSource ?? undefined)
                const hasTypedOptions = options.some(opt => opt.label.startsWith('Buyer - ') || opt.label.startsWith('Seller - '))
                return !hasTypedOptions && options.length > 0 ? (
                  <span className="block mt-1 text-muted-foreground text-xs">
                    Note: This platform uses the same options for both buyer and seller leads.
                  </span>
                ) : null
              })()}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            {fubStages.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin mr-2" />
                <span>Loading FUB stages...</span>
              </div>
            ) : (
              <div className="border rounded-lg overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="bg-muted/50">
                      <TableHead className="w-[200px] min-w-[200px]">Follow Up Boss Stage</TableHead>
                      <TableHead className="w-[280px] min-w-[280px] bg-blue-50 dark:bg-blue-950">
                        <div className="flex items-center gap-2">
                          <span className="inline-block w-2 h-2 bg-blue-500 rounded-full"></span>
                          Buyer Lead Status
                        </div>
                      </TableHead>
                      <TableHead className="w-[280px] min-w-[280px] bg-pink-50 dark:bg-pink-950">
                        <div className="flex items-center gap-2">
                          <span className="inline-block w-2 h-2 bg-pink-500 rounded-full"></span>
                          Seller Lead Status
                        </div>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {fubStages.map((stage) => {
                      const platformOptions = getSourceOptions(selectedMappingSource ?? undefined)
                      const buyerOptions = filterOptionsByType(platformOptions, 'buyer')
                      const sellerOptions = filterOptionsByType(platformOptions, 'seller')
                      const mapping = mappings[stage.name] || { buyer: '', seller: '' }

                      return (
                        <TableRow key={stage.id}>
                          <TableCell className="font-medium">
                            <span className="text-sm">{stage.name}</span>
                          </TableCell>
                          <TableCell className="bg-blue-50/30 dark:bg-blue-950/30">
                            <Select
                              value={mapping.buyer || "__none__"}
                              onValueChange={(value) => handleMappingChange(stage.name, 'buyer', value === "__none__" ? "" : value)}
                            >
                              <SelectTrigger className="w-full border-blue-200 dark:border-blue-800">
                                <SelectValue placeholder="Select status for buyer leads" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__">-- No mapping --</SelectItem>
                                {buyerOptions.map(option => (
                                  <SelectItem key={`buyer-${option.value}`} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className="bg-pink-50/30 dark:bg-pink-950/30">
                            <Select
                              value={mapping.seller || "__none__"}
                              onValueChange={(value) => handleMappingChange(stage.name, 'seller', value === "__none__" ? "" : value)}
                            >
                              <SelectTrigger className="w-full border-pink-200 dark:border-pink-800">
                                <SelectValue placeholder="Select status for seller leads" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value="__none__">-- No mapping --</SelectItem>
                                {sellerOptions.map(option => (
                                  <SelectItem key={`seller-${option.value}`} value={option.value}>
                                    {option.label}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsMappingDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSaveMappings} disabled={isSavingMappings || fubStages.length === 0}>
              {isSavingMappings ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                "Save Mappings"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </SidebarWrapper>
  )
}
