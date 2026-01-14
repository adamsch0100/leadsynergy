import type React from "react"
import type { Metadata } from "next"
import { Inter } from "next/font/google"
import "./globals.css"
import { LoadingProvider } from "@/components/loading-provider"
import { SubscriptionProvider } from "@/contexts/subscription-context"
import { PricingProvider } from "@/contexts/pricing-context"
import { ThemeProvider } from "@/components/theme-provider"
import { Suspense } from "react"

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
})

export const metadata: Metadata = {
  title: "LeadSynergy - Real Estate Lead Management & Enrichment",
  description: "Organize, enrich, and convert more leads with the complete platform for real estate professionals",
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable}`}>
      <body className="min-h-screen font-sans antialiased">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <Suspense fallback={<div>Loading...</div>}>
            <LoadingProvider>
              <SubscriptionProvider>
                <PricingProvider>
                  {children}
                </PricingProvider>
              </SubscriptionProvider>
            </LoadingProvider>
          </Suspense>
        </ThemeProvider>
      </body>
    </html>
  )
}
