"use client";

import {
  ArrowRight,
  BarChart3,
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

const aggregationFeatures = [
  {
    icon: Zap,
    title: "Multi-Platform Aggregation",
    description:
      "Pull leads from Homelight, Redfin, Referral Exchange, and more into one dashboard.",
  },
  {
    icon: ArrowRight,
    title: "FUB Auto-Sync",
    description:
      "Automatically push lead status updates to all connected referral platforms.",
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

export function FeatureGrid() {
  return (
    <section id="features" className="container py-16 md:py-24">
      <div className="text-center mb-12">
        <h2 className="text-3xl font-bold tracking-tight md:text-4xl">
          Everything You Need to Manage & Enhance Leads
        </h2>
        <p className="mt-4 text-lg text-muted-foreground max-w-3xl mx-auto">
          From lead aggregation to contact enrichment and compliance, our platform
          gives you the tools to organize and convert more leads.
        </p>
      </div>

      {/* Lead Aggregation Features */}
      <div className="mb-16">
        <div className="text-center mb-8">
          <h3 className="text-2xl font-bold">Lead Aggregation & Automation</h3>
          <p className="text-muted-foreground mt-2">
            Centralize leads from all your referral sources
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
              <h4 className="text-xl font-semibold">{feature.title}</h4>
              <p className="mt-2 text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Lead Enrichment Features */}
      <div>
        <div className="text-center mb-8">
          <h3 className="text-2xl font-bold">Lead Enrichment & Data</h3>
          <p className="text-muted-foreground mt-2">
            Fill in missing contact information with 7 powerful search types
          </p>
        </div>
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          {enrichmentFeatures.map((feature) => (
            <div
              key={feature.title}
              className="rounded-xl border bg-card p-6 shadow-sm transition-all hover:shadow-md hover:border-primary/50"
            >
              <div className="mb-4 h-12 w-12 rounded-lg bg-indigo-100 dark:bg-indigo-900/30 flex items-center justify-center">
                <feature.icon className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />
              </div>
              <h4 className="text-xl font-semibold">{feature.title}</h4>
              <p className="mt-2 text-muted-foreground">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
