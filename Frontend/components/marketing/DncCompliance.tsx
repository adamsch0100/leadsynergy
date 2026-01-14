"use client";

import { Shield, AlertTriangle, CheckCircle, FileText } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function DncCompliance() {
  return (
    <section className="bg-gradient-to-b from-green-50 to-white dark:from-green-950/20 dark:to-background py-16 md:py-24">
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
                <CheckCircle className="h-6 w-6 text-green-600 dark:text-green-400" />
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
                <AlertTriangle className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
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
                <FileText className="h-6 w-6 text-blue-600 dark:text-blue-400" />
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
      </div>
    </section>
  );
}
