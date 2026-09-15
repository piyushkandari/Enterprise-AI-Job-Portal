"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Users } from "lucide-react";

import { api } from "@/lib/api";
import { getStoredUser, logout } from "@/lib/auth";
import type { Job, UserResponse } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { JobFormDialog } from "@/components/JobFormDialog";

export default function EmployerDashboard() {
  const router = useRouter();
  const [user, setUser] = useState<UserResponse | null>(null);
  const [ready, setReady] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<Job | null>(null);

  useEffect(() => {
    const u = getStoredUser();
    if (!u || u.role !== "employer") {
      router.replace("/login");
      return;
    }
    setUser(u);
    setReady(true);
  }, [router]);

  const loadJobs = useCallback(async () => {
    try {
      const { data } = await api.get<Job[]>("/jobs/mine");
      setJobs(data);
    } catch {
      setJobs([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) loadJobs();
  }, [ready, loadJobs]);

  async function deleteJob(job: Job) {
    if (!confirm(`Delete "${job.title}"? This also removes all its matches.`)) return;
    try {
      await api.delete(`/jobs/${job.id}`);
      toast.success("Job deleted");
      setJobs((prev) => prev.filter((j) => j.id !== job.id));
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Delete failed");
    }
  }

  if (!ready) return <main className="min-h-screen" />;

  return (
    <main className="min-h-screen bg-muted/30">
      <div className="mx-auto max-w-5xl p-8 space-y-6">

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Employer Dashboard</h1>
            <p className="text-sm text-muted-foreground">Signed in as {user?.email}</p>
          </div>
          <div className="flex gap-2">
            <Button
              onClick={() => { setEditing(null); setDialogOpen(true); }}
            >
              <Plus className="h-4 w-4 mr-1" /> Post job
            </Button>
            <Button variant="outline" onClick={logout}>Log out</Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Your Job Postings</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-muted-foreground">Loading…</p>
            ) : jobs.length === 0 ? (
              <Alert>
                <AlertTitle>No jobs yet</AlertTitle>
                <AlertDescription>
                  Click <strong>Post job</strong> to create your first listing.
                </AlertDescription>
              </Alert>
            ) : (
              <ul className="space-y-3">
                {jobs.map((job) => (
                  <li key={job.id} className="rounded-lg border p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="font-semibold truncate">{job.title}</h3>
                          <Badge variant={job.status === "open" ? "default" : "secondary"}>
                            {job.status}
                          </Badge>
                        </div>
                        <p className="mt-1 text-sm text-muted-foreground line-clamp-2">
                          {job.description}
                        </p>
                      </div>
                      <div className="flex gap-1 shrink-0">
                        <Button asChild size="sm" variant="outline">
                          <Link href={`/employer/jobs/${job.id}/candidates`}>
                            <Users className="h-4 w-4 mr-1" /> Candidates
                          </Link>
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => { setEditing(job); setDialogOpen(true); }}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          size="sm" variant="ghost"
                          onClick={() => deleteJob(job)}
                        >
                          <Trash2 className="h-4 w-4 text-rose-600" />
                        </Button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

      </div>

      <JobFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        existing={editing}
        onSaved={(j) => {
          setJobs((prev) => {
            const i = prev.findIndex((x) => x.id === j.id);
            if (i >= 0) { const c = [...prev]; c[i] = j; return c; }
            return [j, ...prev];
          });
        }}
      />
    </main>
  );
}