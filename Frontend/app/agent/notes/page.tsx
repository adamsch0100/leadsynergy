"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { MessageSquare, Plus, Clock, Search } from "lucide-react"

interface Note {
  id: string
  leadName: string
  content: string
  date: string
  important: boolean
}

export default function NotesPage() {
  const [notes, setNotes] = useState<Note[]>([
    {
      id: "1",
      leadName: "John Smith",
      content: "Called to discuss property requirements. Interested in 3-bedroom homes in the north area.",
      date: "2 hours ago",
      important: true,
    },
    {
      id: "2",
      leadName: "Sarah Johnson",
      content: "Scheduled property viewing for next week. Looking for modern condos.",
      date: "1 day ago",
      important: false,
    },
    {
      id: "3",
      leadName: "Michael Brown",
      content: "Followed up about the offer. Waiting for response from seller.",
      date: "3 days ago",
      important: true,
    }
  ])

  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  const [selectedLead, setSelectedLead] = useState("")
  const [newNoteContent, setNewNoteContent] = useState("")

  const leads = [
    "John Smith",
    "Sarah Johnson",
    "Michael Brown",
    "Emily Davis",
    "Robert Wilson"
  ]

  const handleAddNote = () => {
    if (selectedLead && newNoteContent) {
      const newNote: Note = {
        id: Date.now().toString(),
        leadName: selectedLead,
        content: newNoteContent,
        date: "Just now",
        important: false,
      }
      setNotes([newNote, ...notes])
      setIsAddDialogOpen(false)
      setSelectedLead("")
      setNewNoteContent("")
    }
  }

  const filteredNotes = notes.filter(note => 
    note.leadName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    note.content.toLowerCase().includes(searchTerm.toLowerCase())
  )

  return (
    <SidebarWrapper role="agent">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Notes</h1>
          <p className="text-muted-foreground">Keep track of important lead interactions and updates</p>
        </div>
        <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Note
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Note</DialogTitle>
              <DialogDescription>Create a new note for your lead</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="lead">Select Lead</Label>
                <Select value={selectedLead} onValueChange={setSelectedLead}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a lead" />
                  </SelectTrigger>
                  <SelectContent>
                    {leads.map((lead) => (
                      <SelectItem key={lead} value={lead}>
                        {lead}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="note">Note Content</Label>
                <Textarea
                  id="note"
                  value={newNoteContent}
                  onChange={(e) => setNewNoteContent(e.target.value)}
                  placeholder="Enter your note here..."
                  rows={4}
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddNote} disabled={!selectedLead || !newNoteContent}>
                Save Note
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Lead Notes</CardTitle>
          <CardDescription>View and manage your notes for all leads</CardDescription>
          <div className="mt-4 relative">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search notes..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-9"
            />
          </div>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Lead Name</TableHead>
                <TableHead>Note</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredNotes.map((note) => (
                <TableRow key={note.id}>
                  <TableCell className="font-medium">{note.leadName}</TableCell>
                  <TableCell>
                    <div className="flex items-start gap-2">
                      <MessageSquare className="h-4 w-4 mt-1 text-muted-foreground shrink-0" />
                      <span className="text-sm">{note.content}</span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1 text-sm text-muted-foreground">
                      <Clock className="h-4 w-4" />
                      {note.date}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}