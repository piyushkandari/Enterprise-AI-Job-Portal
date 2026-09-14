"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Home() {
  const [status, setStatus] = useState<string>("checking...");

  useEffect(() => {
    api
      .get("/health")
      .then((r) => setStatus(JSON.stringify(r.data)))
      .catch((e) => setStatus("ERROR: " + e.message));
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold">AI Job Board</h1>
        <p className="text-muted-foreground">Backend says:</p>
        <pre className="rounded bg-muted p-4 text-sm">{status}</pre>
      </div>
    </main>
  );
}