import { cn } from "@/lib/utils";

export function MatchScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const tone =
    score >= 70
      ? "bg-emerald-100 text-emerald-800 border-emerald-200"
      : score >= 40
      ? "bg-amber-100 text-amber-800 border-amber-200"
      : "bg-rose-100 text-rose-800 border-rose-200";

  const sizeCls =
    size === "lg" ? "text-3xl px-5 py-2"
    : size === "sm" ? "text-sm px-2 py-0.5"
    : "text-lg px-3 py-1";

  return (
    <div className={cn("inline-flex items-center rounded-md border font-semibold tabular-nums", tone, sizeCls)}>
      {score.toFixed(0)}
      <span className="ml-1 text-xs font-normal opacity-70">/ 100</span>
    </div>
  );
}