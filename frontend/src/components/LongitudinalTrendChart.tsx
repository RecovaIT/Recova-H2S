"use client";

import React, { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Observation, PersonalBaseline } from "@/types/recova";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { formatLabel } from "@/lib/utils";

export function LongitudinalTrendChart({
  observations,
  baselines,
  initialMetric,
}: {
  observations: Observation[];
  baselines: PersonalBaseline[];
  initialMetric?: string;
}) {
  const availableMetrics = useMemo(() => {
    const set = new Set<string>();
    for (const o of observations) {
      if (o.value_num !== null && o.value_num !== undefined) {
        set.add(o.metric_code);
      }
    }
    return Array.from(set);
  }, [observations]);

  const [selectedMetric, setSelectedMetric] = useState<string>(initialMetric || "");
  const activeMetric =
    selectedMetric && availableMetrics.includes(selectedMetric)
      ? selectedMetric
      : availableMetrics[0] || "";

  const activeBaseline = baselines.find(
    (b) => b.metric_code === activeMetric && b.status === "established"
  );

  const chartData = useMemo(() => {
    if (!activeMetric) return [];
    return observations
      .filter((o) => o.metric_code === activeMetric && o.value_num !== null && o.value_num !== undefined)
      .slice()
      .sort((a, b) => new Date(a.effective_at).getTime() - new Date(b.effective_at).getTime())
      .map((o) => ({
        dateLabel: new Date(o.effective_at).toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        value: o.value_num as number,
        unit: o.unit || "",
        source: o.source,
      }));
  }, [observations, activeMetric]);

  const activeUnit = chartData[0]?.unit || "";

  const upperAmber =
    activeBaseline && activeBaseline.n_windows > 0
      ? activeBaseline.mean + 1.0 * Math.max(activeBaseline.sample_sd, 0.01)
      : null;
  const lowerAmber =
    activeBaseline && activeBaseline.n_windows > 0
      ? activeBaseline.mean - 1.0 * Math.max(activeBaseline.sample_sd, 0.01)
      : null;

  const upperRed =
    activeBaseline && activeBaseline.n_windows > 0
      ? activeBaseline.mean + 1.96 * Math.max(activeBaseline.sample_sd, 0.01)
      : null;
  const lowerRed =
    activeBaseline && activeBaseline.n_windows > 0
      ? activeBaseline.mean - 1.96 * Math.max(activeBaseline.sample_sd, 0.01)
      : null;

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
        <div>
          <CardTitle>Longitudinal Biomarker Drift vs Personal Baseline</CardTitle>
          <CardDescription>
            {activeBaseline
              ? `Baseline Mean: ${activeBaseline.mean.toFixed(2)} (SD ${activeBaseline.sample_sd.toFixed(2)} across ${activeBaseline.n_windows} windows)`
              : "Minimum 3–5 stable baseline windows required before deterministic drift bands appear."}
          </CardDescription>
        </div>
        {availableMetrics.length > 0 && (
          <div className="w-56">
            <Select
              aria-label="Select biomarker metric"
              value={activeMetric}
              onChange={(e) => setSelectedMetric(e.target.value)}
            >
              {availableMetrics.map((m) => (
                <option key={m} value={m}>
                  {formatLabel(m)}
                </option>
              ))}
            </Select>
          </div>
        )}
      </CardHeader>

      <CardContent className="space-y-3">
        {activeBaseline && (
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-600 px-2.5 py-1.5 bg-slate-50 dark:bg-slate-900/40 rounded-md border border-slate-200 dark:border-slate-800">
            <span className="flex items-center gap-1.5 font-medium">
              <span className="inline-block w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500" />
              Stable (|Z| &lt; 1.0σ)
            </span>
            <span className="flex items-center gap-1.5 font-medium">
              <span className="inline-block w-3 h-3 rounded bg-amber-500/25 border border-amber-500" />
              Early Drift (1.0σ ≤ |Z| &lt; 1.96σ)
            </span>
            <span className="flex items-center gap-1.5 font-medium">
              <span className="inline-block w-3 h-3 rounded bg-rose-500/25 border border-rose-500" />
              Elevated Alert (|Z| ≥ 1.96σ)
            </span>
          </div>
        )}

        {chartData.length === 0 ? (
          <EmptyState
            title="No numeric longitudinal observations recorded"
            description="Submit wearable batches, daily check-ins, IFHAS labs, cognitive trials, or WorkSafe readiness checks to chart longitudinal trends."
          />
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="dateLabel" tick={{ fontSize: 11, fill: "#475569" }} />
                <YAxis
                  tick={{ fontSize: 11, fill: "#475569" }}
                  domain={["auto", "auto"]}
                  label={
                    activeUnit
                      ? {
                          value: activeUnit,
                          angle: -90,
                          position: "insideLeft",
                          style: { textAnchor: "middle", fill: "#64748b", fontSize: 11 },
                          offset: -2,
                        }
                      : undefined
                  }
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    borderColor: "#cbd5e1",
                    fontSize: "12px",
                  }}
                />

                {/* Shaded baseline z-score regions */}
                {activeBaseline && upperAmber !== null && lowerAmber !== null && (
                  <ReferenceArea
                    y1={Math.max(0, lowerAmber)}
                    y2={upperAmber}
                    fill="#10b981"
                    fillOpacity={0.08}
                    ifOverflow="hidden"
                  />
                )}
                {activeBaseline && upperAmber !== null && upperRed !== null && (
                  <ReferenceArea
                    y1={upperAmber}
                    y2={upperRed}
                    fill="#f59e0b"
                    fillOpacity={0.12}
                    ifOverflow="hidden"
                  />
                )}
                {activeBaseline && lowerAmber !== null && lowerRed !== null && (
                  <ReferenceArea
                    y1={Math.max(0, lowerRed)}
                    y2={Math.max(0, lowerAmber)}
                    fill="#f59e0b"
                    fillOpacity={0.12}
                    ifOverflow="hidden"
                  />
                )}
                {activeBaseline && upperRed !== null && (
                  <ReferenceArea
                    y1={upperRed}
                    fill="#ef4444"
                    fillOpacity={0.10}
                    ifOverflow="hidden"
                  />
                )}
                {activeBaseline && lowerRed !== null && lowerRed > 0 && (
                  <ReferenceArea
                    y2={lowerRed}
                    fill="#ef4444"
                    fillOpacity={0.10}
                    ifOverflow="hidden"
                  />
                )}

                {activeBaseline && (
                  <ReferenceLine
                    y={activeBaseline.mean}
                    stroke="#0f766e"
                    strokeDasharray="4 4"
                    label={{ value: "Baseline Mean", fontSize: 10, fill: "#0f766e" }}
                  />
                )}
                {upperRed !== null && (
                  <ReferenceLine
                    y={upperRed}
                    stroke="#dc2626"
                    strokeDasharray="2 4"
                    label={{ value: "+1.96 SD", fontSize: 10, fill: "#dc2626" }}
                  />
                )}
                {lowerRed !== null && lowerRed >= 0 && (
                  <ReferenceLine
                    y={lowerRed}
                    stroke="#dc2626"
                    strokeDasharray="2 4"
                    label={{ value: "-1.96 SD", fontSize: 10, fill: "#dc2626" }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#0284c7"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "#0284c7" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
