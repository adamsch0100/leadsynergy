"use client"

import { useState } from "react"
import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { SidebarWrapper } from "@/components/sidebar"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertTriangle, Lock } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useSubscription } from "@/contexts/subscription-context"

export default function AssignmentRulesPage() {
  const { subscription } = useSubscription()
  const [selectedSource, setSelectedSource] = useState<string>("")
  const [showUpgradeAlert, setShowUpgradeAlert] = useState(false)

  const [sources] = useState([
    { id: "1", name: "Zillow", strategy: "round-robin" },
    { id: "2", name: "Realtor.com", strategy: "jump-ball" },
    { id: "3", name: "Website Form", strategy: "not-configured" },
  ])

  const [rules] = useState([
    {
      id: "1",
      name: "Round Robin",
      type: "basic",
      description: "Distribute leads equally among all active agents",
      enabled: true,
    },
    {
      id: "2",
      name: "Performance Based",
      type: "advanced",
      description: "Assign leads based on agent conversion rates",
      enabled: false,
      premiumOnly: true,
    },
    {
      id: "3",
      name: "Availability Based",
      type: "advanced",
      description: "Consider agent workload and availability",
      enabled: false,
      premiumOnly: true,
    },
    {
      id: "4",
      name: "Expertise Match",
      type: "advanced",
      description: "Match leads with agents based on property type expertise",
      enabled: false,
      premiumOnly: true,
    },
  ])

  const handleRuleClick = (rule: typeof rules[0]) => {
    if (rule.premiumOnly && subscription.plan === "free") {
      setShowUpgradeAlert(true)
    }
  }

  return (
    <SidebarWrapper role="admin">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Assignment Rules</h1>
          <p className="text-muted-foreground">Configure how leads are distributed to your team</p>
        </div>
      </div>

      {showUpgradeAlert && (
        <Alert className="mb-6">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Premium Feature</AlertTitle>
          <AlertDescription className="mt-2">
            Advanced assignment rules are only available on Pro and Enterprise plans.
            <div className="mt-2">
              <Button variant="outline" asChild className="mr-2">
                <Link href="/admin/billing">Upgrade Plan</Link>
              </Button>
              <Button variant="ghost" onClick={() => setShowUpgradeAlert(false)}>
                Dismiss
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Lead Assignment Strategy</CardTitle>
          <CardDescription>Choose how you want to distribute leads to your team</CardDescription>
        </CardHeader>
        <CardContent>
          <RadioGroup className="space-y-4">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className={`relative flex items-start space-x-4 rounded-lg border p-4 ${
                  rule.premiumOnly && subscription.plan === "free"
                    ? "opacity-50 cursor-not-allowed"
                    : "cursor-pointer"
                }`}
                onClick={() => handleRuleClick(rule)}
              >
                <RadioGroupItem
                  value={rule.id}
                  id={rule.id}
                  disabled={rule.premiumOnly && subscription.plan === "free"}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <Label htmlFor={rule.id} className="text-base font-medium">
                      {rule.name}
                    </Label>
                    {rule.premiumOnly && subscription.plan === "free" && (
                      <Badge variant="outline" className="ml-2">
                        <Lock className="mr-1 h-3 w-3" /> Premium
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">{rule.description}</p>
                </div>
              </div>
            ))}
          </RadioGroup>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Source-Specific Rules</CardTitle>
          <CardDescription>Configure rules for individual lead sources</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="grid gap-2">
              <Label>Select Lead Source</Label>
              <Select value={selectedSource} onValueChange={setSelectedSource}>
                <SelectTrigger>
                  <SelectValue placeholder="Choose a lead source" />
                </SelectTrigger>
                <SelectContent>
                  {sources.map((source) => (
                    <SelectItem key={source.id} value={source.id}>
                      {source.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}
