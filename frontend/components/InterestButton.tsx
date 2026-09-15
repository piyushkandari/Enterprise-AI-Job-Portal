"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Check, Star } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function InterestButton({
  jobId,
  initial,
  onChange,
}: {
  jobId: string;
  initial: boolean;
  onChange?: (v: boolean) => void;
}) {
  const [interested, setInterested] = useState(initial);
  const [busy, setBusy] = useState(false);

  async function toggle() {
    setBusy(true);
    const next = !interested;
    try {
      if (next) {
        await api.post(`/interests/${jobId}`);
      } else {
        await api.delete(`/interests/${jobId}`);
      }
      setInterested(next);
      onChange?.(next);
      toast.success(next ? "Marked as interested" : "Interest removed");
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Failed to update");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      onClick={toggle}
      disabled={busy}
      variant={interested ? "default" : "outline"}
      size="lg"
      className="w-full"
    >
      {interested ? (
        <>
          <Check className="h-4 w-4 mr-2" /> Interested
        </>
      ) : (
        <>
          <Star className="h-4 w-4 mr-2" /> I&apos;m interested
        </>
      )}
    </Button>
  );
}