"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Building2,
  Eye,
  EyeOff,
  Lock,
  Mail,
  User,
  ArrowLeft,
  Key,
  Check,
  Layers,
} from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { initiateSignup } from "../auth/actions";
import {
  BasePlanId,
  BASE_PLANS,
  BASE_PLAN_ORDER,
} from "@/lib/plans";

import { loadStripe } from "@stripe/stripe-js";

interface SignUpForm {
  fullName: string;
  email: string;
  password: string;
  confirmPassword: string;
  organizationName: string;
  fubApiKey?: string;
  basePlan: BasePlanId;
}

// Stripe price IDs for base platform plans
const BASE_PLAN_PRICE_MAP: Record<BasePlanId, string> = {
  starter: process.env.NEXT_PUBLIC_STRIPE_PRICE_STARTER || "price_starter",
  growth: process.env.NEXT_PUBLIC_STRIPE_PRICE_GROWTH || "price_growth",
  pro: process.env.NEXT_PUBLIC_STRIPE_PRICE_PRO || "price_pro",
  enterprise: process.env.NEXT_PUBLIC_STRIPE_PRICE_ENTERPRISE || "price_enterprise",
};

// Load Stripe outside of component rendering to avoid recreating the Stripe object
const stripePromise = loadStripe(
  process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!
);

async function initiateStripeCheckout(
  organizationId: string,
  basePlan: BasePlanId,
  customerEmail: string
) {
  try {
    const priceId = BASE_PLAN_PRICE_MAP[basePlan];
    if (!priceId) {
      throw new Error("Invalid plan or no Stripe price configured");
    }

    // Call backend API
    const response = await fetch("/api/checkout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        priceId,
        organizationId,
        customerEmail,
        plan: basePlan,
      }),
    });

    const data = await response.json();

    if (data.ok && data.session_id) {
      // Redirect to Stripe checkout
      const stripe = await stripePromise;

      if (!stripe) throw new Error("Failed to load stripe");

      // Redirect to checkout using Stripe's redirect
      const result = await stripe.redirectToCheckout({
        sessionId: data.session_id,
      });

      if (result.error) throw result.error;
      return true;
    } else {
      throw new Error(data.error || "Failed to create checkout session");
    }
  } catch (error) {
    console.error("Payment initiation failed:", error);
    return false;
  }
}

// Filter plans for signup - exclude enterprise (requires contact sales)
const signupPlans = BASE_PLAN_ORDER.filter(id => id !== "enterprise").map(id => BASE_PLANS[id]);

export default function SignUpPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [formData, setFormData] = useState<SignUpForm>({
    fullName: "",
    email: "",
    password: "",
    confirmPassword: "",
    organizationName: "",
    fubApiKey: "",
    basePlan: "growth", // Default to most popular
  });

  const handlePlanSelect = (planValue: BasePlanId) => {
    setFormData((prev) => ({ ...prev, basePlan: planValue }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    // Basic validation
    if (
      !formData.fullName ||
      !formData.email ||
      !formData.password ||
      !formData.confirmPassword ||
      !formData.organizationName
    ) {
      setError("Please fill in all fields");
      setIsLoading(false);
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError("Passwords do not match");
      setIsLoading(false);
      return;
    }

    try {
      const data = new FormData();
      data.append("fullName", formData.fullName);
      data.append("email", formData.email);
      data.append("password", formData.password);
      data.append("organizationName", formData.organizationName);
      if (formData.fubApiKey) {
        data.append("fubApiKey", formData.fubApiKey);
      }
      data.append("plan", formData.basePlan);

      // Call the server action to create the account
      const result = await initiateSignup(data);

      if (result.success && result.organizationId) {
        // All plans go to Stripe checkout
        await initiateStripeCheckout(result.organizationId, formData.basePlan, formData.email);
      } else {
        setError(result.error || "Failed to initiate signup");
      }
    } catch (err: any) {
      setError(err.error || "An error occurred during registration");
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="w-full max-w-md">
        <div className="mb-8">
          <Button
            variant="ghost"
            onClick={() => router.push("/login")}
            className="flex items-center gap-2 mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Sign In
          </Button>
          <Link href="/" className="flex items-center gap-2 justify-center">
            <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold">LS</span>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              LeadSynergy
            </span>
          </Link>
        </div>

        <Card className="border-none shadow-lg">
          <CardHeader className="space-y-1">
            <CardTitle className="text-2xl font-bold text-center">
              Create an Account
            </CardTitle>
            <CardDescription className="text-center">
              Start syncing your referral leads to Follow Up Boss
            </CardDescription>
          </CardHeader>
          <CardContent>
            {error && (
              <Alert variant="destructive" className="mb-4">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="fullName">Full Name</Label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="fullName"
                    name="fullName"
                    placeholder="John Doe"
                    className="pl-10"
                    value={formData.fullName}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    placeholder="you@example.com"
                    className="pl-10"
                    value={formData.email}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="password"
                    name="password"
                    type={showPassword ? "text" : "password"}
                    className="pl-10 pr-10"
                    value={formData.password}
                    onChange={handleChange}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute right-0 top-0 h-full px-3 py-2 hover:bg-transparent"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-5 w-5 text-muted-foreground" />
                    ) : (
                      <Eye className="h-5 w-5 text-muted-foreground" />
                    )}
                    <span className="sr-only">
                      {showPassword ? "Hide password" : "Show password"}
                    </span>
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="confirmPassword">Confirm Password</Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="confirmPassword"
                    name="confirmPassword"
                    type={showPassword ? "text" : "password"}
                    className="pl-10"
                    value={formData.confirmPassword}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="organizationName">Organization Name</Label>
                <div className="relative">
                  <Building2 className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="organizationName"
                    name="organizationName"
                    placeholder="Your Company Name"
                    className="pl-10"
                    value={formData.organizationName}
                    onChange={handleChange}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="fubApiKey">Follow Up Boss API Key (Optional)</Label>
                <div className="relative">
                  <Key className="absolute left-3 top-2.5 h-5 w-5 text-muted-foreground" />
                  <Input
                    id="fubApiKey"
                    name="fubApiKey"
                    type="password"
                    placeholder="fka_..."
                    className="pl-10"
                    value={formData.fubApiKey}
                    onChange={handleChange}
                  />
                </div>
                <p className="text-xs text-muted-foreground">
                  Enter your FUB API key to automatically import your leads during signup.
                  You can add this later in settings if you prefer.
                </p>
              </div>

              <div className="space-y-2">
                <Label className="flex items-center gap-2">
                  <Layers className="h-4 w-4" />
                  Select Your Platform Plan
                </Label>
                <p className="text-xs text-muted-foreground mb-3">
                  Choose how many lead sources you want to sync. All plans include unlimited team members.
                </p>
                <div className="grid gap-3">
                  {signupPlans.map((plan) => (
                    <div
                      key={plan.id}
                      className={`relative rounded-lg border p-4 cursor-pointer transition-all hover:border-primary ${
                        formData.basePlan === plan.id
                          ? "bg-primary/5 border-primary ring-1 ring-primary"
                          : ""
                      }`}
                      onClick={() => handlePlanSelect(plan.id)}
                    >
                      {plan.popular && (
                        <Badge className="absolute -top-2 right-4" variant="default">
                          Most Popular
                        </Badge>
                      )}
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          {formData.basePlan === plan.id && (
                            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-primary">
                              <Check className="h-3 w-3 text-primary-foreground" />
                            </div>
                          )}
                          <Label className="text-base font-semibold cursor-pointer">
                            {plan.name}
                          </Label>
                        </div>
                        <span className="text-lg font-bold">
                          {plan.priceDisplay}
                          <span className="text-sm font-normal text-muted-foreground">
                            {plan.interval ? `/${plan.interval.replace("per ", "")}` : ""}
                          </span>
                        </span>
                      </div>
                      <p className="text-sm text-muted-foreground mb-2">
                        {plan.description}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-2 py-1 rounded font-medium">
                          {plan.platforms} {plan.platforms === 1 ? "Platform" : "Platforms"}
                        </span>
                        <span className="text-xs bg-muted px-2 py-1 rounded">
                          Unlimited team members
                        </span>
                        <span className="text-xs bg-muted px-2 py-1 rounded">
                          Bi-directional sync
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-muted-foreground text-center mt-2">
                  Need lead enrichment? Add an Enhancement subscription after signup.{" "}
                  <Link href="/pricing" className="text-primary hover:underline">View all options</Link>
                </p>
              </div>

              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? "Creating Account..." : "Create Account"}
              </Button>
            </form>
          </CardContent>
          <CardFooter>
            <p className="text-center text-sm text-muted-foreground w-full">
              Already have an account?{" "}
              <Link href="/login" className="text-primary hover:underline">
                Sign in
              </Link>
            </p>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
