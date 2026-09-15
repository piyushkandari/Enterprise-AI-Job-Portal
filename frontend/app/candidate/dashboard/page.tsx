"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { RefreshCw } from "lucide-react";

import { api } from "@/lib/api";
import { getStoredUser, logout } from "@/lib/auth";
import type { Recommendation, Resume, UserResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ResumeUploader } from "@/components/ResumeUploader";
import { MatchScoreBadge } from "@/components/MatchScoreBadge";
import { ProcessingSkeleton } from "@/components/ProcessingSkeleton";

export default function CandidateDashboard() {
  const router = useRouter();

  // User is read from localStorage in an effect — never during render.
  const [user, setUser] = useState<UserResponse | null>(null);
  const [ready, setReady] = useState(false);

  const [resume, setResume] = useState<Resume | null>(null);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loadingResume, setLoadingResume] = useState(true);
  const [loadingRecs, setLoadingRecs] = useState(true);
  const [computing, setComputing] = useState(false);

  useEffect(() => {
    const u = getStoredUser();
    if (!u || u.role !== "candidate") {
      router.replace("/login");
      return;
    }
    setUser(u);
    setReady(true);
  }, [router]);

  const loadResume = useCallback(async () => {
    try {
      const { data } = await api.get<Resume | null>("/resumes/me/meta");
      setResume(data);
    } catch {
      setResume(null);
    } finally {
      setLoadingResume(false);
    }
  }, []);

  const loadCachedMatches = useCallback(async () => {
    try {
      const { data } = await api.get<{ recommendations: Recommendation[] }>("/match/me");
      setRecs(data.recommendations ?? []);
    } catch {
      setRecs([]);
    } finally {
      setLoadingRecs(false);
    }
  }, []);

  useEffect(() => {
    if (!ready) return;
    loadResume();
    loadCachedMatches();
  }, [ready, loadResume, loadCachedMatches]);

  async function computeMatches() {
    setComputing(true);
    try {
      const { data } = await api.post<{ recommendations: Recommendation[] }>("/match/recommend-jobs");
      setRecs(data.recommendations ?? []);
      toast.success(`Matched against ${data.recommendations.length} job(s)`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Matching failed");
    } finally {
      setComputing(false);
    }
  }

  if (!ready) {
    return <main className="min-h-screen bg-muted/30" />;
  }

  return (
    <main className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-5xl p-8 space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Candidate Dashboard</h1>
            <p className="text-sm text-muted-foreground">Signed in as {user?.email}</p>
          </div>
          <Button variant="outline" onClick={logout}>Log out</Button>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Your Resume</CardTitle>
          </CardHeader>
          <CardContent>
            {loadingResume ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : (
              <ResumeUploader
                current={resume}
                onUploaded={(r) => {
                  setResume(r);
                  toast.success("Uploaded. Refresh matches to re-run the pipeline.");
                }}
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0">
            <CardTitle>Recommended Jobs</CardTitle>
            <Button
              size="sm"
              variant="outline"
              disabled={!resume || computing}
              onClick={computeMatches}
            >
              <RefreshCw className={`h-4 w-4 mr-1 ${computing ? "animate-spin" : ""}`} />
              {computing ? "Computing…" : recs.length ? "Refresh" : "Compute matches"}
            </Button>
          </CardHeader>
          <CardContent>
            {!resume ? (
              <Alert>
                <AlertTitle>No resume yet</AlertTitle>
                <AlertDescription>
                  Upload a resume above to enable AI-powered job matching.
                </AlertDescription>
              </Alert>
            ) : computing ? (
              <ProcessingSkeleton label="Running the LangGraph matching pipeline…" />
            ) : loadingRecs ? (
              <ProcessingSkeleton label="Loading matches…" />
            ) : recs.length === 0 ? (
              <Alert>
                <AlertTitle>No matches yet</AlertTitle>
                <AlertDescription>
                  Click <strong>Compute matches</strong> to run the pipeline against all open jobs.
                </AlertDescription>
              </Alert>
            ) : (
              <ul className="space-y-3">
                {recs.map((r) => (
                  <li key={r.job_id}>
                    <Link
                      href={`/candidate/matches/${r.job_id}`}
                      className="block rounded-lg border p-4 transition hover:bg-accent"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <h3 className="font-semibold">{r.job_title}</h3>
                        <MatchScoreBadge score={r.score} />
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground line-clamp-2">
                        {r.explanation}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

      </div>
    </main>
  );
}