"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { XCircle } from "lucide-react";

export default function CheckoutCancelPage() {
  const router = useRouter();

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardContent className="pt-6 text-center">
          <XCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold">Payment Not Completed</h2>
          <p className="text-muted-foreground mt-2 mb-4">
            Your payment was cancelled or did not complete successfully.
          </p>
          <p className="text-sm text-muted-foreground mb-6">
            Your information has been saved and you can try again.
          </p>
        </CardContent>
        <CardFooter className="flex gap-4 justify-center">
          <Button variant="outline" onClick={() => router.push("/signup")}>
            Start Over
          </Button>
          <Button onClick={() => router.push("/signup/billing")}>
            Try Again
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
