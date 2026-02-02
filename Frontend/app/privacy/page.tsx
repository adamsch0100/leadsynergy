"use client"

import Link from "next/link"
import { ArrowLeft, Shield, Lock, Eye, Database, Bell, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { useRouter } from "next/navigation"

export default function PrivacyPolicyPage() {
  const router = useRouter()

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-green-50 to-teal-50 dark:from-green-950/20 dark:to-teal-950/20">
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
                Privacy
              </span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4">
              Privacy Policy
            </h1>
            <p className="text-lg text-muted-foreground">
              Last updated: February 2, 2026
            </p>
          </div>
        </div>
      </section>

      {/* Overview Cards */}
      <section className="container py-12 md:py-16">
        <div className="max-w-3xl mx-auto mb-12">
          <p className="text-muted-foreground mb-6">
            LeadSynergy LLC (&quot;we&quot;, &quot;us&quot;, or &quot;our&quot;) is committed to protecting the
            privacy of our users and the consumers whose data is processed through our
            platform. This Privacy Policy explains how we collect, use, store, and share
            information when you use the LeadSynergy service.
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3 max-w-4xl mx-auto mb-16">
          <Card>
            <CardHeader>
              <div className="h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/50 flex items-center justify-center mb-2">
                <Lock className="h-6 w-6 text-green-600" />
              </div>
              <CardTitle className="text-lg">Encrypted at Rest</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              All data is stored in encrypted databases hosted by Supabase with
              enterprise-grade security.
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center mb-2">
                <Eye className="h-6 w-6 text-blue-600" />
              </div>
              <CardTitle className="text-lg">Transparent Practices</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              We only collect data necessary to provide and improve the Service.
              No data is sold to third parties.
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="h-12 w-12 rounded-lg bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center mb-2">
                <Database className="h-6 w-6 text-purple-600" />
              </div>
              <CardTitle className="text-lg">Your Data, Your Control</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              You can export or delete your data at any time. We retain data only
              as long as necessary to provide the Service.
            </CardContent>
          </Card>
        </div>

        {/* Detailed Sections */}
        <div className="max-w-3xl mx-auto">
          <Accordion type="multiple" className="space-y-4">
            <AccordionItem value="collection" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                1. Information We Collect
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-4">
                <div>
                  <p className="font-medium text-foreground mb-2">Account Information</p>
                  <p>
                    When you create an account, we collect your name, email address, password
                    (stored as a hash, never in plaintext), organization name, and billing
                    information (processed and stored by Stripe).
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">CRM and Integration Data</p>
                  <p>
                    When you connect your Follow Up Boss account, we access lead data including
                    names, phone numbers, email addresses, property preferences, conversation
                    history, tags, stages, and notes. This data is used to provide AI-assisted
                    follow-up and synchronization services.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">Referral Platform Data</p>
                  <p>
                    If you enable referral platform integrations, we access your account on
                    those platforms to synchronize lead status updates. We store the minimum
                    data necessary to perform these synchronizations.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">Usage Data</p>
                  <p>
                    We automatically collect information about how you use the Service, including
                    pages visited, features used, AI agent performance metrics, and error logs.
                    This data is used to improve the Service and diagnose issues.
                  </p>
                </div>
                <div>
                  <p className="font-medium text-foreground mb-2">Cookies</p>
                  <p>
                    We use essential cookies to maintain your session and authentication state.
                    We do not use third-party advertising or tracking cookies.
                  </p>
                </div>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="use" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                2. How We Use Your Information
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>We use the information we collect to:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Provide, maintain, and improve the LeadSynergy service</li>
                  <li>Generate AI-powered responses and follow-up messages on your behalf</li>
                  <li>Synchronize lead status across your connected platforms</li>
                  <li>Score and qualify leads based on conversation analysis</li>
                  <li>Schedule follow-up sequences and appointments</li>
                  <li>Process payments and manage your subscription</li>
                  <li>Send service-related communications (account alerts, billing updates)</li>
                  <li>Detect and prevent fraud, abuse, or security incidents</li>
                  <li>Generate aggregated analytics to improve service quality</li>
                </ul>
                <p>
                  We do not use your data to train AI models. Your conversation data is sent to
                  third-party AI providers (such as OpenRouter) solely to generate real-time
                  responses, and is not retained by those providers for training purposes.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="sharing" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                3. How We Share Your Information
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>We share your information only in the following circumstances:</p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>
                    <span className="font-medium text-foreground">Service providers:</span> We
                    use third-party services to operate our platform, including Supabase (database
                    and authentication), Stripe (payment processing), OpenRouter (AI model
                    inference), and Follow Up Boss (CRM integration). These providers process
                    data only as necessary to provide their services to us.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Your connected platforms:</span> When
                    you authorize integrations with referral platforms, we send status updates and
                    data to those platforms on your behalf.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Legal requirements:</span> We
                    may disclose information if required by law, regulation, legal process, or
                    governmental request.
                  </li>
                  <li>
                    <span className="font-medium text-foreground">Business transfers:</span> In
                    the event of a merger, acquisition, or sale of assets, your data may be
                    transferred to the successor entity.
                  </li>
                </ul>
                <p className="font-medium text-foreground">
                  We do not sell your personal information or lead data to third parties.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="security" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                4. Data Security
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  We implement industry-standard security measures to protect your data:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>All data is encrypted in transit using TLS 1.2+</li>
                  <li>Database storage is encrypted at rest via Supabase (AES-256)</li>
                  <li>Authentication is managed by Supabase Auth with secure session handling</li>
                  <li>API keys and credentials for third-party services are stored encrypted</li>
                  <li>Access to production systems is restricted and logged</li>
                  <li>We conduct regular security reviews of our codebase</li>
                </ul>
                <p>
                  While we strive to protect your data, no method of electronic transmission or
                  storage is 100% secure. We cannot guarantee absolute security.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="retention" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                5. Data Retention
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  We retain your data for as long as your account is active and as needed to
                  provide the Service. Specifically:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Account data: Retained while your account is active</li>
                  <li>Lead and conversation data: Retained while your account is active</li>
                  <li>AI agent logs and analytics: Retained for 12 months</li>
                  <li>Billing records: Retained for 7 years as required by tax law</li>
                  <li>Support tickets: Retained for 3 years after resolution</li>
                </ul>
                <p>
                  After account cancellation, we retain your data for 30 days to allow for
                  reactivation or data export. After that period, data is permanently deleted
                  from our active systems. Backups may retain data for up to 90 additional days
                  before being purged.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="rights" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                6. Your Rights
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  Depending on your location, you may have the following rights regarding your
                  personal data:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li><span className="font-medium text-foreground">Access:</span> Request a copy of the personal data we hold about you</li>
                  <li><span className="font-medium text-foreground">Correction:</span> Request that we correct inaccurate or incomplete data</li>
                  <li><span className="font-medium text-foreground">Deletion:</span> Request that we delete your personal data</li>
                  <li><span className="font-medium text-foreground">Portability:</span> Request your data in a structured, machine-readable format</li>
                  <li><span className="font-medium text-foreground">Restriction:</span> Request that we limit processing of your data</li>
                  <li><span className="font-medium text-foreground">Objection:</span> Object to processing of your data for certain purposes</li>
                </ul>
                <p>
                  To exercise any of these rights, contact us at support@leadsynergy.com. We
                  will respond to your request within 30 days.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="consumer" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                7. Consumer Data (Lead Data)
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  LeadSynergy processes consumer data (lead information) on behalf of our users.
                  In this capacity, our users are the data controllers and LeadSynergy acts as a
                  data processor.
                </p>
                <p>
                  We process lead data solely as instructed by our users and as necessary to
                  provide the Service. This includes:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Storing lead contact information synced from your CRM</li>
                  <li>Analyzing conversation content to detect intent and generate responses</li>
                  <li>Tracking lead scores and engagement metrics</li>
                  <li>Honoring opt-out requests from consumers (STOP messages)</li>
                </ul>
                <p>
                  If a consumer contacts us directly about their data, we will refer them to the
                  appropriate LeadSynergy user (the data controller) and assist as needed.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="ccpa" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                8. California Privacy Rights (CCPA)
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  If you are a California resident, the California Consumer Privacy Act (CCPA)
                  provides you with additional rights:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Right to know what personal information is collected, used, shared, or sold</li>
                  <li>Right to delete personal information held by businesses</li>
                  <li>Right to opt out of the sale of personal information</li>
                  <li>Right to non-discrimination for exercising your CCPA rights</li>
                </ul>
                <p>
                  We do not sell personal information as defined by the CCPA. To submit a CCPA
                  request, contact us at support@leadsynergy.com.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="children" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                9. Children&apos;s Privacy
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  The Service is not directed to individuals under the age of 18. We do not
                  knowingly collect personal information from children. If you become aware that
                  a child has provided us with personal information, please contact us and we
                  will take steps to delete that information.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="changes" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                10. Changes to This Policy
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  We may update this Privacy Policy from time to time. We will notify you of
                  material changes by posting the updated policy on this page with a new
                  &quot;Last updated&quot; date and, where appropriate, by sending an email notification.
                </p>
                <p>
                  We encourage you to review this policy periodically. Your continued use of the
                  Service after changes constitutes acceptance of the updated policy.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="contact" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                11. Contact Us
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  If you have questions or concerns about this Privacy Policy or our data
                  practices, please contact us:
                </p>
                <ul className="list-none space-y-1">
                  <li>Email: support@leadsynergy.com</li>
                  <li>Website: <Link href="/contact" className="text-primary hover:underline">Contact Page</Link></li>
                </ul>
              </AccordionContent>
            </AccordionItem>
          </Accordion>
        </div>
      </section>

      {/* Related Links */}
      <section className="bg-muted/40 py-12">
        <div className="container">
          <h3 className="text-xl font-bold mb-6">Related Policies</h3>
          <div className="flex flex-wrap gap-6">
            <Link href="/terms" className="text-sm text-primary hover:underline">
              Terms of Service
            </Link>
            <Link href="/compliance" className="text-sm text-primary hover:underline">
              DNC & TCPA Compliance Guide
            </Link>
            <Link href="/contact" className="text-sm text-primary hover:underline">
              Contact Us
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}
