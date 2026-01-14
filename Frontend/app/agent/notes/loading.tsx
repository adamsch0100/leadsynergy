import { SidebarWrapper } from "@/components/sidebar"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"

export default function NotesLoading() {
  return (
    <SidebarWrapper role="agent">
      <div className="flex items-center justify-between mb-8">
        <div>
          <Skeleton className="h-8 w-[150px] mb-2" />
          <Skeleton className="h-4 w-[250px]" />
        </div>
        <Skeleton className="h-10 w-[100px]" />
      </div>

      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-[100px] mb-2" />
          <Skeleton className="h-4 w-[200px] mb-4" />
          <Skeleton className="h-10 w-full" />
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-start gap-4 border-b pb-4">
                <Skeleton className="h-5 w-[120px]" />
                <Skeleton className="h-5 flex-1" />
                <Skeleton className="h-5 w-[80px]" />
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </SidebarWrapper>
  )
}