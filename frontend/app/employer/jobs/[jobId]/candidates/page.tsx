"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, RefreshCw, Star } from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type { Verdict } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { MatchBreakdown } from "@/components/MatchBreakdown";
import { ProcessingSkeleton } from "@/components/ProcessingSkeleton";

interface CandidateRow {
  resume_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  years_experience: number;
  score: number;
  explanation: string;
  verdicts: Verdict[];
  is_interested: boolean;
}

export default function JobCandidatesPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const [data, setData] = useState<{
    job_title: string;
    candidates: CandidateRow[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const u = getStoredUser();
    if (!u || u.role !== "employer") {
      router.replace("/login");
    }
  }, [router]);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/match/for-job-employer/${params.jobId}`);
      setData(data);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Failed to load candidates");
    } finally {
      setLoading(false);
    }
  }, [params.jobId]);

  useEffect(() => {
    load();
  }, [load]);

  async function compute() {
    setComputing(true);
    try {
      await api.post(`/match/compute-for-job/${params.jobId}`);
      toast.success("Candidates ranked");
      await load();
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Compute failed");
    } finally {
      setComputing(false);
    }
  }

  // Sort so interested candidates float to the top, then by score.
  const candidates = data?.candidates ?? [];
  const sorted = [...candidates].sort((a, b) => {
    if (a.is_interested !== b.is_interested) {
      return a.is_interested ? -1 : 1;
    }
    return b.score - a.score;
  });
  const interestedCount = candidates.filter((c) => c.is_interested).length;

  return (
    <main className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-5xl p-8 space-y-6">

        <Button asChild variant="ghost" size="sm">
          <Link href="/employer/dashboard">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back
          </Link>
        </Button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              {data?.job_title ?? "Top Candidates"}
            </h1>
            {interestedCount > 0 && (
              <p className="text-sm text-emerald-700 mt-1 flex items-center gap-1">
                <Star className="h-4 w-4 fill-current" />
                {interestedCount} candidate{interestedCount > 1 ? "s" : ""} marked interested
              </p>
            )}
          </div>
          <Button onClick={compute} disabled={computing}>
            <RefreshCw className={`h-4 w-4 mr-1 ${computing ? "animate-spin" : ""}`} />
            {computing ? "Ranking…" : "Compute / refresh"}
          </Button>
        </div>

        {computing && (
          <ProcessingSkeleton label="Ranking all candidates against this job…" />
        )}

        {loading && !data && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}

        {data && candidates.length === 0 && !computing && (
          <Alert>
            <AlertTitle>No candidates ranked yet</AlertTitle>
            <AlertDescription>
              Click <strong>Compute / refresh</strong> to run the pipeline against
              all candidate resumes.
            </AlertDescription>
          </Alert>
        )}

        {sorted.length > 0 && (
          <ul className="space-y-3">
            {sorted.map((c) => (
              <li
                key={c.resume_id}
                className={`rounded-lg border bg-background p-4 ${
                  c.is_interested ? "border-emerald-300 ring-1 ring-emerald-100" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold">{c.candidate_name}</h3>
                      {c.is_interested && (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 text-emerald-800 text-xs px-2 py-0.5 font-medium">
                          <Star className="h-3 w-3 fill-current" />
                          Interested
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {c.candidate_email || "no email"} · {c.years_experience} yrs exp
                    </p>
                  </div>
                  <MatchScoreBadge score={c.score} />
                </div>

                <p className="mt-2 text-sm text-muted-foreground">{c.explanation}</p>

                <Button
                  variant="link"
                  size="sm"
                  className="px-0 mt-1"
                  onClick={() =>
                    setExpanded(expanded === c.resume_id ? null : c.resume_id)
                  }
                >
                  {expanded === c.resume_id ? "Hide breakdown" : "Show breakdown"}
                </Button>

                {expanded === c.resume_id && (
                  <div className="mt-3">
                    <MatchBreakdown verdicts={c.verdicts} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}

      </div>
    </main>
  );
}