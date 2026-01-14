"use client";

import Link from "next/link";
import { Check, X, ArrowLeft, Sparkles, Shield, Phone, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useRouter } from "next/navigation";
import { usePricing } from "@/contexts/pricing-context";
import { PLANS, PLAN_ORDER, CREDIT_PACKAGES, PlanId, ADDITIONAL_TEAM_MEMBER_PRICE } from "@/lib/plans";

export default function PricingPage() {
  const router = useRouter();
  const { selectedPlan, setSelectedPlan } = usePricing();

  const handlePlanClick = (planValue: PlanId) => {
    setSelectedPlan(planValue as any);
  };

  // Filter credit packages for display (group by type)
  const enhancementPackages = CREDIT_PACKAGES.filter(p => p.type === "enhancement");
  const criminalPackages = CREDIT_PACKAGES.filter(p => p.type === "criminal");
  const dncPackages = CREDIT_PACKAGES.filter(p => p.type === "dnc");

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
      <div className="container py-8 md:py-12">
        <div className="flex justify-between items-center mb-8">
          <Button
            variant="ghost"
            onClick={() => router.back()}
            className="flex items-center gap-2"
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </Button>
        </div>
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold tracking-tight mb-3">
            LeadSynergy Pricing
          </h1>
          <p className="text-lg text-muted-foreground max-w-3xl mx-auto">
            Manage your referral leads across all platforms and enrich them with powerful data.
            One subscription covers both lead management and enrichment.
          </p>
        </div>

        {/* Two Value Props */}
        <div className="grid gap-6 md:grid-cols-2 max-w-4xl mx-auto mb-12">
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900 flex items-center justify-center">
                <RefreshCw className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <h3 className="font-bold text-lg">Lead Management</h3>
                <p className="text-sm text-muted-foreground">Included in all plans</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-green-500" />
                Sync leads from Homelight, Redfin, Referral Exchange, Agent Pronto, My Agent Finder
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-green-500" />
                Automatic lead import to Follow Up Boss
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-green-500" />
                Update lead status back to referral platforms
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-green-500" />
                Track referral fees and commissions
              </li>
            </ul>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border shadow-sm">
            <div className="flex items-center gap-3 mb-4">
              <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900 flex items-center justify-center">
                <Sparkles className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <h3 className="font-bold text-lg">Lead Enrichment</h3>
                <p className="text-sm text-muted-foreground">Credits included per plan</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm">
              <li className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-blue-500" />
                <span><strong>Enhancement:</strong> Find missing phone/email, address history</span>
              </li>
              <li className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-red-500" />
                <span><strong>Criminal:</strong> Background checks (FCRA compliant)</span>
              </li>
              <li className="flex items-center gap-2">
                <Phone className="h-4 w-4 text-green-500" />
                <span><strong>DNC:</strong> Do Not Call registry verification</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="h-4 w-4 text-green-500" />
                Auto-enhance new leads as they arrive
              </li>
            </ul>
          </div>
        </div>

        {/* Pricing Cards */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4 max-w-7xl mx-auto">
          {PLAN_ORDER.map((planId) => {
            const plan = PLANS[planId];
            return (
              <Card
                key={plan.id}
                className={`relative cursor-pointer transition-all hover:border-primary ${
                  selectedPlan?.toLowerCase() === plan.id
                    ? "border-primary shadow-lg"
                    : ""
                } ${plan.popular ? "ring-2 ring-primary" : ""}`}
                onClick={() => handlePlanClick(plan.id)}
              >
                {plan.popular && (
                  <div className="absolute -top-4 left-0 right-0 flex justify-center">
                    <span className="bg-primary text-primary-foreground text-sm font-medium px-3 py-1 rounded-full">
                      Most Popular
                    </span>
                  </div>
                )}
                <CardHeader className={plan.popular ? "pt-8" : ""}>
                  <CardTitle className="text-xl">{plan.name}</CardTitle>
                  <CardDescription className="min-h-[40px]">{plan.description}</CardDescription>
                  <div className="mt-4">
                    <span className="text-3xl font-bold">{plan.priceDisplay}</span>
                    {plan.interval && <span className="text-muted-foreground">/{plan.interval}</span>}
                  </div>
                </CardHeader>
                <CardContent>
                  {/* Highlights */}
                  <div className="bg-primary/5 rounded-lg p-3 mb-4">
                    {plan.highlights.map((highlight) => (
                      <div key={highlight} className="flex items-center gap-2 text-sm">
                        <Check className="h-3 w-3 text-primary" />
                        <span className="font-medium">{highlight}</span>
                      </div>
                    ))}
                  </div>

                  {/* Credit Summary */}
                  <div className="bg-muted/50 rounded-lg p-3 mb-4">
                    <p className="text-xs font-medium text-muted-foreground mb-2">Monthly Enrichment Credits:</p>
                    <div className="grid grid-cols-3 gap-2 text-center text-xs">
                      <div>
                        <p className="font-bold text-blue-600">{plan.credits.enhancement}</p>
                        <p className="text-muted-foreground">Enhance</p>
                      </div>
                      <div>
                        <p className="font-bold text-red-600">{plan.credits.criminal}</p>
                        <p className="text-muted-foreground">Criminal</p>
                      </div>
                      <div>
                        <p className="font-bold text-green-600">{plan.credits.dnc}</p>
                        <p className="text-muted-foreground">DNC</p>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2 max-h-[200px] overflow-y-auto">
                    {plan.features.map((feature) => (
                      <div key={feature} className="flex items-start gap-2">
                        <Check className="h-4 w-4 text-primary flex-shrink-0 mt-0.5" />
                        <span className="text-xs">{feature}</span>
                      </div>
                    ))}
                  </div>
                  <Button
                    className="w-full mt-6"
                    variant={
                      selectedPlan?.toLowerCase() === plan.id
                        ? "default"
                        : "outline"
                    }
                    asChild
                  >
                    <Link
                      href={
                        plan.id === "enterprise"
                          ? "/contact"
                          : `/signup?plan=${plan.id}`
                      }
                    >
                      {plan.id === "enterprise"
                        ? "Contact Sales"
                        : "Get Started"}
                    </Link>
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Add-ons Section - Credits Only */}
        <section className="mt-16">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold">Credit Add-ons</h2>
            <p className="text-muted-foreground mt-2">
              Need more credits? Purchase additional packs anytime. Credits don't expire.
            </p>
          </div>

          <div className="max-w-5xl mx-auto">
            {/* Enhancement Credits */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-500" />
                Enhancement Credits
              </h3>
              <div className="grid gap-4 md:grid-cols-3">
                {enhancementPackages.map((pkg) => (
                  <div
                    key={pkg.id}
                    className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 border"
                  >
                    <h4 className="font-medium text-sm">{pkg.name}</h4>
                    <p className="text-lg font-bold text-primary">{pkg.priceDisplay}</p>
                    <p className="text-xs text-muted-foreground">{pkg.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Criminal Searches */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Shield className="h-5 w-5 text-red-500" />
                Criminal Searches
              </h3>
              <div className="grid gap-4 md:grid-cols-2">
                {criminalPackages.map((pkg) => (
                  <div
                    key={pkg.id}
                    className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 border"
                  >
                    <h4 className="font-medium text-sm">{pkg.name}</h4>
                    <p className="text-lg font-bold text-primary">{pkg.priceDisplay}</p>
                    <p className="text-xs text-muted-foreground">{pkg.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* DNC Checks */}
            <div className="mb-8">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Phone className="h-5 w-5 text-green-500" />
                DNC Checks
              </h3>
              <div className="grid gap-4 md:grid-cols-2">
                {dncPackages.map((pkg) => (
                  <div
                    key={pkg.id}
                    className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4 border"
                  >
                    <h4 className="font-medium text-sm">{pkg.name}</h4>
                    <p className="text-lg font-bold text-primary">{pkg.priceDisplay}</p>
                    <p className="text-xs text-muted-foreground">{pkg.description}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Additional Team Members */}
            <div className="bg-muted/30 rounded-lg p-6 border">
              <h3 className="text-lg font-semibold mb-2">Additional Team Members</h3>
              <p className="text-muted-foreground text-sm mb-2">
                Need more seats than your plan includes? Add team members for <strong>${ADDITIONAL_TEAM_MEMBER_PRICE}/month</strong> each.
              </p>
              <p className="text-xs text-muted-foreground">
                Available for Team and Brokerage plans. Enterprise plans include unlimited team members.
              </p>
            </div>
          </div>
        </section>

        {/* Comparison Table */}
        <section className="mt-20">
          <div className="text-center mb-12">
            <h2 className="text-3xl font-bold tracking-tight mb-4">
              Compare Plans
            </h2>
            <p className="text-lg text-muted-foreground">
              Full feature comparison across all plans
            </p>
          </div>

          <div className="w-full overflow-auto">
            <table className="w-full border-collapse bg-white dark:bg-gray-800 rounded-lg overflow-hidden">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-4 px-4 font-semibold">Feature</th>
                  <th className="text-center py-4 px-4 font-semibold">Solo Agent</th>
                  <th className="text-center py-4 px-4 font-semibold bg-primary/5">Team</th>
                  <th className="text-center py-4 px-4 font-semibold">Brokerage</th>
                  <th className="text-center py-4 px-4 font-semibold">Enterprise</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr className="bg-muted/20">
                  <td className="py-3 px-4 font-semibold" colSpan={5}>Lead Management</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Referral Platforms</td>
                  <td className="text-center py-3 px-4">3 platforms</td>
                  <td className="text-center py-3 px-4 bg-primary/5">All 5</td>
                  <td className="text-center py-3 px-4">All 5</td>
                  <td className="text-center py-3 px-4">All 5</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Leads Synced to FUB</td>
                  <td className="text-center py-3 px-4">Unlimited</td>
                  <td className="text-center py-3 px-4 bg-primary/5">Unlimited</td>
                  <td className="text-center py-3 px-4">Unlimited</td>
                  <td className="text-center py-3 px-4">Unlimited</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Status Updates to Platforms</td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Commission Tracking</td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Team Members</td>
                  <td className="text-center py-3 px-4">1</td>
                  <td className="text-center py-3 px-4 bg-primary/5">Up to 5</td>
                  <td className="text-center py-3 px-4">Up to 15</td>
                  <td className="text-center py-3 px-4">Unlimited</td>
                </tr>
                <tr className="bg-muted/20">
                  <td className="py-3 px-4 font-semibold" colSpan={5}>Lead Enrichment (Monthly)</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Enhancement Credits</td>
                  <td className="text-center py-3 px-4">25</td>
                  <td className="text-center py-3 px-4 bg-primary/5">100</td>
                  <td className="text-center py-3 px-4">300</td>
                  <td className="text-center py-3 px-4">1000+</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Criminal Searches</td>
                  <td className="text-center py-3 px-4">1</td>
                  <td className="text-center py-3 px-4 bg-primary/5">3</td>
                  <td className="text-center py-3 px-4">8</td>
                  <td className="text-center py-3 px-4">25+</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">DNC Checks</td>
                  <td className="text-center py-3 px-4">50</td>
                  <td className="text-center py-3 px-4 bg-primary/5">150</td>
                  <td className="text-center py-3 px-4">400</td>
                  <td className="text-center py-3 px-4">1500+</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Auto-Enhancement</td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr className="bg-muted/20">
                  <td className="py-3 px-4 font-semibold" colSpan={5}>Features</td>
                </tr>
                <tr>
                  <td className="py-3 px-4">FUB Embedded App</td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Credit Allocation</td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Team Analytics</td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">API Access</td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4 bg-primary/5"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4"><X className="h-5 w-5 text-muted-foreground inline-block" /></td>
                  <td className="text-center py-3 px-4"><Check className="h-5 w-5 text-primary inline-block" /></td>
                </tr>
                <tr>
                  <td className="py-3 px-4">Support</td>
                  <td className="text-center py-3 px-4">Email</td>
                  <td className="text-center py-3 px-4 bg-primary/5">Priority</td>
                  <td className="text-center py-3 px-4">Priority</td>
                  <td className="text-center py-3 px-4">Dedicated</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mt-12 text-center">
            <h3 className="text-2xl font-bold mb-4">Need Custom Pricing?</h3>
            <p className="text-muted-foreground mb-6">
              Contact our sales team for custom plans tailored to your brokerage needs.
            </p>
            <Button variant="outline" size="lg" asChild>
              <Link href="/contact">Contact Sales</Link>
            </Button>
          </div>
        </section>

        {/* FAQ */}
        <section className="mt-20 max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-center mb-8">Frequently Asked Questions</h2>
          <div className="space-y-6">
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border">
              <h3 className="font-semibold mb-2">What referral platforms do you support?</h3>
              <p className="text-muted-foreground text-sm">
                We currently support Homelight, Redfin Partner Agent, Referral Exchange, Agent Pronto, and My Agent Finder.
                We're adding new platforms regularly.
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border">
              <h3 className="font-semibold mb-2">How does lead syncing work?</h3>
              <p className="text-muted-foreground text-sm">
                LeadSynergy automatically pulls your leads from each connected referral platform and creates them in Follow Up Boss
                with all relevant details. When you update a lead's status in FUB, we sync that update back to the original platform.
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border">
              <h3 className="font-semibold mb-2">What are enhancement credits used for?</h3>
              <p className="text-muted-foreground text-sm">
                Enhancement credits let you enrich your leads with additional contact information like phone numbers,
                email addresses, and address history. This helps you reach leads that might have incomplete information.
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border">
              <h3 className="font-semibold mb-2">Can I purchase more credits if I run out?</h3>
              <p className="text-muted-foreground text-sm">
                Yes! You can purchase additional credit packs anytime from your billing dashboard. Credits purchased as add-ons
                don't expire and carry over month-to-month.
              </p>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 border">
              <h3 className="font-semibold mb-2">Can I upgrade or downgrade my plan?</h3>
              <p className="text-muted-foreground text-sm">
                Absolutely! You can change your plan at any time from your billing settings. Upgrades take effect immediately,
                and downgrades take effect at your next billing cycle.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
