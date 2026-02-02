"use client"

import Link from "next/link"
import { ArrowLeft, FileText } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import { useRouter } from "next/navigation"

export default function TermsOfServicePage() {
  const router = useRouter()

  return (
    <div className="min-h-screen">
      {/* Hero Section */}
      <section className="bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-950/20 dark:to-blue-950/20">
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
              <FileText className="h-6 w-6 text-blue-600" />
              <span className="text-sm font-medium text-blue-600 uppercase tracking-wide">
                Legal
              </span>
            </div>
            <h1 className="text-4xl font-bold tracking-tight mb-4">
              Terms of Service
            </h1>
            <p className="text-lg text-muted-foreground">
              Last updated: February 2, 2026
            </p>
          </div>
        </div>
      </section>

      {/* Terms Content */}
      <section className="container py-12 md:py-16">
        <div className="max-w-3xl mx-auto prose prose-slate dark:prose-invert">

          <p className="text-muted-foreground mb-8">
            These Terms of Service (&quot;Terms&quot;) govern your access to and use of LeadSynergy
            (&quot;the Service&quot;), operated by LeadSynergy LLC (&quot;we&quot;, &quot;us&quot;, or &quot;our&quot;). By creating
            an account or using the Service, you agree to be bound by these Terms.
          </p>

          <Accordion type="multiple" className="space-y-4">
            <AccordionItem value="acceptance" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                1. Acceptance of Terms
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  By accessing or using LeadSynergy, you confirm that you are at least 18 years
                  old and have the legal authority to enter into these Terms on behalf of yourself
                  or the organization you represent.
                </p>
                <p>
                  If you do not agree with any part of these Terms, you must not use the Service.
                  We reserve the right to update these Terms at any time. Continued use of the
                  Service after changes constitutes acceptance of the revised Terms. We will notify
                  you of material changes via email or in-app notification.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="description" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                2. Description of Service
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  LeadSynergy is a lead management platform designed for real estate professionals.
                  The Service integrates with Follow Up Boss (FUB) and various referral platforms
                  to automate lead follow-up, status synchronization, and AI-assisted communication.
                </p>
                <p>Key features include:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>AI-powered lead follow-up via SMS and email through your CRM</li>
                  <li>Automated referral platform status synchronization</li>
                  <li>Lead scoring and qualification</li>
                  <li>Appointment scheduling assistance</li>
                  <li>Analytics and reporting</li>
                </ul>
                <p>
                  We may modify, suspend, or discontinue any part of the Service at any time with
                  reasonable notice.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="accounts" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                3. User Accounts
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  You are responsible for maintaining the confidentiality of your account credentials,
                  including your password and any API keys you configure within the Service.
                </p>
                <p>
                  You agree to: (a) provide accurate and complete information during registration;
                  (b) keep your account information up to date; (c) notify us immediately of any
                  unauthorized use of your account; and (d) accept responsibility for all activities
                  that occur under your account.
                </p>
                <p>
                  Each subscription is tied to a single organization. You may invite team members
                  to your organization based on your subscription plan limits.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="subscriptions" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                4. Subscriptions and Billing
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  LeadSynergy offers paid subscription plans billed on a monthly recurring basis.
                  Pricing and plan details are available on our pricing page and may be updated
                  from time to time with 30 days notice.
                </p>
                <p>
                  Payment is processed through Stripe. By subscribing, you authorize us to charge
                  your payment method on a recurring basis until you cancel. All fees are
                  non-refundable except as required by applicable law or as otherwise stated in
                  these Terms.
                </p>
                <p>
                  You may upgrade, downgrade, or cancel your subscription at any time through
                  your account settings. Downgrades and cancellations take effect at the end of
                  the current billing period. If your payment fails, we may suspend your access
                  to the Service after a grace period.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="usage" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                5. Acceptable Use
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>You agree not to:</p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Use the Service in violation of any applicable law or regulation, including TCPA, CAN-SPAM, and state telemarketing laws</li>
                  <li>Send unsolicited messages to consumers who have opted out or are on the Do Not Call registry without a valid exemption</li>
                  <li>Provide false or misleading information to leads through the AI agent or any other feature</li>
                  <li>Attempt to reverse-engineer, decompile, or extract the source code of the Service</li>
                  <li>Share your account credentials or allow unauthorized access to your account</li>
                  <li>Use the Service to harass, threaten, or abuse any person</li>
                  <li>Interfere with or disrupt the integrity or performance of the Service</li>
                  <li>Use automated means to access the Service beyond what we provide (e.g., scraping our platform)</li>
                </ul>
                <p>
                  We reserve the right to suspend or terminate accounts that violate these terms.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="compliance" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                6. Compliance Responsibilities
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  You are solely responsible for ensuring your use of the Service complies with
                  all applicable federal, state, and local laws, including but not limited to:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Telephone Consumer Protection Act (TCPA)</li>
                  <li>National Do Not Call Registry regulations</li>
                  <li>CAN-SPAM Act</li>
                  <li>State-specific real estate licensing and advertising requirements</li>
                  <li>Fair housing laws</li>
                </ul>
                <p>
                  While LeadSynergy provides tools to assist with compliance (such as quiet hours
                  enforcement and opt-out handling), the ultimate responsibility for legal compliance
                  rests with you. We recommend consulting with a legal professional regarding your
                  specific obligations.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="ai" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                7. AI Agent and Automated Communications
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  The LeadSynergy AI agent sends automated messages on your behalf through your
                  connected CRM system. By enabling the AI agent, you acknowledge and agree that:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Messages are sent from your business phone number and represent your business</li>
                  <li>You have obtained appropriate consent from recipients for automated communications</li>
                  <li>AI-generated responses, while designed to be helpful, may occasionally be inaccurate or inappropriate</li>
                  <li>You are responsible for monitoring AI conversations and intervening when necessary</li>
                  <li>We honor opt-out requests (STOP) automatically and you must not re-contact opted-out leads</li>
                </ul>
                <p>
                  We do not guarantee any specific conversion rate, response rate, or business
                  outcome from the use of the AI agent.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="thirdparty" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                8. Third-Party Integrations
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  The Service integrates with third-party platforms including Follow Up Boss,
                  referral networks, and payment processors. Your use of these integrations is
                  subject to the respective third-party terms of service.
                </p>
                <p>
                  We are not responsible for the availability, accuracy, or functionality of
                  third-party services. Changes to third-party APIs or terms may affect the
                  functionality of our Service. We will make reasonable efforts to adapt to such
                  changes but cannot guarantee uninterrupted integration.
                </p>
                <p>
                  By providing your API keys and credentials for third-party platforms, you
                  authorize us to access those platforms on your behalf to perform the services
                  described in your subscription plan.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="ip" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                9. Intellectual Property
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  The Service, including its software, design, text, graphics, and other content,
                  is owned by LeadSynergy LLC and protected by copyright, trademark, and other
                  intellectual property laws.
                </p>
                <p>
                  You retain ownership of all data you provide to the Service, including lead
                  information, conversation content, and business data. You grant us a limited
                  license to use this data solely to provide and improve the Service.
                </p>
                <p>
                  We may use aggregated, anonymized usage data for analytics and service
                  improvement purposes.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="disclaimer" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                10. Disclaimers and Limitation of Liability
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  THE SERVICE IS PROVIDED &quot;AS IS&quot; AND &quot;AS AVAILABLE&quot; WITHOUT WARRANTIES OF
                  ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED
                  WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND
                  NON-INFRINGEMENT.
                </p>
                <p>
                  We do not warrant that the Service will be uninterrupted, error-free, or secure.
                  We do not warrant the accuracy of any AI-generated content or the results of
                  any automated actions performed by the Service.
                </p>
                <p>
                  TO THE MAXIMUM EXTENT PERMITTED BY LAW, LEADSYNERGY LLC SHALL NOT BE LIABLE
                  FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES,
                  INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, BUSINESS OPPORTUNITIES,
                  OR GOODWILL, ARISING OUT OF OR RELATED TO YOUR USE OF THE SERVICE.
                </p>
                <p>
                  OUR TOTAL LIABILITY FOR ANY CLAIMS ARISING FROM YOUR USE OF THE SERVICE SHALL
                  NOT EXCEED THE AMOUNT YOU PAID US IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="indemnification" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                11. Indemnification
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  You agree to indemnify, defend, and hold harmless LeadSynergy LLC and its
                  officers, directors, employees, and agents from any claims, damages, losses,
                  liabilities, and expenses (including reasonable legal fees) arising from:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>Your use of the Service</li>
                  <li>Your violation of these Terms</li>
                  <li>Your violation of any applicable law or regulation</li>
                  <li>Any content or data you provide through the Service</li>
                  <li>Your interactions with leads and clients facilitated through the Service</li>
                </ul>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="termination" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                12. Termination
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  You may cancel your account at any time through your account settings or by
                  contacting support. We may suspend or terminate your account if you violate
                  these Terms or for any other reason with 30 days notice.
                </p>
                <p>
                  Upon termination: (a) your access to the Service will cease; (b) we will
                  retain your data for 30 days to allow for export, after which it may be
                  deleted; (c) any outstanding fees remain due; (d) provisions that by their
                  nature should survive termination will survive, including Sections 9, 10, 11,
                  and 13.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="governing" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                13. Governing Law and Disputes
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  These Terms are governed by the laws of the State of Florida, without regard to
                  conflict of law principles.
                </p>
                <p>
                  Any disputes arising from these Terms or your use of the Service shall first be
                  addressed through good-faith negotiation. If the dispute cannot be resolved
                  within 30 days, it shall be submitted to binding arbitration in accordance with
                  the rules of the American Arbitration Association.
                </p>
                <p>
                  You agree to resolve disputes on an individual basis and waive any right to
                  participate in class action lawsuits or class-wide arbitration.
                </p>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem value="contact" className="bg-muted/30 rounded-lg px-4">
              <AccordionTrigger className="hover:no-underline text-base font-semibold">
                14. Contact Information
              </AccordionTrigger>
              <AccordionContent className="text-muted-foreground space-y-3">
                <p>
                  If you have questions about these Terms, please contact us:
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
            <Link href="/privacy" className="text-sm text-primary hover:underline">
              Privacy Policy
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
