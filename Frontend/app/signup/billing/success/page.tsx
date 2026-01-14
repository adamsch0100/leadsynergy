"use client";

import { useDebugValue, useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { completeSignup } from "@/app/auth/actions";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Check, Loader } from "lucide-react";
import { error } from "console";

export default function CheckoutSuccessPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"processing" | "success" | "error">(
    "processing"
  );
  const [error, setError] = useState("");

  useEffect(() => {
    const sessionId = searchParams.get("session_id");

    if (!sessionId) {
      setStatus("error");
      setError("Invalid checkout session");
      return;
    }

    // Complete the signup process
    const finishSignup = async () => {
      try {
        const result = await completeSignup();

        if (result.success) {
          setStatus("success");
        } else {
          setStatus("error");
          setError(result.error || "Failed to complete signup");
        }
      } catch (error: any) {
        setStatus("error");
        setError(error.message || "An unexpected error occurred");
      }
    };

    finishSignup();
  }, [searchParams]);

  return (
    <div className="flex min-h screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardContent className="pt-6">
          {status === "processing" && (
            <div className="text-center py-8">
              <Loader className="h-12 w-12 animate-spin mx-auto mb-4" />
              <h2 className="text-2xl font-bol">Finalizing your account...</h2>
              <p className="text-muted-foreground mt-2">
                Please wait while we set up your account
              </p>
            </div>
          )}
          {status === "success" && (
            <div className="text-center py-8">
              <div className="mx-auto h-12 w-12 bg-green-100 rounded-full flex items-center justify-center mb-4">
                <Check className="h-6 w-6 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold">Success!</h2>
              <p className="text-muted-foreground mt-2 mb-6">
                Your account has been created successfully
              </p>
              <Button onClick={() => router.push("/login")}>Sign In</Button>
            </div>
          )}
          {status === "error" && (
            <div className="text-center py-8">
              <div className="mx-auto h-12 w-12 bg-red-100 rounded-full flex items-center justify-center mb-4">
                <span className="text-red-600 font-bold text-xl">!</span>
              </div>
              <h2 className="text-2xl font-bold text-red-600">
                Something went wrong
              </h2>
              <p className="text-muted-foreground mt-2 mb-6">{error}</p>
              <Button variant="outline" onClick={() => router.push("/signup")}>
                Try Again
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
