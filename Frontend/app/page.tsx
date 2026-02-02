"use client";

import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  Check,
  Clock,
  DollarSign,
  FileSearch,
  Home,
  Mail,
  Phone,
  Search,
  Shield,
  UserCheck,
  Users,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { usePricing } from "@/contexts/pricing-context";

export default function HomePage() {
  const { selectedPlan, setSelectedPlan } = usePricing();

  const handlePlanClick = (planValue: string) => {
    setSelectedPlan(planValue as any);
  };

  return (
    <div className="flex flex-col min-h-screen">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
              <span className="text-white font-bold">LS</span>
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
              LeadSynergy
            </span>
          </Link>
          <div className="flex-1 flex items-center justify-center">
            <nav className="hidden md:flex gap-6">
              <button
                onClick={() => document.getElementById("features")?.scrollIntoView({ behavior: "smooth" })}
                className="text-sm font-medium hover:text-primary"
              >
                Features
              </button>
              <button
                onClick={() => document.getElementById("enrichment")?.scrollIntoView({ behavior: "smooth" })}
                className="text-sm font-medium hover:text-primary"
              >
                Enrichment
              </button>
              <button
                onClick={() => document.getElementById("compliance")?.scrollIntoView({ behavior: "smooth" })}
                className="text-sm font-medium hover:text-primary"
              >
                Compliance
              </button>
              <button
                onClick={() => document.getElementById("pricing")?.scrollIntoView({ behavior: "smooth" })}
                className="text-sm font-medium hover:text-primary"
              >
                Pricing
              </button>
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <ThemeToggle />
            <Link href="/login" className="text-sm font-medium hover:text-primary">
              Sign In
            </Link>
            <Button asChild>
              <Link href="/signup">Get Started</Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20" />
          <div className="container relative pt-20 pb-24 md:pt-32 md:pb-36">
            <div className="grid gap-8 md:grid-cols-2 items-center">
              <div className="flex flex-col gap-6">
                <div className="inline-flex items-center rounded-full border px-3 py-1 text-sm w-fit">
                  <span className="font-medium">Lead Organization & Enhancement Platform</span>
                </div>
                <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight">
                  Organize, Enrich & Convert{" "}
                  <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                    More Leads
                  </span>
                </h1>
                <p className="text-lg text-muted-foreground md:text-xl">
                  The complete platform for real estate professionals. Aggregate leads from
                  all referral sources, enrich contact data instantly, and stay compliant
                  with DNC regulations - all integrated with Follow Up Boss.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                  <Button size="lg" asChild>
                    <Link href="/signup">
                      Start Free Trial <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" asChild>
                    <Link href="#features">See How It Works</Link>
                  </Button>
                </div>
              </div>
              <div className="relative hidden md:block">
                <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 opacity-30 blur-xl" />
                <div className="relative rounded-xl border bg-background p-6 shadow-lg">
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center">
                        <Zap className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Lead Aggregation</h3>
                        <p className="text-sm text-muted-foreground">
                          Pull leads from 5+ referral platforms automatically
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center">
                        <Search className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Contact Enrichment</h3>
                        <p className="text-sm text-muted-foreground">
                          7 powerful search types to find missing contact info
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                        <Shield className="h-5 w-5 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">DNC Compliance</h3>
                        <p className="text-sm text-muted-foreground">
                          Check numbers against Do Not Call registry instantly
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center">
                        <Users className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">FUB Integration</h3>
                        <p className="text-sm text-muted-foreground">
                          Seamless Follow Up Boss embedded app and webhooks
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Lead Aggregation Features */}
        <section id="features" className="container py-16 md:py-24">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Lead Aggregation & Automation
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
              Centralize leads from all your referral sources and keep them synced with Follow Up Boss
            </p>
          </div>
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
            {aggregationFeatures.map((feature) => (
              <div
                key={feature.title}
                className="rounded-xl border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/50"
              >
                <div className="mb-4 h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
                  <feature.icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold">{feature.title}</h3>
                <p className="mt-2 text-muted-foreground">{feature.description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Lead Enrichment Features */}
        <section id="enrichment" className="bg-muted/40 py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 mb-4">
                <Search className="h-5 w-5 text-indigo-600" />
                <span className="text-sm font-medium text-indigo-600 uppercase tracking-wide">
                  Lead Enrichment
                </span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                7 Powerful Search Types
              </h2>
              <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
                Fill in missing contact information and verify data with our comprehensive enrichment tools
              </p>
            </div>
            <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
              {enrichmentFeatures.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-xl border bg-background p-6 shadow-sm transition-all hover:shadow-md hover:border-indigo-500/50"
                >
                  <div className="mb-4 h-12 w-12 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                    <feature.icon className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <h3 className="text-xl font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-muted-foreground">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* DNC Compliance Section */}
        <section id="compliance" className="bg-gradient-to-b from-green-50 to-white dark:from-green-950/20 dark:to-background py-16 md:py-24">
          <div className="container">
            <div className="text-center mb-12">
              <div className="inline-flex items-center gap-2 mb-4">
                <Shield className="h-6 w-6 text-green-600" />
                <span className="text-sm font-medium text-green-600 uppercase tracking-wide">
                  Compliance First
                </span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                Stay Compliant with DNC Regulations
              </h2>
              <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
                Avoid costly fines and protect your reputation with built-in Do Not Call
                registry checking and TCPA compliance tools.
              </p>
            </div>

            <div className="grid gap-8 md:grid-cols-3 max-w-5xl mx-auto">
              <Card className="border-green-200 dark:border-green-900">
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center mb-4">
                    <Check className="h-6 w-6 text-green-600 dark:text-green-400" />
                  </div>
                  <CardTitle>Instant DNC Checks</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground">
                  Check any phone number against the National Do Not Call Registry before
                  making contact. Get instant results with confidence scores.
                </CardContent>
              </Card>

              <Card className="border-yellow-200 dark:border-yellow-900">
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-yellow-100 dark:bg-yellow-900/50 flex items-center justify-center mb-4">
                    <Shield className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
                  </div>
                  <CardTitle>TCPA Guidelines</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground">
                  Built-in safeguards help you follow Telephone Consumer Protection Act
                  rules. Automatic flagging of potential compliance issues.
                </CardContent>
              </Card>

              <Card className="border-blue-200 dark:border-blue-900">
                <CardHeader>
                  <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-4">
                    <FileSearch className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                  <CardTitle>Audit Trail</CardTitle>
                </CardHeader>
                <CardContent className="text-muted-foreground">
                  Maintain complete records of all DNC checks for your protection.
                  Export compliance reports for your records or legal review.
                </CardContent>
              </Card>
            </div>

            <div className="mt-12 p-6 bg-muted/50 rounded-xl max-w-3xl mx-auto">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0">
                  <Shield className="h-8 w-8 text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-lg mb-2">
                    Potential Fines for DNC Violations
                  </h3>
                  <p className="text-muted-foreground text-sm">
                    The FTC can impose fines of up to <strong>$51,744 per call</strong> to
                    numbers on the Do Not Call Registry. Our platform helps you avoid these
                    costly mistakes by checking numbers before you dial.
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-8 text-center">
              <Button variant="outline" asChild>
                <Link href="/compliance">Learn More About Compliance</Link>
              </Button>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section id="pricing" className="container py-16 md:py-24">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Simple, Transparent Pricing
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
              Choose the plan that fits your needs. All plans include lead aggregation,
              enrichment credits, and DNC checking.
            </p>
          </div>

          <div className="grid gap-8 md:grid-cols-3 max-w-6xl mx-auto">
            {plans.map((plan) => (
              <Card
                key={plan.name}
                className={`relative cursor-pointer transition-all hover:border-primary ${
                  selectedPlan.toLowerCase() === plan.value
                    ? "border-primary shadow-lg"
                    : ""
                }`}
                onClick={() => handlePlanClick(plan.value)}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-0 right-0 flex justify-center">
                    <span className="bg-primary text-primary-foreground text-sm font-medium px-3 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}
                <CardHeader className={plan.popular ? "pt-8" : ""}>
                  <CardTitle className="text-2xl">{plan.name}</CardTitle>
                  <CardDescription>{plan.description}</CardDescription>
                  <div className="mt-4">
                    <span className="text-4xl font-bold">{plan.price}</span>
                    <span className="text-muted-foreground">/month</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-4">
                    {plan.features.map((feature) => (
                      <div key={feature} className="flex items-center gap-2">
                        <Check className="h-4 w-4 text-primary flex-shrink-0" />
                        <span className="text-sm">{feature}</span>
                      </div>
                    ))}
                  </div>
                  <Button
                    className="w-full mt-8"
                    variant={selectedPlan.toLowerCase() === plan.value ? "default" : "outline"}
                    asChild
                  >
                    <Link href={`/signup?plan=${plan.value}`}>
                      Get Started
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="mt-12 text-center">
            <p className="text-muted-foreground mb-4">
              Need more enrichment credits? Purchase add-on bundles anytime.
            </p>
            <Button variant="link" asChild>
              <Link href="/pricing">View Full Pricing Details</Link>
            </Button>
          </div>
        </section>

        {/* CTA Section */}
        <section className="bg-gradient-to-r from-blue-600 to-indigo-600">
          <div className="container py-16 md:py-24">
            <div className="flex flex-col items-center text-center">
              <h2 className="text-3xl font-bold tracking-tight text-white md:text-4xl">
                Ready to Organize & Enrich Your Leads?
              </h2>
              <p className="mt-4 text-lg text-white/80 max-w-2xl">
                Streamline your referral lead management and close more deals
                with automated status syncing and enriched data.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 mt-8">
                <Button size="lg" variant="secondary" asChild>
                  <Link href="/signup">
                    Start Free Trial <ArrowRight className="ml-2 h-4 w-4" />
                  </Link>
                </Button>
                <Button size="lg" variant="outline" className="bg-transparent text-white border-white hover:bg-white/10" asChild>
                  <Link href="/contact">Talk to Sales</Link>
                </Button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t bg-muted/40">
        <div className="container py-8 md:py-12">
          <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-4">
            <div>
              <div className="flex items-center gap-2">
                <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
                  <span className="text-white font-bold">LS</span>
                </div>
                <span className="text-xl font-bold">LeadSynergy</span>
              </div>
              <p className="mt-4 text-sm text-muted-foreground">
                The complete lead organization and enhancement platform for real
                estate professionals.
              </p>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link href="/#features" className="hover:text-foreground">
                    Lead Aggregation
                  </Link>
                </li>
                <li>
                  <Link href="/#enrichment" className="hover:text-foreground">
                    Lead Enrichment
                  </Link>
                </li>
                <li>
                  <Link href="/#compliance" className="hover:text-foreground">
                    DNC Compliance
                  </Link>
                </li>
                <li>
                  <Link href="/pricing" className="hover:text-foreground">
                    Pricing
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Support</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link href="/contact" className="hover:text-foreground">
                    Contact Us
                  </Link>
                </li>
                <li>
                  <Link href="/compliance" className="hover:text-foreground">
                    Compliance Guide
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link href="/privacy" className="hover:text-foreground">
                    Privacy Policy
                  </Link>
                </li>
                <li>
                  <Link href="/terms" className="hover:text-foreground">
                    Terms of Service
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-8 border-t pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-sm text-muted-foreground">
              &copy; {new Date().getFullYear()} LeadSynergy. All rights reserved.
            </p>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span>Integrated with Follow Up Boss</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

// Lead Aggregation Features
const aggregationFeatures = [
  {
    icon: Zap,
    title: "Multi-Platform Aggregation",
    description:
      "Pull leads from Homelight, Redfin, Referral Exchange, Agent Pronto, and more into one dashboard.",
  },
  {
    icon: ArrowRight,
    title: "FUB Auto-Sync",
    description:
      "Automatically push lead status updates to all connected referral platforms in real-time.",
  },
  {
    icon: Clock,
    title: "Real-Time Updates",
    description:
      "Instant synchronization ensures partners always have the latest lead information.",
  },
  {
    icon: DollarSign,
    title: "Commission Tracking",
    description:
      "Track referral fees and commissions across all your pay-per-close partnerships.",
  },
  {
    icon: Users,
    title: "Team Management",
    description:
      "Assign leads to team members with customizable round-robin and rule-based distribution.",
  },
  {
    icon: BarChart3,
    title: "Performance Analytics",
    description:
      "Track lead conversion rates, response times, and team performance metrics.",
  },
];

// Lead Enrichment Features
const enrichmentFeatures = [
  {
    icon: Search,
    title: "Contact Enrichment",
    description:
      "Enhance lead profiles with missing phone numbers, emails, and addresses.",
  },
  {
    icon: Phone,
    title: "Reverse Phone Lookup",
    description:
      "Find the person behind any phone number with comprehensive data.",
  },
  {
    icon: Mail,
    title: "Reverse Email Search",
    description:
      "Discover contact details and social profiles from an email address.",
  },
  {
    icon: Home,
    title: "Property Owner Search",
    description:
      "Find current property owners instantly from any US address.",
  },
  {
    icon: UserCheck,
    title: "Advanced Person Search",
    description:
      "Multi-field search to find detailed person records nationwide.",
  },
  {
    icon: FileSearch,
    title: "Background Checks",
    description:
      "Access criminal history and background information when needed.",
  },
];

// Pricing Plans — matches BASE_PLANS in lib/plans.ts
const plans = [
  {
    name: "Starter",
    value: "starter",
    price: "$29.99",
    description: "For agents starting with one referral platform",
    features: [
      "1 lead source connection",
      "Unlimited leads synced to FUB",
      "Bi-directional status updates",
      "Stage mapping",
      "FUB embedded app",
      "Email support",
    ],
  },
  {
    name: "Growth",
    value: "growth",
    price: "$69.99",
    description: "For agents managing multiple referral sources",
    popular: true,
    features: [
      "3 lead source connections",
      "Custom stage mapping",
      "Commission tracking",
      "FUB embedded app",
      "Priority support",
      "Unlimited team members",
    ],
  },
  {
    name: "Pro",
    value: "pro",
    price: "$119.99",
    description: "For teams using all major referral platforms",
    features: [
      "5 lead source connections",
      "Advanced stage mapping",
      "Advanced commission tracking",
      "Team analytics dashboard",
      "Priority support",
      "Unlimited team members",
    ],
  },
];
