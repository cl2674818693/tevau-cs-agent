import { render, renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const streamTicketEvents = vi.fn();
vi.mock("../src/api/chat", () => ({
  streamTicketEvents: (args: { conversationId: number }) => streamTicketEvents(args),
}));

import { TicketStatusBanner } from "../src/components/TicketStatusBanner";
import { useTicketStream } from "../src/hooks/useTicketStream";

beforeEach(() => streamTicketEvents.mockReset());
afterEach(() => vi.restoreAllMocks());

describe("useTicketStream", () => {
  it("opens stream and accumulates ticket events", async () => {
    streamTicketEvents.mockImplementation(async function* () {
      yield { type: "assigned", external_id: "AI-7" };
      yield { type: "resolved", external_id: "AI-7" };
      await new Promise(() => {}); // 长连不结束，避免重连
    });
    const { result } = renderHook(() => useTicketStream(7));
    expect(streamTicketEvents).toHaveBeenCalledWith({ conversationId: 7 });
    await waitFor(() =>
      expect(result.current.map((e) => e.event)).toEqual(["assigned", "resolved"]),
    );
  });

  it("does not open when conversationId is null", () => {
    renderHook(() => useTicketStream(null));
    expect(streamTicketEvents).not.toHaveBeenCalled();
  });

  it("stops accumulating after unmount", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    streamTicketEvents.mockImplementation(async function* () {
      yield { type: "assigned", external_id: "AI-1" };
      await gate;
      yield { type: "resolved", external_id: "AI-1" };
      await new Promise(() => {});
    });
    const { result, unmount } = renderHook(() => useTicketStream(1));
    await waitFor(() => expect(result.current.length).toBe(1));
    unmount();
    release();
    await new Promise((r) => setTimeout(r, 0));
    expect(result.current.map((e) => e.event)).toEqual(["assigned"]);
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
