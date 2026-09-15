import { Skeleton } from "@/components/ui/skeleton";

export function ProcessingSkeleton({ label = "Running match pipeline…" }: { label?: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 text-sm text-muted-foreground">
        <div className="h-2 w-2 animate-pulse rounded-full bg-primary" />
        {label}
      </div>
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-lg border p-5 space-y-3">
          <div className="flex items-center justify-between">
            <Skeleton className="h-5 w-48" />
            <Skeleton className="h-8 w-16" />
          </div>
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ))}
    </div>
  );
}