import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider } from "@/components/ui/toast";
import { DecideAiReviewWorkspace } from "@/components/DecideAiReviewWorkspace";
import type { PipelineRunDetail } from "@/types/recova";

const BASE_RUN: PipelineRunDetail = {
  id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
  organization_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
  patient_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
  track: "core",
  status: "completed",
  trigger: "wearable",
  algorithm_version: "1.2.0",
  risk_tier: "RED",
  confidence_index: 0.92,
  is_emergency: false,
  as_of: "2026-11-12T10:00:00Z",
  created_at: "2026-11-12T10:00:00Z",
  steps: [],
  scoring: {
    id: "sr1",
    run_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    track: "core",
    algorithm_version: "1.2.0",
    risk_tier: "RED",
    confidence_index: 0.92,
    composite_index: 2.85,
    primary_metric_code: "hrv_rmssd",
    primary_z: -2.85,
    missing_streams: ["voice_checkin"],
    confounders_applied: [],
    config_snapshot: {},
    computed_at: "2026-11-12T10:00:00Z",
    metric_results: [
      {
        metric_code: "hrv_rmssd",
        label: "HRV RMSSD",
        unit: "ms",
        current_value: 22.0,
        baseline_mean: 48.0,
        baseline_sd: 4.5,
        adjusted_se: 2.25,
        signed_z: -2.85,
        risk_tier: "RED",
        status: "scored",
      },
    ],
  },
  synthesis: {
    id: "syn1",
    run_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    status: "provider_not_configured",
    prompt_version: "1.0.0",
    created_at: "2026-11-12T10:00:00Z",
  },
};

describe("DecideAiReviewWorkspace", () => {
  it("shows honest provider_not_configured notice and never fabricates AI summaries", () => {
    render(
      <ToastProvider>
        <DecideAiReviewWorkspace run={BASE_RUN} canSign={true} />
      </ToastProvider>
    );

    expect(screen.getByText(/HRV RMSSD/)).toBeInTheDocument();
    expect(screen.getByText("-2.85")).toBeInTheDocument();
    expect(screen.getByText(/AI Synthesis Not Executed/i)).toBeInTheDocument();
    expect(screen.getByText(/Recova never fabricates AI output/i)).toBeInTheDocument();
  });

  it("renders English and RTL Arabic tabs when synthesis completed", async () => {
    const user = userEvent.setup();
    const withSynth: PipelineRunDetail = {
      ...BASE_RUN,
      synthesis: {
        id: "syn2",
        run_id: BASE_RUN.id,
        status: "completed",
        provider: "openai",
        model: "gpt-4o-mini",
        prompt_version: "1.0.0",
        summary_en: "HRV dropped 2.85 SD below personal baseline.",
        summary_ar: "انخفض تقلب معدل ضربات القلب بمقدار 2.85.",
        structured: { priority: "urgent" },
        created_at: "2026-11-12T10:00:00Z",
      },
    };

    render(
      <ToastProvider>
        <DecideAiReviewWorkspace run={withSynth} canSign={false} />
      </ToastProvider>
    );

    expect(screen.getByText("HRV dropped 2.85 SD below personal baseline.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /الملخص العربي/i }));
    const arDiv = screen.getByText("انخفض تقلب معدل ضربات القلب بمقدار 2.85.");
    expect(arDiv).toHaveAttribute("dir", "rtl");
  });
});
