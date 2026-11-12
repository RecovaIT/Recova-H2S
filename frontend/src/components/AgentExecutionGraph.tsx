"use client";

import React, { useState } from "react";
import {
  AlertOctagon,
  CheckCircle2,
  Clock,
  Eye,
  MinusCircle,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { AgentStep, PipelineRunDetail } from "@/types/recova";
import { cn, formatLabel } from "@/lib/utils";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { RiskBadge, StatusBadge } from "@/components/RiskBadge";

const STEP_STYLE: Record<string, { border: string; icon: React.ReactNode }> = {
  completed: {
    border: "border-emerald-300 bg-emerald-50/60",
    icon: <CheckCircle2 className="h-4 w-4 text-emerald-600" />,
  },
  flagged: {
    border: "border-red-400 bg-red-50",
    icon: <AlertOctagon className="h-4 w-4 text-red-600" />,
  },
  failed: {
    border: "border-red-300 bg-red-50/70",
    icon: <XCircle className="h-4 w-4 text-red-600" />,
  },
  bypassed: {
    border: "border-amber-300 bg-amber-50/60",
    icon: <MinusCircle className="h-4 w-4 text-amber-600" />,
  },
  skipped: {
    border: "border-slate-200 bg-slate-50",
    icon: <MinusCircle className="h-4 w-4 text-slate-400" />,
  },
  running: {
    border: "border-sky-300 bg-sky-50",
    icon: <Clock className="h-4 w-4 animate-spin text-sky-600" />,
  },
  waiting: {
    border: "border-slate-200 bg-white",
    icon: <Clock className="h-4 w-4 text-slate-400" />,
  },
};

export function AgentExecutionGraph({
  run,
  canInspect = false,
}: {
  run: PipelineRunDetail;
  canInspect?: boolean;
}) {
  const [selectedStep, setSelectedStep] = useState<AgentStep | null>(null);
  const steps = [...(run.steps || [])].sort((a, b) => a.step_order - b.step_order);

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-teal-700" />
            Shared Six-Agent Execution Graph
          </CardTitle>
          <CardDescription>
            Run <code className="text-[11px]">{run.id.slice(0, 8)}</code> · Track{" "}
            {formatLabel(run.track)} · Trigger: {formatLabel(run.trigger)} · Algorithm{" "}
            <code>v{run.algorithm_version}</code>
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={run.status} />
          {run.risk_tier && <RiskBadge tier={run.risk_tier} />}
          {run.confidence_index !== null && run.confidence_index !== undefined && (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 tabular-nums">
              Confidence {Math.round(run.confidence_index * 100)}%
            </span>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {steps.map((step) => {
            const st = STEP_STYLE[step.status] || STEP_STYLE.waiting;
            return (
              <div
                key={step.id}
                className={cn(
                  "flex flex-col justify-between rounded-xl border p-3 transition-shadow hover:shadow-xs",
                  st.border
                )}
              >
                <div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                      Step {step.step_order}
                    </span>
                    {st.icon}
                  </div>
                  <div className="mt-1.5 text-xs font-semibold text-slate-900">
                    {step.agent_name}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-600 line-clamp-3">
                    {step.message || formatLabel(step.status)}
                  </div>
                  {step.error && (
                    <div className="mt-1 rounded bg-red-100 px-1.5 py-1 text-[10px] text-red-800">
                      {step.error}
                    </div>
                  )}
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-black/5 pt-2 text-[11px] text-slate-500">
                  <span className="tabular-nums">
                    {step.duration_ms !== null && step.duration_ms !== undefined
                      ? `${step.duration_ms} ms`
                      : "—"}
                  </span>
                  {canInspect && (step.input_payload || step.output_payload) && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 px-1.5 text-[11px]"
                      onClick={() => setSelectedStep(step)}
                    >
                      <Eye className="h-3 w-3" /> I/O
                    </Button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>

      <Dialog
        open={Boolean(selectedStep)}
        onOpenChange={(open) => !open && setSelectedStep(null)}
        title={selectedStep ? `${selectedStep.agent_name} — Agent I/O Audit` : ""}
        description={
          selectedStep
            ? `Status: ${selectedStep.status} · Duration: ${selectedStep.duration_ms ?? "—"} ms`
            : undefined
        }
        maxWidthClass="max-w-3xl"
      >
        {selectedStep && (
          <div className="space-y-4">
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                Validated Input Payload
              </h4>
              <pre className="max-h-60 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                {JSON.stringify(selectedStep.input_payload ?? {}, null, 2)}
              </pre>
            </div>
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-600">
                Schema-Validated Output Payload
              </h4>
              <pre className="max-h-64 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-emerald-200">
                {JSON.stringify(selectedStep.output_payload ?? {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </Dialog>
    </Card>
  );
}
