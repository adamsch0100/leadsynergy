"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/components/ui/button"
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
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CalendarIcon, Upload } from "lucide-react"
import { cn } from "@/lib/utils"
import { format } from "date-fns"

interface CommissionModalProps {
  trigger: React.ReactNode
  onSubmit?: (data: CommissionData) => void
}

export interface CommissionData {
  propertyAddress: string
  contractDate: Date | undefined
  closingDate: Date | undefined
  commissionPercentage: number
  file: File | null
}

export function CommissionModal({ trigger, onSubmit }: CommissionModalProps) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState<CommissionData>({
    propertyAddress: "",
    contractDate: undefined,
    closingDate: undefined,
    commissionPercentage: 0,
    file: null,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (onSubmit) {
      onSubmit(data)
    }
    setOpen(false)
    // Reset form
    setData({
      propertyAddress: "",
      contractDate: undefined,
      closingDate: undefined,
      commissionPercentage: 0,
      file: null,
    })
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setData({ ...data, file: e.target.files[0] })
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-[500px]">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Track Commission</DialogTitle>
            <DialogDescription>Enter the details of your commission for this property.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="propertyAddress">Property Address</Label>
              <Input
                id="propertyAddress"
                value={data.propertyAddress}
                onChange={(e) => setData({ ...data, propertyAddress: e.target.value })}
                placeholder="123 Main St, City, State, ZIP"
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="contractDate">Contract Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !data.contractDate && "text-muted-foreground",
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {data.contractDate ? format(data.contractDate, "PPP") : <span>Pick a date</span>}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0">
                    <Calendar
                      mode="single"
                      selected={data.contractDate}
                      onSelect={(date) => setData({ ...data, contractDate: date })}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="closingDate">Closing Date</Label>
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      className={cn(
                        "w-full justify-start text-left font-normal",
                        !data.closingDate && "text-muted-foreground",
                      )}
                    >
                      <CalendarIcon className="mr-2 h-4 w-4" />
                      {data.closingDate ? format(data.closingDate, "PPP") : <span>Pick a date</span>}
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto p-0">
                    <Calendar
                      mode="single"
                      selected={data.closingDate}
                      onSelect={(date) => setData({ ...data, closingDate: date })}
                      initialFocus
                    />
                  </PopoverContent>
                </Popover>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="commissionPercentage">Commission Percentage</Label>
              <div className="relative">
                <Input
                  id="commissionPercentage"
                  type="number"
                  min="0"
                  max="100"
                  step="0.01"
                  value={data.commissionPercentage || ""}
                  onChange={(e) =>
                    setData({
                      ...data,
                      commissionPercentage: Number.parseFloat(e.target.value) || 0,
                    })
                  }
                  className="pr-8"
                  required
                />
                <span className="absolute right-3 top-2">%</span>
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="file">Upload Proof of Commission</Label>
              <div className="flex items-center gap-2">
                <Input
                  id="file"
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => document.getElementById("file")?.click()}
                  className="w-full"
                >
                  <Upload className="mr-2 h-4 w-4" />
                  {data.file ? data.file.name : "Choose file"}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">Accepted formats: PDF, JPG, PNG (max 5MB)</p>
            </div>
          </div>
          <DialogFooter>
            <Button type="submit">Submit Commission</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
