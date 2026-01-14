"use client";

import Link from "next/link";
import { ArrowRight, Search, Shield, Zap, Users } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Hero() {
  return (
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
  );
}
