"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function StageMappingPage() {
  const router = useRouter()

  useEffect(() => {
    // Redirect to Lead Sources page - stage mapping is now integrated there
    router.replace("/admin/lead-sources")
  }, [router])

  return (
    <div className="flex items-center justify-center min-h-screen">
      <p className="text-muted-foreground">Redirecting to Lead Sources...</p>
    </div>
  )
}
