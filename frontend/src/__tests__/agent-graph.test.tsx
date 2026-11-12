import React from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentExecutionGraph } from "@/components/AgentExecutionGraph";
import type { PipelineRunDetail } from "@/types/recova";

const SAMPLE_EMERGENCY_RUN: PipelineRunDetail = {
  id: "11111111-1111-1111-1111-111111111111",
  organization_id: "22222222-2222-2222-2222-222222222222",
  patient_id: "33333333-3333-3333-3333-333333333333",
  track: "core",
  status: "emergency_bypass",
  trigger: "checkin",
  algorithm_version: "1.2.0",
  risk_tier: "EMERGENCY_BYPASS",
  confidence_index: 1.0,
  is_emergency: true,
  as_of: "2026-11-12T10:00:00Z",
  created_at: "2026-11-12T10:00:00Z",
  steps: [
    {
      id: "s1",
      run_id: "11111111-1111-1111-1111-111111111111",
      agent_key: "gate1_consent",
      agent_name: "Gate 1 — Consent & Governance",
      step_order: 1,
      status: "completed",
      message: "Consent verified",
      duration_ms: 4,
      input_payload: { patient_id: "p1" },
      output_payload: { consent_granted: true },
    },
    {
      id: "s2",
      run_id: "11111111-1111-1111-1111-111111111111",
      agent_key: "gate2_emergency",
      agent_name: "Gate 2 — Emergency Bypass",
      step_order: 2,
      status: "flagged",
      message: "Suicidal ideation red flag triggered",
      duration_ms: 2,
      input_payload: { text: "help" },
      output_payload: { rule_codes: ["SUICIDAL_IDEATION"] },
    },
    {
      id: "s3",
      run_id: "11111111-1111-1111-1111-111111111111",
      agent_key: "agent3_aggregator",
      agent_name: "Agent 3 — Signal Aggregator",
      step_order: 3,
      status: "skipped",
      message: "Bypassed due to emergency",
    },
  ],
};

describe("AgentExecutionGraph", () => {
  it("renders agent statuses and restricts I/O inspector by permission", async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <AgentExecutionGraph run={SAMPLE_EMERGENCY_RUN} canInspect={false} />
    );

    expect(screen.getByText("EMERGENCY BYPASS")).toBeInTheDocument();
    expect(screen.getByText("Suicidal ideation red flag triggered")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /I\/O/i })).not.toBeInTheDocument();

    rerender(<AgentExecutionGraph run={SAMPLE_EMERGENCY_RUN} canInspect={true} />);
    const buttons = screen.getAllByRole("button", { name: /I\/O/i });
    expect(buttons.length).toBe(2);

    await user.click(buttons[1]);
    expect(screen.getByText(/SUICIDAL_IDEATION/)).toBeInTheDocument();
  });
});
