"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

export default function HomePage() {
  const router = useRouter();
  const { loading, needsBootstrap, session } = useAuth();

  useEffect(() => {
    if (loading) return;
    if (needsBootstrap) {
      router.replace("/bootstrap");
    } else if (session) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [loading, needsBootstrap, session, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin text-teal-700" />
        <span>Loading Recova platform...</span>
      </div>
    </div>
  );
}
