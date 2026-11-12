"use client";

import React, { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertCircle, Info, X } from "lucide-react";

type ToastKind = "success" | "error" | "info";

interface ToastEntry {
  id: string;
  kind: ToastKind;
  title: string;
  description?: string;
}

interface ToastContextValue {
  pushToast: (title: string, kind?: ToastKind, description?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastEntry[]>([]);

  const dismiss = useCallback((id: string) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const pushToast = useCallback(
    (title: string, kind: ToastKind = "info", description?: string) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setItems((prev) => [...prev, { id, kind, title, description }]);
      setTimeout(() => {
        dismiss(id);
      }, 5000);
    },
    [dismiss]
  );

  return (
    <ToastContext.Provider value={{ pushToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2">
        {items.map((t) => (
          <div
            key={t.id}
            className="flex items-start gap-2.5 rounded-lg border border-slate-200 bg-white p-3 shadow-lg"
          >
            {t.kind === "success" && <CheckCircle2 className="mt-0.5 h-4 w-4 text-emerald-600" />}
            {t.kind === "error" && <AlertCircle className="mt-0.5 h-4 w-4 text-red-600" />}
            {t.kind === "info" && <Info className="mt-0.5 h-4 w-4 text-sky-600" />}
            <div className="flex-1 text-xs">
              <p className="font-semibold text-slate-900">{t.title}</p>
              {t.description && <p className="mt-0.5 text-slate-600">{t.description}</p>}
            </div>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              className="rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
