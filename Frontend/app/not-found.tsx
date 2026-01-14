import Link from "next/link"
import { Button } from "@/components/ui/button"
import { Home } from "lucide-react"

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20 p-4">
      <div className="text-center">
        <h1 className="text-9xl font-bold text-primary">404</h1>
        <h2 className="mt-4 text-3xl font-bold tracking-tight">Page Not Found</h2>
        <p className="mt-2 text-lg text-muted-foreground">
          The page you are looking for doesn&apos;t exist or has been moved.
        </p>
        <Button className="mt-8" size="lg" asChild>
          <Link href="/">
            <Home className="mr-2 h-5 w-5" />
            Return to Homepage
          </Link>
        </Button>
      </div>
    </div>
  )
}
