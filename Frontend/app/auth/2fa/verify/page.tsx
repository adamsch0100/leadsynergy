"use client"

import { useState } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { Smartphone, Key } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

export default function TwoFactorVerifyPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const email = searchParams.get("email")
  
  const [method, setMethod] = useState<"app" | "recovery">("app")
  const [code, setCode] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      // Simulate API verification
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      if (method === "app" && code === "123456" || method === "recovery" && code === "1234-5678-9012") {
        if (email?.includes("admin")) {
          router.push("/admin/dashboard")
        } else {
          router.push("/agent/dashboard")
        }
      } else {
        throw new Error("Invalid code")
      }
    } catch (err) {
      setError(method === "app" ? 
        "Invalid verification code. Please try again." : 
        "Invalid recovery code. Please try again."
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="w-full max-w-md">
        <Card className="border-none shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">Two-Factor Authentication</CardTitle>
            <CardDescription className="text-center">
              Enter your verification code to continue
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs value={method} onValueChange={(value) => setMethod(value as "app" | "recovery")}>
              <TabsList className="grid w-full grid-cols-2 mb-4">
                <TabsTrigger value="app">Authenticator App</TabsTrigger>
                <TabsTrigger value="recovery">Recovery Code</TabsTrigger>
              </TabsList>
              <TabsContent value="app">
                <form onSubmit={handleVerify} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="code">Enter 6-digit Code</Label>
                    <div className="relative">
                      <Smartphone className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="code"
                        placeholder="123456"
                        className="pl-10"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        maxLength={6}
                        required
                      />
                    </div>
                  </div>
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? "Verifying..." : "Verify & Sign In"}
                  </Button>
                </form>
              </TabsContent>
              <TabsContent value="recovery">
                <form onSubmit={handleVerify} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="recovery">Enter Recovery Code</Label>
                    <div className="relative">
                      <Key className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                      <Input
                        id="recovery"
                        placeholder="1234-5678-9012"
                        className="pl-10"
                        value={code}
                        onChange={(e) => setCode(e.target.value)}
                        required
                      />
                    </div>
                  </div>
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                  <Button type="submit" className="w-full" disabled={isLoading}>
                    {isLoading ? "Verifying..." : "Verify & Sign In"}
                  </Button>
                </form>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}