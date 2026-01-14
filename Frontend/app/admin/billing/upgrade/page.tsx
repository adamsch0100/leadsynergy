"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { ArrowLeft, Check, CreditCard } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useSubscription } from "@/contexts/subscription-context"
import { Badge } from "@/components/ui/badge"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Label } from "@/components/ui/label"

interface PaymentMethod {
  id: string
  type: string
  lastFour: string
  expiryDate: string
  isDefault: boolean
}

const planDetails = {
  free: {
    name: "Free Plan",
    price: "$0/month",
    description: "Perfect for small teams"
  },
  pro: {
    name: "Pro Plan",
    price: "$49/month",
    description: "For growing real estate teams"
  },
  enterprise: {
    name: "Enterprise Plan",
    price: "Custom pricing",
    description: "For large brokerages"
  }
}

export default function UpgradePage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const planParam = searchParams.get("plan") || "free"
  const { subscription } = useSubscription()
  
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")
  const [isSuccess, setIsSuccess] = useState(false)
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState("")

  const currentPlan = planDetails[planParam as keyof typeof planDetails]

  // TODO: Replace with actual payment methods from API
  const mockPaymentMethods: PaymentMethod[] = [
    {
      id: "1",
      type: "visa",
      lastFour: "4242",
      expiryDate: "12/25",
      isDefault: true
    },
    {
      id: "2",
      type: "mastercard",
      lastFour: "8888",
      expiryDate: "06/24",
      isDefault: false
    }
  ]

  const handleUpgrade = async () => {
    if (!selectedPaymentMethod && planParam !== "free") {
      setError("Please select a payment method")
      return
    }

    setError("")
    setIsLoading(true)

    try {
      // In a real app, this would make an API call to update the subscription
      await new Promise(resolve => setTimeout(resolve, 1000))
      setIsSuccess(true)
    } catch (err) {
      setError("Failed to process the subscription change")
    } finally {
      setIsLoading(false)
    }
  }

  if (isSuccess) {
    return (
      <div className="container max-w-md mx-auto py-8">
        <Card className="border-none shadow-lg">
          <CardContent className="pt-6">
            <div className="mb-6 text-center">
              <div className="mx-auto h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mb-4">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold mb-2">Subscription Updated!</h2>
              <p className="text-muted-foreground">
                Your subscription has been successfully updated to the {currentPlan.name}.
              </p>
            </div>
            <Button className="w-full" onClick={() => router.push("/admin/dashboard")}>
              Return to Dashboard
            </Button>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="container max-w-md mx-auto py-8">
      <div className="mb-8">
        <Button
          variant="ghost"
          onClick={() => router.back()}
          className="flex items-center gap-2"
        >
          <ArrowLeft className="h-4 w-4" />
          Back
        </Button>
      </div>

      <Card className="border-none shadow-lg">
        <CardHeader>
          <CardTitle>Upgrade Subscription</CardTitle>
          <CardDescription>
            Review and confirm your subscription change
          </CardDescription>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="mb-6 p-4 bg-primary/5 rounded-lg">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold">{currentPlan.name}</h3>
              <span className="font-medium">{currentPlan.price}</span>
            </div>
            <p className="text-sm text-muted-foreground">{currentPlan.description}</p>
          </div>

          {planParam !== "free" && (
            <div className="space-y-4">
              <Label>Select Payment Method</Label>
              <RadioGroup
                value={selectedPaymentMethod}
                onValueChange={setSelectedPaymentMethod}
              >
                {mockPaymentMethods.map(method => (
                  <div key={method.id} className="flex items-center space-x-2">
                    <RadioGroupItem value={method.id} id={method.id} />
                    <Label htmlFor={method.id} className="flex items-center gap-2">
                      <CreditCard className="h-4 w-4" />
                      <span>•••• {method.lastFour}</span>
                      {method.isDefault && (
                        <Badge variant="outline" className="ml-2">Default</Badge>
                      )}
                    </Label>
                  </div>
                ))}
              </RadioGroup>
            </div>
          )}
        </CardContent>
        <CardFooter>
          <Button 
            className="w-full" 
            onClick={handleUpgrade}
            disabled={isLoading || (!selectedPaymentMethod && planParam !== "free")}
          >
            {isLoading ? "Processing..." : `Confirm Subscription Change`}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}