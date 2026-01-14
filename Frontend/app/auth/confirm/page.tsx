"use client"

import { useState, useEffect } from "react"
import { useRouter, useSearchParams } from "next/navigation"
import { CheckCircle2, XCircle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card"

export default function EmailConfirmPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const token = searchParams.get("token")
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading")

  useEffect(() => {
    const verifyEmail = async () => {
      try {
        // Simulate API verification
        await new Promise(resolve => setTimeout(resolve, 2000))
        setStatus("success")
      } catch (err) {
        setStatus("error")
      }
    }

    if (token) {
      verifyEmail()
    } else {
      setStatus("error")
    }
  }, [token])

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="w-full max-w-md">
        <Card className="border-none shadow-lg">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center justify-center text-center">
              {status === "loading" && (
                <>
                  <Loader2 className="h-12 w-12 text-blue-500 animate-spin mb-4" />
                  <CardTitle className="text-2xl font-bold mb-2">
                    Verifying Your Email
                  </CardTitle>
                  <CardDescription>
                    Please wait while we verify your email address...
                  </CardDescription>
                </>
              )}

              {status === "success" && (
                <>
                  <CheckCircle2 className="h-12 w-12 text-green-500 mb-4" />
                  <CardTitle className="text-2xl font-bold mb-2">
                    Email Verified Successfully
                  </CardTitle>
                  <CardDescription className="mb-6">
                    Your email address has been verified. You can now access all features of your account.
                  </CardDescription>
                  <Button className="w-full" onClick={() => router.push("/login")}>
                    Continue to Login
                  </Button>
                </>
              )}

              {status === "error" && (
                <>
                  <XCircle className="h-12 w-12 text-red-500 mb-4" />
                  <CardTitle className="text-2xl font-bold mb-2">
                    Verification Failed
                  </CardTitle>
                  <CardDescription className="mb-6">
                    The verification link is invalid or has expired. Please request a new verification email.
                  </CardDescription>
                  <Button 
                    className="w-full" 
                    variant="outline"
                    onClick={() => {
                      // In a real app, this would trigger a new verification email
                      router.push("/login")
                    }}
                  >
                    Request New Verification
                  </Button>
                </>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}