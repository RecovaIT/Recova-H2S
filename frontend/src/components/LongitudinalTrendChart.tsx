"use client";

import React, { useMemo, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
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

      <CardContent>
        {chartData.length === 0 ? (
          <EmptyState
            title="No numeric longitudinal observations recorded"
            description="Submit wearable batches, daily check-ins, IFHAS labs, cognitive trials, or WorkSafe readiness checks to chart longitudinal trends."
          />
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="dateLabel" tick={{ fontSize: 11, fill: "#475569" }} />
                <YAxis tick={{ fontSize: 11, fill: "#475569" }} domain={["auto", "auto"]} />
                <Tooltip
                  contentStyle={{
                    borderRadius: "8px",
                    borderColor: "#cbd5e1",
                    fontSize: "12px",
                  }}
                />
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
