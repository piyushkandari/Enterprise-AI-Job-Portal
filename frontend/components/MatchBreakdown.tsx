import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

function StatusIcon({ status }: { status: Verdict["status"] }) {
  const cls = "inline-block h-2.5 w-2.5 rounded-full";
  if (status === "met") return <span className={cn(cls, "bg-emerald-500")} />;
  if (status === "partial") return <span className={cn(cls, "bg-amber-500")} />;
  return <span className={cn(cls, "bg-rose-500")} />;
}

function VerdictList({ items }: { items: Verdict[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground py-3">Nothing here.</p>;
  }
  return (
    <ul className="space-y-3 pt-2">
      {items.map((v, i) => (
        <li key={i} className="rounded-md border p-3">
          <div className="flex items-center gap-2">
            <StatusIcon status={v.status} />
            <span className="font-medium">{v.requirement}</span>
            <span className="ml-auto text-xs text-muted-foreground">
              weight {v.weight} · confidence {(v.confidence * 100).toFixed(0)}%
            </span>
          </div>
          {v.evidence && (
            <p className="mt-2 text-sm text-muted-foreground italic border-l-2 pl-3">
              “{v.evidence}”
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

export function MatchBreakdown({ verdicts }: { verdicts: Verdict[] }) {
  const met = verdicts.filter((v) => v.status === "met");
  const partial = verdicts.filter((v) => v.status === "partial");
  const missing = verdicts.filter((v) => v.status === "missing");

  return (
    <Tabs defaultValue="met" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="met">Met ({met.length})</TabsTrigger>
        <TabsTrigger value="partial">Partial ({partial.length})</TabsTrigger>
        <TabsTrigger value="missing">Missing ({missing.length})</TabsTrigger>
      </TabsList>
      <TabsContent value="met"><VerdictList items={met} /></TabsContent>
      <TabsContent value="partial"><VerdictList items={partial} /></TabsContent>
      <TabsContent value="missing"><VerdictList items={missing} /></TabsContent>
    </Tabs>
  );
}