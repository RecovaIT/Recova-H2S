import { act, renderHook } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useRealtimeEvents } from '@/hooks/useRealtimeEvents';

afterEach(() => vi.unstubAllGlobals());
it('receives backend step and emergency events and closes on unmount', () => {
  const listeners = new Map<string, (e: MessageEvent) => void>();
  const close = vi.fn();
  vi.stubGlobal('EventSource', class {
    addEventListener(name: string, cb: (e: MessageEvent) => void) { listeners.set(name, cb); }
    close = close;
  });
  const cb = vi.fn();
  const { unmount } = renderHook(() => useRealtimeEvents(true, cb));
  for (const type of ['agent.step_started', 'agent.step_finished', 'pipeline.finished', 'pipeline.emergency_bypass']) {
    expect(listeners.has(type)).toBe(true);
    act(() => listeners.get(type)!({ data: JSON.stringify({type, data:{run_id:'1'}}) } as MessageEvent));
    expect(cb).toHaveBeenLastCalledWith(expect.objectContaining({type}));
  }
  unmount(); expect(close).toHaveBeenCalledOnce();
});
