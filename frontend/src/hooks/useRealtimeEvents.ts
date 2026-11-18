"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/api";

export interface RealtimeEvent {
  type: string;
  timestamp?: string;
  data?: Record<string, unknown>;
}

export function useRealtimeEvents(
  enabled: boolean,
  onEvent?: (event: RealtimeEvent) => void
) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const callbackRef = useRef(onEvent);

  useEffect(() => {
    callbackRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    if (!enabled || typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }
    const url = `${API_BASE_URL.replace(/\/+$/, "")}/pipeline/events/stream`;
    const es = new EventSource(url, { withCredentials: true });

    const handlePayload = (raw: string, fallbackType: string) => {
      try {
        const parsed = JSON.parse(raw) as RealtimeEvent;
        const ev: RealtimeEvent = {
          type: parsed.type || fallbackType,
          timestamp: parsed.timestamp || new Date().toISOString(),
          data: parsed.data || {},
        };
        setEvents((prev) => [ev, ...prev].slice(0, 50));
        callbackRef.current?.(ev);
      } catch {
        // Ignore malformed keepalive frames
      }
    };

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (msg) => handlePayload(msg.data, "message");

    const eventNames = [
      "connected",
      "pipeline.started",
      "agent.step_started",
      "agent.step_finished",
      "pipeline.finished",
      "pipeline.emergency_bypass",
      "pipeline.step",
      "pipeline.completed",
      "pipeline.blocked",
      "pipeline.emergency",
      "review.signed",
      "referral.updated",
      "emergency.resolved",
    ];
    for (const evName of eventNames) {
      es.addEventListener(evName, (evt) => {
        const me = evt as MessageEvent<string>;
        handlePayload(me.data, evName);
      });
    }

    return () => {
      setConnected(false);
      es.close();
    };
  }, [enabled]);

  return { connected, events };
}
