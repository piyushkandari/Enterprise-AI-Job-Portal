"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import type { Job } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

export function JobFormDialog({
  open, onOpenChange, existing, onSaved,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  existing: Job | null;
  onSaved: (j: Job) => void;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState<"open" | "closed">("open");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setTitle(existing?.title ?? "");
      setDescription(existing?.description ?? "");
      setStatus((existing?.status as "open" | "closed") ?? "open");
    }
  }, [open, existing]);

  async function save() {
    if (title.length < 2 || description.length < 20) {
      toast.error("Title and description must be meaningful");
      return;
    }
    setSaving(true);
    try {
      if (existing) {
        const { data } = await api.patch<Job>(`/jobs/${existing.id}`, { title, description, status });
        toast.success("Job updated");
        onSaved(data);
      } else {
        const { data } = await api.post<Job>("/jobs/", { title, description, status });
        toast.success("Job posted");
        onSaved(data);
      }
      onOpenChange(false);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{existing ? "Edit job" : "Post a new job"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="desc">Description</Label>
            <Textarea
              id="desc"
              rows={10}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Paste the full job description. Mention must-have and nice-to-have skills explicitly — the extraction node reads these signals."
            />
            <p className="text-xs text-muted-foreground">
              Longer descriptions with explicit &ldquo;required&rdquo;/&ldquo;nice to have&rdquo; language produce better extractions.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="status">Status</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as "open" | "closed")}>
              <SelectTrigger id="status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="open">Open</SelectItem>
                <SelectItem value="closed">Closed</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "Saving…" : existing ? "Save changes" : "Post job"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}