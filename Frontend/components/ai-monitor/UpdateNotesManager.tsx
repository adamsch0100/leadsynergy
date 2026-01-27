"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Check, X, Edit, Loader2, FileText } from "lucide-react"
import { cn } from "@/lib/utils"

interface PendingNote {
  id: string
  person_id: number
  note_type: string
  note_content: string
  raw_value: string
  confidence: number
  status: string
  created_at: string
}

interface UpdateNotesManagerProps {
  notes: PendingNote[]
  onApprove: (noteId: string) => Promise<void>
  onDismiss: (noteId: string) => Promise<void>
  onBulkApprove: (noteIds: string[]) => Promise<void>
  className?: string
}

const API_BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function UpdateNotesManager({
  notes,
  onApprove,
  onDismiss,
  onBulkApprove,
  className
}: UpdateNotesManagerProps) {
  const [selectedNotes, setSelectedNotes] = useState<Set<string>>(new Set())
  const [processingNotes, setProcessingNotes] = useState<Set<string>>(new Set())
  const [bulkProcessing, setBulkProcessing] = useState(false)

  const pendingNotes = notes.filter(n => n.status === 'pending')

  const toggleSelect = (noteId: string) => {
    setSelectedNotes(prev => {
      const next = new Set(prev)
      if (next.has(noteId)) {
        next.delete(noteId)
      } else {
        next.add(noteId)
      }
      return next
    })
  }

  const selectAll = () => {
    if (selectedNotes.size === pendingNotes.length) {
      setSelectedNotes(new Set())
    } else {
      setSelectedNotes(new Set(pendingNotes.map(n => n.id)))
    }
  }

  const handleApprove = async (noteId: string) => {
    setProcessingNotes(prev => new Set(prev).add(noteId))
    try {
      await onApprove(noteId)
      setSelectedNotes(prev => {
        const next = new Set(prev)
        next.delete(noteId)
        return next
      })
    } finally {
      setProcessingNotes(prev => {
        const next = new Set(prev)
        next.delete(noteId)
        return next
      })
    }
  }

  const handleDismiss = async (noteId: string) => {
    setProcessingNotes(prev => new Set(prev).add(noteId))
    try {
      await onDismiss(noteId)
      setSelectedNotes(prev => {
        const next = new Set(prev)
        next.delete(noteId)
        return next
      })
    } finally {
      setProcessingNotes(prev => {
        const next = new Set(prev)
        next.delete(noteId)
        return next
      })
    }
  }

  const handleBulkApprove = async () => {
    if (selectedNotes.size === 0) return
    setBulkProcessing(true)
    try {
      await onBulkApprove(Array.from(selectedNotes))
      setSelectedNotes(new Set())
    } finally {
      setBulkProcessing(false)
    }
  }

  const getNoteTypeColor = (noteType: string) => {
    const colors: Record<string, string> = {
      timeline: "bg-blue-100 text-blue-700",
      budget: "bg-green-100 text-green-700",
      pre_approval: "bg-purple-100 text-purple-700",
      areas: "bg-orange-100 text-orange-700",
      motivation: "bg-pink-100 text-pink-700",
      property_type: "bg-cyan-100 text-cyan-700",
    }
    return colors[noteType] || "bg-gray-100 text-gray-700"
  }

  const formatConfidence = (confidence: number) => {
    return `${Math.round(confidence * 100)}%`
  }

  if (pendingNotes.length === 0) {
    return (
      <div className={cn("flex flex-col items-center justify-center py-6 text-muted-foreground", className)}>
        <FileText className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">No pending @update notes</p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-3", className)}>
      {/* Bulk actions header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Checkbox
            checked={selectedNotes.size === pendingNotes.length && pendingNotes.length > 0}
            onCheckedChange={selectAll}
          />
          <span className="text-sm text-muted-foreground">
            {selectedNotes.size > 0
              ? `${selectedNotes.size} selected`
              : `${pendingNotes.length} pending notes`}
          </span>
        </div>

        {selectedNotes.size > 0 && (
          <Button
            size="sm"
            onClick={handleBulkApprove}
            disabled={bulkProcessing}
          >
            {bulkProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin mr-1" />
            ) : (
              <Check className="h-4 w-4 mr-1" />
            )}
            Approve Selected
          </Button>
        )}
      </div>

      {/* Notes list */}
      <div className="space-y-2">
        {pendingNotes.map((note) => (
          <Card key={note.id} className="overflow-hidden">
            <CardContent className="p-3">
              <div className="flex items-start gap-3">
                <Checkbox
                  checked={selectedNotes.has(note.id)}
                  onCheckedChange={() => toggleSelect(note.id)}
                  disabled={processingNotes.has(note.id)}
                />

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className={cn("text-xs", getNoteTypeColor(note.note_type))}>
                      {note.note_type.replace('_', ' ')}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {formatConfidence(note.confidence)} confidence
                    </span>
                  </div>

                  <p className="text-sm font-medium truncate" title={note.note_content}>
                    {note.note_content}
                  </p>

                  <p className="text-xs text-muted-foreground mt-1">
                    Extracted: {note.raw_value}
                  </p>
                </div>

                <div className="flex items-center gap-1 flex-shrink-0">
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-green-600 hover:text-green-700 hover:bg-green-50"
                    onClick={() => handleApprove(note.id)}
                    disabled={processingNotes.has(note.id)}
                    title="Approve"
                  >
                    {processingNotes.has(note.id) ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Check className="h-4 w-4" />
                    )}
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-8 w-8 text-red-600 hover:text-red-700 hover:bg-red-50"
                    onClick={() => handleDismiss(note.id)}
                    disabled={processingNotes.has(note.id)}
                    title="Dismiss"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
