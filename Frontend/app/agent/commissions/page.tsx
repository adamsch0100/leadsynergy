"use client"

import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { DollarSign, Plus } from "lucide-react"
import { CommissionModal, type CommissionData } from "./commission-modal"

interface Commission {
  id: string
  propertyAddress: string
  contractDate: string
  closingDate: string
  commissionAmount: string
  status: "pending" | "approved" | "paid"
}

export default function CommissionsPage() {
  const [commissions, setCommissions] = useState<Commission[]>([
    {
      id: "1",
      propertyAddress: "123 Main St, Anytown, CA 12345",
      contractDate: "2023-04-15",
      closingDate: "2023-05-20",
      commissionAmount: "$5,250",
      status: "paid",
    },
    {
      id: "2",
      propertyAddress: "456 Oak Ave, Somewhere, CA 67890",
      contractDate: "2023-05-10",
      closingDate: "2023-06-15",
      commissionAmount: "$7,800",
      status: "approved",
    },
    {
      id: "3",
      propertyAddress: "789 Pine Rd, Nowhere, CA 54321",
      contractDate: "2023-06-05",
      closingDate: "2023-07-10",
      commissionAmount: "$6,300",
      status: "pending",
    },
  ])

  const handleAddCommission = (data: CommissionData) => {
    const newCommission: Commission = {
      id: Date.now().toString(),
      propertyAddress: data.propertyAddress,
      contractDate: data.contractDate ? new Date(data.contractDate).toISOString().split("T")[0] : "",
      closingDate: data.closingDate ? new Date(data.closingDate).toISOString().split("T")[0] : "",
      commissionAmount: `$${(data.commissionPercentage * 1000).toLocaleString()}`,
      status: "pending",
    }

    setCommissions([...commissions, newCommission])
  }

  return (
    <SidebarWrapper role="agent">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Commissions</h1>
          <p className="text-muted-foreground">Track and manage your real estate commissions</p>
        </div>
        <CommissionModal
          trigger={
            <Button>
              <Plus className="mr-2 h-4 w-4" />
              Add Commission
            </Button>
          }
          onSubmit={handleAddCommission}
        />
      </div>

      <div className="grid gap-6 md:grid-cols-3 mb-8">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Total Commissions</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$19,350</div>
            <p className="text-xs text-muted-foreground">Across all properties</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Pending Commissions</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$6,300</div>
            <p className="text-xs text-muted-foreground">Awaiting approval</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">Paid Commissions</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$5,250</div>
            <p className="text-xs text-muted-foreground">Received this month</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Commission History</CardTitle>
          <CardDescription>View and manage all your commission records</CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Property Address</TableHead>
                <TableHead>Contract Date</TableHead>
                <TableHead>Closing Date</TableHead>
                <TableHead>Commission</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commissions.map((commission) => (
                <TableRow key={commission.id}>
                  <TableCell className="font-medium">{commission.propertyAddress}</TableCell>
                  <TableCell>{commission.contractDate}</TableCell>
                  <TableCell>{commission.closingDate}</TableCell>
                  <TableCell>{commission.commissionAmount}</TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        commission.status === "paid"
                          ? "default"
                          : commission.status === "approved"
                            ? "outline"
                            : "secondary"
                      }
                    >
                      {commission.status}
                    </Badge>
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
