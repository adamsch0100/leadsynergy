"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, CreditCard, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import Link from "next/link";
import { usePricing } from "@/contexts/pricing-context";
import { completeSignup } from "@/app/auth/actions";
import SubscribeComponent from "@/components/stripe/SubscribeComponent";
import { createClient } from "@/lib/supabase/server";

type PlanType = "basic" | "professional" | "business";

// Function to handle payment
async function handlePayment(plan: PlanType, organizationId: string) {
  try {
    // Map plan to Stripe price ID
    const PLAN_PRICE_MAP = {
      basic: "price_1RLgO000AWGobp71BZUK4ZvN",
      professional: "price_1RLgPC00AWGobp71AkKUemR7",
      business: "price_1RLgQA00AWGobp71l87HOumZ",
    };

    const priceId = PLAN_PRICE_MAP[plan];

    // Call backend API
    const response = await fetch(process.env.BACKEND_URL!, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        priceId,
        organizationId,
      }),
    });

    const data = await response.json();

    // Check if successful
    if (data.ok && data.session_id) {
      // Redirect to Stripe checkout
      window.location.href = `https://checkout.stripe.com/c/pay/${data.session_id}`;
    } else {
      throw new Error(data.error || "Failed to create checkout session");
    }
  } catch (err) {
    console.error("Payment initiation failed:", err);
  }
}

export default function SignupBillingPage() {
  const router = useRouter();
  const { selectedPlan } = usePricing();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [isSuccess, setIsSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [accountSetupStatus, setAccountSetupStatus] = useState<
    "pending" | "success" | "error"
  >("pending");
  const [organizationId, setOrganizationId] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      // In a real app, this would process the payment with a payment provider
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Payment successful, now complete the signup process
      setIsSuccess(true);

      try {
        // Call the server action to complete the signup
        const result = await completeSignup();

        if (result.success) {
          setAccountSetupStatus("success");
        } else {
          console.error("Account setup failed:", result.error);
          setAccountSetupStatus("error");
          setError(
            `Paymen processed, but account setup failed: ${result.error}`
          );
        }
      } catch (error: any) {
        console.error("Account setup failed:", error.error);
        setAccountSetupStatus("error");
        setError(
          `Paymen processed, but account setup failed: ${
            error.error || "Unknown error"
          }`
        );
      }
    } catch (err) {
      setError("An error occurred while processing your payment");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFreeSignup = async () => {
    if (isSubmitting) return; // Prevent duplicate submissions
    setIsSubmitting(true);
    try {
      // Complete signup for free plan
      const result = await completeSignup();

      if (result.success) {
        setIsSuccess(true);
        setAccountSetupStatus("success");
      } else {
        setError(`Account setup failed: ${result.error}`);
        setAccountSetupStatus("error");
      }
    } catch (err: any) {
      setError(`Account setup failed: ${err.message || "Unknown error"}`);
      setAccountSetupStatus("error");
    } finally {
      // Don't set isSubmitting back to false on success to prevent multiple attempts
      // Only reset if there was an error
      if (!isSuccess) {
        setIsSubmitting(false);
      }
    }
  };

  const planDetails = {
    basic: {
      name: "Free Plan",
      price: "$0/month",
      description: "Perfect for small teams",
    },
    professional: {
      name: "Pro Plan",
      price: "$49/month",
      description: "For growing real estate teams",
    },
    business: {
      name: "Enterprise Plan",
      price: "Custom pricing",
      description: "For large brokerages",
    },
  };

  const currentPlan = planDetails[selectedPlan || "basic"];

  if (isSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
        <div className="w-full max-w-md">
          <Card className="border-none shadow-lg">
            <CardContent className="pt-6">
              <div className="mb-6 text-center">
                {accountSetupStatus === "pending" && (
                  <>
                    <div className="mx-auto h-12 w-12 rounded-full bg-blue-100 flex items-center justify-center mb-4">
                      {/* Add a loading spinner here */}
                      <div className="animate-spin h-6 w-6 border-2 border-blue-600 rounded-full border-t-transparent" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">
                      Setting up your account...
                    </h2>
                    <p className="text-muted-foreground">
                      Please wait while we finalize your account.
                    </p>
                  </>
                )}

                {accountSetupStatus === "success" && (
                  <>
                    <div className="mx-auto h-12 w-12 rounded-full bg-green-100 flex items-center justify-center mb-4">
                      <Check className="h-6 w-6 text-green-600" />
                    </div>
                    <h2 className="text-2xl font-bold mb-2">Setup Complete!</h2>
                    <p className="text-muted-foreground">
                      Your account has been created and your {currentPlan.name}{" "}
                      has been activated successfully.
                    </p>
                  </>
                )}

                {accountSetupStatus === "error" && (
                  <>
                    <div className="mx-auto h-12 w-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
                      <span className="h-6 w-6 text-red-600">!</span>
                    </div>
                    <h2 className="text-2xl font-bold mb-2 text-red-600">
                      Account Setup Failed
                    </h2>
                    <p className="text-muted-foreground mb-4">
                      {error || "There was a problem setting up your account."}
                    </p>
                    <Button
                      variant="outline"
                      className="mb-4"
                      onClick={() => setIsSuccess(false)}
                    >
                      Try Again
                    </Button>
                  </>
                )}
              </div>

              {accountSetupStatus === "success" && (
                <Button className="w-full" asChild>
                  <Link href="/login">Sign In to Your Account</Link>
                </Button>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="w-full max-w-md">
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
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">
              Complete Your Subscription
            </CardTitle>
            <CardDescription className="text-center">
              Enter your payment details to activate your {currentPlan.name}
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
              <p className="text-sm text-muted-foreground">
                {currentPlan.description}
              </p>
            </div>

            {selectedPlan !== "basic" && (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  {/* <Label htmlFor="cardNumber">Card Number</Label>
                  <div className="relative">
                    <CreditCard className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                    <Input
                      id="cardNumber"
                      placeholder="4242 4242 4242 4242"
                      className="pl-10"
                      required
                    />
                  </div> */}
                  <SubscribeComponent
                    priceId={
                      selectedPlan === "professional"
                        ? "price_basicPlanIdFromStripe"
                        : "price_enterprisePlanIdFromStripe"
                    }
                    price={currentPlan.price}
                    description={currentPlan.name}
                    organizationId="pending"
                  />
                  <p className="text-sm text-center text-muted-foreground">
                    You'll be taken to a secure checkout page to complete your
                    payment
                  </p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="expiry">Expiry Date</Label>
                    <Input id="expiry" placeholder="MM/YY" required />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="cvc">CVC</Label>
                    <Input id="cvc" placeholder="123" required />
                  </div>
                </div>

                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? "Processing..." : `Pay ${currentPlan.price}`}
                </Button>
              </form>
            )}

            {selectedPlan === "basic" && (
              <Button
                className="w-full"
                onClick={handleFreeSignup}
                disabled={isLoading}
              >
                {isLoading ? "Processing..." : "Activate Free Plan"}
              </Button>
            )}
          </CardContent>
          <CardFooter className="justify-center">
            <p className="text-center text-sm text-muted-foreground">
              Your payment is secure and encrypted
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
