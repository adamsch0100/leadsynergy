"use client";

import Link from "next/link";
import {
  ArrowRight,
  ArrowLeftRight,
  BarChart3,
  Bot,
  Brain,
  Check,
  Clock,
  DollarSign,
  FileSearch,
  Globe,
  Home,
  Layers,
  Mail,
  MessageSquare,
  Phone,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Target,
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
                onClick={() => document.getElementById("ai-agent")?.scrollIntoView({ behavior: "smooth" })}
                className="text-sm font-medium hover:text-primary"
              >
                AI Agent
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
                <div className="inline-flex items-center rounded-full border px-3 py-1 text-sm w-fit gap-2">
                  <Sparkles className="h-3.5 w-3.5 text-blue-600" />
                  <span className="font-medium">AI-Powered Lead Management for Real Estate</span>
                </div>
                <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight">
                  Your AI Agent That{" "}
                  <span className="bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                    Never Sleeps
                  </span>
                </h1>
                <p className="text-lg text-muted-foreground md:text-xl">
                  Aggregate leads from every referral source, enrich contacts instantly,
                  and let your AI agent engage new leads in under 60 seconds &mdash; 24/7.
                  All integrated with Follow Up Boss.
                </p>
                <div className="flex flex-col sm:flex-row gap-4">
                  <Button size="lg" asChild>
                    <Link href="/signup">
                      Start Free Trial <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                  <Button size="lg" variant="outline" asChild>
                    <Link href="#ai-agent">See the AI Agent</Link>
                  </Button>
                </div>
                <div className="flex items-center gap-6 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Check className="h-4 w-4 text-green-600" />
                    <span>No credit card required</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Check className="h-4 w-4 text-green-600" />
                    <span>Works with Follow Up Boss</span>
                  </div>
                </div>
              </div>
              <div className="relative hidden md:block">
                <div className="absolute -inset-0.5 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-500 opacity-30 blur-xl" />
                <div className="relative rounded-xl border bg-background p-6 shadow-lg">
                  <div className="space-y-4">
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center">
                        <Bot className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">AI Lead Agent</h3>
                        <p className="text-sm text-muted-foreground">
                          Instant outreach + 17-step follow-up sequences
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-indigo-100 dark:bg-indigo-900/50 flex items-center justify-center">
                        <Zap className="h-5 w-5 text-indigo-600 dark:text-indigo-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Lead Aggregation</h3>
                        <p className="text-sm text-muted-foreground">
                          Pull leads from 5+ referral platforms automatically
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900/50 flex items-center justify-center">
                        <Search className="h-5 w-5 text-green-600 dark:text-green-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">Contact Enrichment</h3>
                        <p className="text-sm text-muted-foreground">
                          7 powerful search types to find missing contact info
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="h-10 w-10 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center">
                        <Shield className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                      </div>
                      <div>
                        <h3 className="font-medium">DNC Compliance</h3>
                        <p className="text-sm text-muted-foreground">
                          Check numbers against Do Not Call registry instantly
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Speed-to-Lead Stats Banner */}
        <section className="border-y bg-muted/30">
          <div className="container py-10">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
              <div>
                <div className="text-3xl md:text-4xl font-bold text-primary">&lt;60s</div>
                <p className="text-sm text-muted-foreground mt-1">Average response time</p>
              </div>
              <div>
                <div className="text-3xl md:text-4xl font-bold text-primary">21x</div>
                <p className="text-sm text-muted-foreground mt-1">More likely to qualify</p>
              </div>
              <div>
                <div className="text-3xl md:text-4xl font-bold text-primary">24/7</div>
                <p className="text-sm text-muted-foreground mt-1">Always-on engagement</p>
              </div>
              <div>
                <div className="text-3xl md:text-4xl font-bold text-primary">17</div>
                <p className="text-sm text-muted-foreground mt-1">Automated follow-up steps</p>
              </div>
            </div>
          </div>
        </section>

        {/* AI Agent Section */}
        <section id="ai-agent" className="relative py-16 md:py-24 overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-b from-violet-50/50 to-blue-50/50 dark:from-violet-950/10 dark:to-blue-950/10" />
          <div className="container relative">
            <div className="text-center mb-14">
              <div className="inline-flex items-center gap-2 mb-4">
                <Bot className="h-5 w-5 text-violet-600" />
                <span className="text-sm font-medium text-violet-600 uppercase tracking-wide">
                  AI Lead Agent
                </span>
              </div>
              <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
                Your Tireless AI Sales Assistant
              </h2>
              <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
                The moment a new lead comes in, your AI agent sends a personalized
                SMS &mdash; then runs an intelligent 17-step follow-up sequence of texts
                and emails over weeks, all while you focus on closing deals.
              </p>
            </div>

            {/* AI Feature Grid */}
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 max-w-6xl mx-auto">
              {aiFeatures.map((feature) => (
                <div
                  key={feature.title}
                  className="rounded-xl border bg-background p-6 shadow-sm transition-all hover:shadow-md hover:border-violet-500/50"
                >
                  <div className="mb-4 h-12 w-12 rounded-lg bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center">
                    <feature.icon className="h-6 w-6 text-violet-600 dark:text-violet-400" />
                  </div>
                  <h3 className="text-lg font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm text-muted-foreground">{feature.description}</p>
                </div>
              ))}
            </div>

            {/* AI How It Works */}
            <div className="mt-16 max-w-5xl mx-auto">
              <h3 className="text-2xl font-bold text-center mb-10">How the AI Agent Works</h3>
              <div className="grid md:grid-cols-4 gap-6">
                {aiSteps.map((step, index) => (
                  <div key={step.title} className="relative text-center">
                    {index < aiSteps.length - 1 && (
                      <div className="hidden md:block absolute top-8 left-[60%] w-[80%] border-t-2 border-dashed border-violet-300 dark:border-violet-700" />
                    )}
                    <div className="inline-flex h-16 w-16 items-center justify-center rounded-full bg-violet-100 dark:bg-violet-900/40 mb-4 relative">
                      <step.icon className="h-7 w-7 text-violet-600 dark:text-violet-400" />
                      <span className="absolute -top-1 -right-1 h-6 w-6 rounded-full bg-violet-600 text-white text-xs font-bold flex items-center justify-center">
                        {index + 1}
                      </span>
                    </div>
                    <h4 className="font-semibold mb-1">{step.title}</h4>
                    <p className="text-sm text-muted-foreground">{step.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* AI Differentiator Callout */}
            <div className="mt-14 max-w-4xl mx-auto rounded-xl border-2 border-violet-200 dark:border-violet-800 bg-violet-50/50 dark:bg-violet-950/20 p-8">
              <div className="flex flex-col md:flex-row items-start gap-6">
                <div className="flex-shrink-0">
                  <div className="h-14 w-14 rounded-full bg-violet-100 dark:bg-violet-900/50 flex items-center justify-center">
                    <Brain className="h-7 w-7 text-violet-600 dark:text-violet-400" />
                  </div>
                </div>
                <div>
                  <h3 className="text-xl font-bold mb-2">Not Just Templates &mdash; Real AI Conversations</h3>
                  <p className="text-muted-foreground">
                    Unlike drip campaigns that send the same canned message to everyone,
                    LeadSynergy&apos;s AI agent analyzes each lead&apos;s context &mdash; their inquiry,
                    property interests, location, and stage &mdash; to craft genuinely personalized
                    messages. It adapts tone and content for each follow-up, knows when to push
                    and when to back off, and automatically hands off to your team when a lead
                    is ready to talk.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Lead Sync & Aggregation Section */}
        <section id="features" className="container py-16 md:py-24">
          <div className="text-center mb-14">
            <div className="inline-flex items-center gap-2 mb-4">
              <RefreshCw className="h-5 w-5 text-blue-600" />
              <span className="text-sm font-medium text-blue-600 uppercase tracking-wide">
                Bi-Directional Sync
              </span>
            </div>
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
              Every Referral Platform. One Dashboard. Always in Sync.
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
              LeadSynergy automatically pulls new leads from your referral platforms into
              Follow Up Boss, then pushes status updates back &mdash; so your partners always
              see the latest and you never miss a lead.
            </p>
          </div>

          {/* Visual Sync Flow */}
          <div className="max-w-5xl mx-auto mb-16">
            <div className="grid md:grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-4 md:gap-2">
              {/* Lead Sources */}
              <div className="rounded-xl border-2 border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-950/20 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Globe className="h-5 w-5 text-blue-600" />
                  <h3 className="font-semibold text-blue-700 dark:text-blue-400">Referral Platforms</h3>
                </div>
                <div className="space-y-2.5">
                  {["Pay-at-close platforms", "Referral networks", "Zillow-type portals", "Broker referral systems", "And more..."].map((source) => (
                    <div key={source} className="flex items-center gap-2 text-sm">
                      <div className="h-2 w-2 rounded-full bg-blue-500" />
                      <span>{source}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Arrow */}
              <div className="hidden md:flex flex-col items-center gap-1">
                <ArrowLeftRight className="h-6 w-6 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground font-medium">AUTO SYNC</span>
              </div>

              {/* LeadSynergy Hub */}
              <div className="rounded-xl border-2 border-primary bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/30 dark:to-indigo-950/30 p-6 shadow-md">
                <div className="flex items-center gap-3 mb-4">
                  <div className="h-8 w-8 rounded-md bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
                    <span className="text-white font-bold text-xs">LS</span>
                  </div>
                  <h3 className="font-semibold">LeadSynergy</h3>
                </div>
                <div className="space-y-2.5 text-sm">
                  <div className="flex items-center gap-2">
                    <Layers className="h-3.5 w-3.5 text-primary" />
                    <span>Aggregation</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Bot className="h-3.5 w-3.5 text-primary" />
                    <span>AI Agent</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Search className="h-3.5 w-3.5 text-primary" />
                    <span>Enrichment</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Shield className="h-3.5 w-3.5 text-primary" />
                    <span>DNC Compliance</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <BarChart3 className="h-3.5 w-3.5 text-primary" />
                    <span>Analytics</span>
                  </div>
                </div>
              </div>

              {/* Arrow */}
              <div className="hidden md:flex flex-col items-center gap-1">
                <ArrowLeftRight className="h-6 w-6 text-muted-foreground" />
                <span className="text-[10px] text-muted-foreground font-medium">AUTO SYNC</span>
              </div>

              {/* FUB */}
              <div className="rounded-xl border-2 border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/20 p-6">
                <div className="flex items-center gap-3 mb-4">
                  <Users className="h-5 w-5 text-emerald-600" />
                  <h3 className="font-semibold text-emerald-700 dark:text-emerald-400">Follow Up Boss</h3>
                </div>
                <div className="space-y-2.5 text-sm">
                  <div className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Leads auto-created</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Stages mapped</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Notes &amp; tags synced</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Embedded app inside FUB</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Check className="h-3.5 w-3.5 text-emerald-600" />
                    <span>Status updates pushed back</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sync Feature Details */}
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3 max-w-6xl mx-auto">
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
              enrichment credits, DNC checking, and AI agent access.
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
                Stop Losing Leads to Slow Response Times
              </h2>
              <p className="mt-4 text-lg text-white/80 max-w-2xl">
                Every minute you wait to respond, the chance of qualifying a lead drops
                dramatically. Let your AI agent respond instantly while you focus on
                closing deals.
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
                AI-powered lead management and follow-up platform for real
                estate professionals.
              </p>
            </div>

            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li>
                  <Link href="/#ai-agent" className="hover:text-foreground">
                    AI Agent
                  </Link>
                </li>
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

// AI Agent Features
const aiFeatures = [
  {
    icon: Zap,
    title: "Instant Lead Response",
    description:
      "New lead comes in? Your AI agent sends a personalized SMS within seconds. Research shows responding in under 5 minutes makes you 21x more likely to qualify a lead.",
  },
  {
    icon: MessageSquare,
    title: "17-Step Follow-Up Sequences",
    description:
      "Automated SMS and email sequences over weeks that adapt to each lead. No more leads slipping through the cracks because you forgot to follow up.",
  },
  {
    icon: Brain,
    title: "Contextual AI Messages",
    description:
      "Not canned templates. The AI analyzes each lead's inquiry, property interests, and stage to craft personalized messages that feel human.",
  },
  {
    icon: Target,
    title: "Smart Lead Qualification",
    description:
      "The AI scores and qualifies leads based on their responses and engagement. When they're ready, it hands off to your team with full context.",
  },
  {
    icon: Clock,
    title: "TCPA-Compliant Scheduling",
    description:
      "Messages are only sent during legal hours in the lead's timezone. Automatic cooldown periods prevent message clustering.",
  },
  {
    icon: Sparkles,
    title: "Customizable Personality",
    description:
      "Set your agent's tone — friendly casual, professional, enthusiastic, or consultative. It represents your brand, your way.",
  },
];

// AI How It Works Steps
const aiSteps = [
  {
    icon: Zap,
    title: "Lead Arrives",
    description: "New lead synced from any referral platform or FUB",
  },
  {
    icon: Bot,
    title: "AI Engages",
    description: "Personalized SMS sent within seconds of arrival",
  },
  {
    icon: MessageSquare,
    title: "Follow-Up",
    description: "17-step sequence of texts and emails over weeks",
  },
  {
    icon: UserCheck,
    title: "Handoff",
    description: "Qualified lead handed to your team, ready to close",
  },
];

// Lead Aggregation Features
const aggregationFeatures = [
  {
    icon: Zap,
    title: "5+ Platform Aggregation",
    description:
      "Automatically pull new leads from all your referral and pay-at-close platforms into one place — no manual entry, no missed leads.",
  },
  {
    icon: RefreshCw,
    title: "Bi-Directional Status Sync",
    description:
      "Update a lead stage in FUB and it pushes back to the referral platform. Update it on the platform and it syncs to FUB. Always in sync, both directions.",
  },
  {
    icon: Layers,
    title: "Stage Mapping",
    description:
      "Map each platform's unique statuses to your FUB stages. Each referral source has different terminology — you define how they translate.",
  },
  {
    icon: DollarSign,
    title: "Commission Tracking",
    description:
      "Track referral fees and commissions across all your pay-per-close partnerships. Know exactly what you owe and what you're earning.",
  },
  {
    icon: Users,
    title: "Team Management",
    description:
      "Assign leads to team members with customizable round-robin and rule-based distribution. Everyone sees their own pipeline.",
  },
  {
    icon: BarChart3,
    title: "Performance Analytics",
    description:
      "See which referral sources convert best, track response times, and measure team performance across all platforms.",
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
      "AI agent with SMS & email follow-ups",
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
      "AI agent with SMS & email follow-ups",
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
      "AI agent with SMS & email follow-ups",
      "Advanced stage mapping",
      "Advanced commission tracking",
      "Team analytics dashboard",
      "Priority support",
      "Unlimited team members",
    ],
  },
];
