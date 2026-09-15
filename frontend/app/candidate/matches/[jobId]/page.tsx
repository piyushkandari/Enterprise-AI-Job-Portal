"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

import { api } from "@/lib/api";
import { getStoredUser } from "@/lib/auth";
import type { Verdict } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { MatchBreakdown } from "@/components/MatchBreakdown";
import { InterestButton } from "@/components/InterestButton";

interface MatchDetail {
  job_id: string;
  job_title: string;
  job_description: string;
  score: number;
  explanation: string;
  verdicts: Verdict[];
  computed_at: string;
  is_interested?: boolean;
}

export default function MatchDetailPage() {
  const params = useParams<{ jobId: string }>();
  const router = useRouter();
  const [match, setMatch] = useState<MatchDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const u = getStoredUser();
    if (!u || u.role !== "candidate") {
      router.replace("/login");
      return;
    }
    api
      .get<MatchDetail>(`/match/for-job/${params.jobId}`)
      .then((r) => setMatch(r.data))
      .catch((e) => setError(e?.response?.data?.detail ?? "Failed to load match"))
      .finally(() => setLoading(false));
  }, [params.jobId, router]);

  return (
    <main className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-4xl p-8 space-y-6">

        <Button asChild variant="ghost" size="sm">
          <Link href="/candidate/dashboard">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to dashboard
          </Link>
        </Button>

        {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

        {error && (
          <Alert>
            <AlertTitle>Cannot load match</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {match && (
          <>
            <Card>
              <CardHeader className="flex flex-row items-start justify-between space-y-0">
                <div>
                  <CardTitle className="text-2xl">{match.job_title}</CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">
                    Computed {new Date(match.computed_at).toLocaleString()}
                  </p>
                </div>
                <MatchScoreBadge score={match.score} size="lg" />
              </CardHeader>
              <CardContent>
                <p className="text-sm leading-relaxed">{match.explanation}</p>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="pt-6">
                <InterestButton
                  jobId={match.job_id}
                  initial={!!match.is_interested}
                  onChange={(v) =>
                    setMatch((prev) => (prev ? { ...prev, is_interested: v } : prev))
                  }
                />
                <p className="mt-2 text-xs text-center text-muted-foreground">
                  Let the employer know you&apos;re interested. They&apos;ll see your
                  name, email, and profile on their dashboard.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Requirement Breakdown</CardTitle>
              </CardHeader>
              <CardContent>
                <MatchBreakdown verdicts={match.verdicts} />
              </CardContent>
            </Card>

            <details className="rounded-lg border bg-background p-4">
              <summary className="cursor-pointer text-sm font-medium">
                Job description
              </summary>
              <pre className="mt-3 whitespace-pre-wrap text-sm text-muted-foreground font-sans">
                {match.job_description}
              </pre>
            </details>
          </>
        )}

      </div>
    </main>
  );
}