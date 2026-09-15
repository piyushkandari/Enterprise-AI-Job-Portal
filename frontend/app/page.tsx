// frontend/app/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getStoredUser, dashboardPathFor } from "@/lib/auth";

export default function Home() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const user = getStoredUser();
    if (user) {
      router.replace(dashboardPathFor(user.role));
    } else {
      setChecking(false);
    }
  }, [router]);

  if (checking) return null;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-6">
      <div className="text-center space-y-3 max-w-2xl">
        <h1 className="text-5xl font-bold tracking-tight">AI Job Board</h1>
        <p className="text-muted-foreground text-lg">
          Semantic job matching with grounded, explained scores.
          Not keyword search.
        </p>
      </div>
      <div className="flex gap-3">
        <Button asChild size="lg">
          <Link href="/signup">Get started</Link>
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href="/login">Log in</Link>
        </Button>
      </div>
    </main>
  );
}