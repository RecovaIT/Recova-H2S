"use client";

import React from "react";
import { Globe } from "lucide-react";
import { useLanguage } from "@/hooks/useLanguage";
import { cn } from "@/lib/utils";

export function LanguageSwitcher({
  variant = "inline",
  className,
}: {
  variant?: "floating" | "inline";
  className?: string;
}) {
  const { isAr, toggleLang } = useLanguage();

  return (
    <button
      type="button"
      onClick={toggleLang}
      aria-label="Toggle language"
      title={isAr ? "Switch to English" : "التبديل إلى العربية"}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border border-[#e2edf2] bg-white px-3 py-1.5 text-xs font-semibold text-[#003e5e] shadow-sm transition-colors hover:bg-[#f0f6f9] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#175675]",
        variant === "floating" && "fixed right-4 top-4 z-50",
        className
      )}
    >
      <Globe className="h-3.5 w-3.5 shrink-0" />
      <span>{isAr ? "English" : "العربية"}</span>
    </button>
  );
}
