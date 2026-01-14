"use client";

import Link from "next/link";
import { ArrowLeft, Shield, AlertTriangle, CheckCircle, FileText, Phone, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useRouter } from "next/navigation";

export default function CompliancePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-950/20 dark:to-emerald-950/20">
        <div className="container py-8 md:py-12">
          <Button
            variant="ghost"
            onClick={() => router.back()}
            className="flex items-center gap-2 mb-8"
          >
            <ArrowLeft className="h-4 w-4" />
            Go Back
          </Button>

          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 mb-4">
              <Shield className="h-6 w-6 text-green-600" />
              <span className="text-sm font-medium text-green-600 uppercase tracking-wide">
                Compliance Center
              </span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4">
              DNC & TCPA Compliance Guide
            </h1>
            <p className="text-lg text-muted-foreground">
              Understand the regulations that govern telemarketing and how our
              platform helps you stay compliant while reaching leads effectively.
            </p>
          </div>
        </div>
      </section>

      {/* What is DNC Section */}
      <section className="container py-12 md:py-16">
        <div className="grid gap-8 lg:grid-cols-2">
          <div>
            <h2 className="text-3xl font-bold mb-4">What is the Do Not Call Registry?</h2>
            <p className="text-muted-foreground mb-6">
              The National Do Not Call Registry is a list of phone numbers from consumers
              who have indicated their preference to limit the telemarketing calls they
              receive. The registry is managed by the Federal Trade Commission (FTC) and
              enforced by both the FTC and the Federal Communications Commission (FCC).
            </p>
            <p className="text-muted-foreground mb-6">
              As a real estate professional, you must check phone numbers against this
              registry before making cold calls. Our platform makes this simple with
              instant DNC checking built right into your workflow.
            </p>
            <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <div className="flex items-start gap-3">
                <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                <div>
                  <p className="font-medium text-yellow-800 dark:text-yellow-200">
                    Penalties for DNC Violations
                  </p>
                  <p className="text-sm text-yellow-700 dark:text-yellow-300">
                    Fines can reach up to $51,744 per call to a number on the registry.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Phone className="h-5 w-5 text-green-600" />
                  DNC Registry Facts
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium">245+ Million Numbers</p>
                    <p className="text-sm text-muted-foreground">
                      The registry contains hundreds of millions of phone numbers
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium">31-Day Update Window</p>
                    <p className="text-sm text-muted-foreground">
                      New numbers must be honored within 31 days of registration
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium">Numbers Don&apos;t Expire</p>
                    <p className="text-sm text-muted-foreground">
                      Once on the list, numbers stay until the consumer removes them
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium">Exemptions Exist</p>
                    <p className="text-sm text-muted-foreground">
                      Existing business relationships may be exempt (see below)
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* TCPA Section */}
      <section className="bg-muted/40 py-12 md:py-16">
        <div className="container">
          <h2 className="text-3xl font-bold mb-4">Understanding TCPA</h2>
          <p className="text-muted-foreground mb-8 max-w-3xl">
            The Telephone Consumer Protection Act (TCPA) of 1991 is a federal law that
            restricts telephone solicitations and the use of automated telephone equipment.
            It applies to calls, text messages, and faxes.
          </p>

          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-2">
                  <Phone className="h-6 w-6 text-blue-600" />
                </div>
                <CardTitle>Consent Requirements</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground">
                Prior express written consent is required for autodialed or prerecorded
                marketing calls to cell phones. Regular manual calls have different rules.
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-2">
                  <FileText className="h-6 w-6 text-purple-600" />
                </div>
                <CardTitle>Time Restrictions</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground">
                Telemarketing calls are only permitted between 8:00 AM and 9:00 PM in
                the recipient&apos;s local time zone.
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="h-12 w-12 rounded-lg bg-red-100 dark:bg-red-900/50 flex items-center justify-center mb-2">
                  <AlertTriangle className="h-6 w-6 text-red-600" />
                </div>
                <CardTitle>Penalties</CardTitle>
              </CardHeader>
              <CardContent className="text-muted-foreground">
                TCPA violations can result in statutory damages of $500 per violation,
                or up to $1,500 for willful violations.
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Exemptions Section */}
      <section className="container py-12 md:py-16">
        <h2 className="text-3xl font-bold mb-4">Real Estate Exemptions</h2>
        <p className="text-muted-foreground mb-8 max-w-3xl">
          There are certain exemptions that may apply to real estate professionals.
          However, we always recommend checking numbers against the DNC registry as
          a best practice.
        </p>

        <div className="grid gap-6 md:grid-cols-2 max-w-4xl">
          <Card className="border-green-200 dark:border-green-900">
            <CardHeader>
              <CardTitle className="text-green-700 dark:text-green-400">
                May Be Exempt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-1" />
                <span className="text-sm">
                  Existing business relationship (within 18 months of transaction)
                </span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-1" />
                <span className="text-sm">
                  Inquiry from the consumer (within 3 months)
                </span>
              </div>
              <div className="flex items-start gap-2">
                <CheckCircle className="h-4 w-4 text-green-600 mt-1" />
                <span className="text-sm">
                  Written permission obtained from the consumer
                </span>
              </div>
            </CardContent>
          </Card>

          <Card className="border-red-200 dark:border-red-900">
            <CardHeader>
              <CardTitle className="text-red-700 dark:text-red-400">
                Not Exempt
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600 mt-1" />
                <span className="text-sm">
                  Cold calling numbers with no prior relationship
                </span>
              </div>
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600 mt-1" />
                <span className="text-sm">
                  Purchased lead lists without consent verification
                </span>
              </div>
              <div className="flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-red-600 mt-1" />
                <span className="text-sm">
                  Consumer has specifically requested to be on your internal DNC list
                </span>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>

      {/* FAQ Section */}
      <section className="bg-muted/40 py-12 md:py-16">
        <div className="container">
          <h2 className="text-3xl font-bold mb-8">Frequently Asked Questions</h2>

          <div className="max-w-3xl">
            <Accordion type="single" collapsible className="space-y-4">
              <AccordionItem value="item-1" className="bg-background rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline">
                  How often should I check numbers against the DNC registry?
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  The FTC recommends checking your calling lists against the registry
                  at least every 31 days before initiating calls. Our platform allows
                  you to check numbers in real-time as you work with leads.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-2" className="bg-background rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline">
                  Can I call someone on the DNC list if they gave me their number?
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  Yes, if you have an established business relationship or if the
                  consumer has given you express written consent, you may be exempt.
                  However, you must honor any request to stop calling.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-3" className="bg-background rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline">
                  What&apos;s the difference between the federal DNC and state DNC lists?
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  Some states maintain their own Do Not Call lists with additional
                  requirements. Our platform checks against the federal registry.
                  Always check your state&apos;s specific requirements.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-4" className="bg-background rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline">
                  Do text messages fall under DNC and TCPA rules?
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  Yes, text messages are treated similarly to phone calls under TCPA.
                  You need prior express consent before sending marketing text messages,
                  and the DNC registry applies to text marketing as well.
                </AccordionContent>
              </AccordionItem>

              <AccordionItem value="item-5" className="bg-background rounded-lg px-4">
                <AccordionTrigger className="hover:no-underline">
                  How does LeadSynergy help with compliance?
                </AccordionTrigger>
                <AccordionContent className="text-muted-foreground">
                  Our platform includes built-in DNC checking that allows you to verify
                  phone numbers before you call. We maintain audit logs of all checks
                  for your records and provide compliance reports.
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container py-12 md:py-16">
        <div className="text-center max-w-2xl mx-auto">
          <Shield className="h-12 w-12 text-green-600 mx-auto mb-4" />
          <h2 className="text-3xl font-bold mb-4">Stay Compliant with Confidence</h2>
          <p className="text-muted-foreground mb-8">
            Our platform makes DNC compliance simple with real-time checking,
            audit trails, and easy-to-use tools built right into your workflow.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Button size="lg" asChild>
              <Link href="/signup">Start Free Trial</Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link href="/contact">Talk to Sales</Link>
            </Button>
          </div>
        </div>
      </section>

      {/* Resources */}
      <section className="bg-muted/40 py-12">
        <div className="container">
          <h3 className="text-xl font-bold mb-6">Official Resources</h3>
          <div className="flex flex-wrap gap-4">
            <a
              href="https://www.donotcall.gov/"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
            >
              FTC Do Not Call Registry
              <ExternalLink className="h-4 w-4" />
            </a>
            <a
              href="https://www.fcc.gov/consumers/guides/stop-unwanted-robocalls-and-texts"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
            >
              FCC Consumer Guide
              <ExternalLink className="h-4 w-4" />
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
