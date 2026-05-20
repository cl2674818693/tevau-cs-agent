import { act, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TicketStatusBanner } from "../src/components/TicketStatusBanner";
import { useTicketStream } from "../src/hooks/useTicketStream";

type Listener = (e: { data: string }) => void;

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  url: string;
  listeners: Record<string, Listener[]> = {};
  closed = false;
  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }
  addEventListener(name: string, fn: Listener) {
    (this.listeners[name] ??= []).push(fn);
  }
  emit(name: string, data: unknown) {
    for (const fn of this.listeners[name] ?? []) fn({ data: JSON.stringify(data) });
  }
  close() {
    this.closed = true;
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
});
afterEach(() => vi.restoreAllMocks());

describe("useTicketStream", () => {
  it("opens stream and accumulates ticket events", () => {
    const { result } = renderHook(() => useTicketStream(7));
    const es = FakeEventSource.instances[0];
    expect(es.url).toBe("/api/v1/conversations/7/ticket-events-stream");
    act(() => es.emit("assigned", { external_id: "AI-7" }));
    act(() => es.emit("resolved", { external_id: "AI-7" }));
    expect(result.current.map((e) => e.event)).toEqual(["assigned", "resolved"]);
  });

  it("does not open when conversationId is null", () => {
    renderHook(() => useTicketStream(null));
    expect(FakeEventSource.instances.length).toBe(0);
  });

  it("closes the stream on unmount", () => {
    const { unmount } = renderHook(() => useTicketStream(1));
    const es = FakeEventSource.instances[0];
    unmount();
    expect(es.closed).toBe(true);
  });
});

describe("TicketStatusBanner", () => {
  it("renders nothing without events", () => {
    const { container } = render(<TicketStatusBanner events={[]} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the latest event label", () => {
    render(
      <TicketStatusBanner
        events={[
          { event: "assigned", external_id: "AI-1" },
          { event: "resolved", external_id: "AI-1" },
        ]}
      />,
    );
    expect(screen.getByText(/工单已解决 · AI-1/)).toBeTruthy();
  });
});
