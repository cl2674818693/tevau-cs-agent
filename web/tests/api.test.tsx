import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { cancelStream, initConversation, sendFeedback, streamChat } from "../src/api/chat";
import { ChatRoute } from "../src/routes/ChatRoute";

afterEach(() => vi.restoreAllMocks());

const INIT_JSON = {
  conversation_id: 1,
  user_type: "b",
  display_name: "X",
  greeting: "您好",
  history_url: null,
  limits: { daily_token_used_pct: 0, max_turns: 20 },
};

function sseResponse(frames: string[]): Response {
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      const enc = new TextEncoder();
      for (const f of frames) c.enqueue(enc.encode(f));
      c.close();
    },
  });
  return new Response(body, { status: 200 });
}

describe("api/chat", () => {
  it("initConversation posts and returns json", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (_url: string, _opts?: RequestInit) =>
          new Response(JSON.stringify(INIT_JSON), { status: 200 }),
      ),
    );
    const info = await initConversation();
    expect(info.conversation_id).toBe(1);
  });

  it("streamChat parses SSE frames and skips ping", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        sseResponse([
          'event: conversation\ndata: {"conversation_id":1}\nid: a\n\n',
          "event: ping\ndata: \n\n",
          'event: content_block_delta\ndata: {"delta":{"text":"hi"}}\n\n',
        ]),
      ),
    );
    const types: string[] = [];
    for await (const ev of streamChat({ conversationId: 1, message: "x" })) {
      types.push(ev.type);
    }
    expect(types).toEqual(["conversation", "content_block_delta"]);
  });

  it("streamChat appends client_message_id to url", async () => {
    const f = vi.fn(async (_url: string, _opts?: RequestInit) =>
      sseResponse(['event: message_stop\ndata: {"stop_reason":"x"}\n\n']),
    );
    vi.stubGlobal("fetch", f);
    const types: string[] = [];
    for await (const ev of streamChat({
      conversationId: 1,
      message: "x",
      clientMessageId: "cm-9",
    })) {
      types.push(ev.type);
    }
    expect(f.mock.calls[0][0]).toContain("client_message_id=cm-9");
  });

  it("sendFeedback posts rating", async () => {
    const f = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 200 }),
    );
    vi.stubGlobal("fetch", f);
    await sendFeedback(1, 3, "down", "答非所问");
    expect(f.mock.calls[0][0]).toBe("/api/v1/conversations/1/feedback");
    const body = JSON.parse((f.mock.calls[0][1] as RequestInit).body as string);
    expect(body).toMatchObject({ message_id: 3, rating: "down", reason: "答非所问" });
  });

  it("cancelStream sends DELETE", async () => {
    const f = vi.fn(
      async (_url: string, _opts?: RequestInit) => new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", f);
    await cancelStream(1);
    expect((f.mock.calls[0][1] as RequestInit).method).toBe("DELETE");
  });
});

describe("ChatRoute", () => {
  it("renders the chat window", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async (_url: string, _opts?: RequestInit) =>
          new Response(JSON.stringify(INIT_JSON), { status: 200 }),
      ),
    );
    render(<ChatRoute />);
    await waitFor(() => expect(screen.getByPlaceholderText("描述你的问题…")).toBeTruthy());
  });
});
