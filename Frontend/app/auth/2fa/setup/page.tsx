"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Smartphone, QrCode, Copy, Shield, CheckCircle2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export default function TwoFactorSetupPage() {
  const router = useRouter()
  const [step, setStep] = useState<"qr" | "verify">("qr")
  const [verificationCode, setVerificationCode] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState("")
  const [recoveryCodesVisible, setRecoveryCodesVisible] = useState(false)
  
  // In a real app, these would come from the API
  const qrCodeUrl = "https://placeholder.com/qr"
  const secretKey = "ABCD EFGH IJKL MNOP"
  const recoveryCodes = [
    "1234-5678-9012",
    "3456-7890-1234",
    "5678-9012-3456",
    "7890-1234-5678",
    "9012-3456-7890",
  ]

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      // Simulate API verification
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      if (verificationCode === "123456") {
        setRecoveryCodesVisible(true)
      } else {
        throw new Error("Invalid verification code")
      }
    } catch (err) {
      setError("Invalid verification code. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  const handleCopySecretKey = () => {
    navigator.clipboard.writeText(secretKey)
  }

  const handleCopyRecoveryCodes = () => {
    navigator.clipboard.writeText(recoveryCodes.join("\n"))
  }

  const handleFinish = () => {
    router.push("/login?message=2FA enabled successfully")
  }

  if (recoveryCodesVisible) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
        <div className="w-full max-w-md">
          <Card className="border-none shadow-lg">
            <CardHeader className="space-y-1">
              <div className="flex items-center gap-2 justify-center mb-2">
                <Shield className="h-6 w-6 text-green-600" />
                <CardTitle className="text-2xl font-bold">2FA Enabled!</CardTitle>
              </div>
              <CardDescription className="text-center">
                Save these recovery codes in a secure place. You'll need them if you lose access to your authenticator app.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="bg-muted/50 rounded-lg p-4 mb-4 font-mono text-sm">
                {recoveryCodes.map((code, index) => (
                  <div key={code} className="flex justify-between items-center mb-2 last:mb-0">
                    <span>{code}</span>
                    {index === 0 && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-6 w-6"
                        onClick={handleCopyRecoveryCodes}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
              <Alert>
                <AlertDescription>
                  Store these codes safely! They will only be shown once.
                </AlertDescription>
              </Alert>
            </CardContent>
            <CardFooter>
              <Button className="w-full" onClick={handleFinish}>
                I've Saved My Recovery Codes
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="w-full max-w-md">
        <Card className="border-none shadow-lg">
          <CardHeader className="space-y-1">
            <div className="flex items-center gap-2 justify-center mb-2">
              <Shield className="h-6 w-6" />
              <CardTitle className="text-2xl font-bold">Set Up Two-Factor Authentication</CardTitle>
            </div>
            <CardDescription className="text-center">
              Enhance your account security by enabling two-factor authentication
            </CardDescription>
          </CardHeader>
          <CardContent>
            {step === "qr" ? (
              <div className="space-y-4">
                <div className="rounded-lg bg-muted/50 p-4">
                  <div className="mb-4">
                    <h3 className="font-semibold mb-2">1. Install an authenticator app</h3>
                    <p className="text-sm text-muted-foreground">
                      We recommend Google Authenticator or Authy
                    </p>
                  </div>
                  <div className="mb-4">
                    <h3 className="font-semibold mb-2">2. Scan this QR code</h3>
                    <div className="bg-white p-4 rounded-lg inline-block">
                      <QrCode className="h-32 w-32 text-primary" />
                    </div>
                  </div>
                  <div>
                    <h3 className="font-semibold mb-2">Can't scan the QR code?</h3>
                    <p className="text-sm text-muted-foreground mb-2">
                      Enter this key manually in your app:
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="bg-muted rounded px-2 py-1 text-sm font-mono">
                        {secretKey}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={handleCopySecretKey}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
                <Button className="w-full" onClick={() => setStep("verify")}>
                  Next
                </Button>
              </div>
            ) : (
              <form onSubmit={handleVerify} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="code">Enter Verification Code</Label>
                  <div className="relative">
                    <Smartphone className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                    <Input
                      id="code"
                      placeholder="123456"
                      className="pl-10"
                      value={verificationCode}
                      onChange={(e) => setVerificationCode(e.target.value)}
                      maxLength={6}
                      required
                    />
                  </div>
                  {error && (
                    <Alert variant="destructive">
                      <AlertDescription>{error}</AlertDescription>
                    </Alert>
                  )}
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? "Verifying..." : "Verify & Enable 2FA"}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}