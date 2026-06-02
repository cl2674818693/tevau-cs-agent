// chat API（streamChat / streamConversationMessages / fetchHistory / ...）的 URL + SSE 解析行为。
// SSE 帧分隔符必须兼容 \r\n\r\n（sse-starlette 默认）和 \n\n。
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  cancelStream,
  fetchHistory,
  initConversation,
  reportClientInfo,
  requestHuman,
  sendFeedback,
  sendTicketUserEvent,
  streamChat,
  streamConversationMessages,
} from "@/api/chat";

import { clearLocalStorage } from "../../_helpers/storage";

function sseBody(frames: string[], sep = "\n\n"): ReadableStream<Uint8Array> {
  const data = frames.join(sep) + sep;
  const enc = new TextEncoder().encode(data);
  return new ReadableStream({
    start(controller) {
      controller.enqueue(enc);
      controller.close();
    },
  });
}

async function collect<T>(it: AsyncGenerator<T>): Promise<T[]> {
  const out: T[] = [];
  for await (const ev of it) out.push(ev);
  return out;
}

describe("chat API", () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    clearLocalStorage();
    fetchMock = vi.fn();
    vi.spyOn(globalThis, "fetch").mockImplementation(fetchMock as unknown as typeof fetch);
  });
  afterEach(() => vi.restoreAllMocks());

  describe("initConversation", () => {
    it("不传 resume 时 body={}", async () => {
      fetchMock.mockResolvedValue(new Response('{"conversation_id":1}', { status: 200 }));
      const r = await initConversation();
      expect(r.conversation_id).toBe(1);
      const args = fetchMock.mock.calls[0];
      expect(args[0]).toBe("/api/v1/conversations");
      expect(args[1].method).toBe("POST");
      expect(args[1].body).toBe("{}");
    });

    it("传 resume 时 body 包含 resume id", async () => {
      fetchMock.mockResolvedValue(new Response('{"conversation_id":7}', { status: 200 }));
      await initConversation(42);
      expect(fetchMock.mock.calls[0][1].body).toContain('"resume":42');
    });

    it("非 2xx 抛错", async () => {
      fetchMock.mockResolvedValue(new Response("", { status: 500 }));
      await expect(initConversation()).rejects.toThrow(/init http 500/);
    });
  });

  describe("fetchHistory", () => {
    it("成功返回 messages 数组", async () => {
      fetchMock.mockResolvedValue(
        new Response(JSON.stringify({ messages: [{ role: "user", content: "x" }] }), {
          status: 200,
        }),
      );
      const out = await fetchHistory("/some/url");
      expect(out).toEqual([{ role: "user", content: "x" }]);
    });

    it("非 ok 返回空数组（不抛）", async () => {
      fetchMock.mockResolvedValue(new Response("", { status: 500 }));
      expect(await fetchHistory("/x")).toEqual([]);
    });

    it("网络抛错时返回空数组", async () => {
      fetchMock.mockRejectedValue(new Error("net"));
      expect(await fetchHistory("/x")).toEqual([]);
    });
  });

  describe("streamChat URL + SSE", () => {
    it("URL 携带 conversation_id / encoded message / ui_locale / client_message_id / attachment_ids", async () => {
      fetchMock.mockResolvedValue(
        new Response(sseBody([]), {
          status: 200,
          headers: { "content-type": "text/event-stream" },
        }),
      );
      await collect(
        streamChat({
          conversationId: 5,
          message: "你 好 & q",
          clientMessageId: "cm-1",
          attachmentIds: [1, 2, 3],
        }),
      );
      const url = fetchMock.mock.calls[0][0] as string;
      expect(url).toContain("conversation_id=5");
      expect(url).toContain("message=" + encodeURIComponent("你 好 & q"));
      expect(url).toContain("ui_locale=");
      expect(url).toContain("client_message_id=cm-1");
      expect(url).toContain("attachment_ids=1,2,3");
    });

    it("传 lastEventId 时 header 加 Last-Event-ID", async () => {
      fetchMock.mockResolvedValue(
        new Response(sseBody([]), { status: 200 }),
      );
      await collect(
        streamChat({ conversationId: 1, message: "x", lastEventId: "ev-9" }),
      );
      const init = fetchMock.mock.calls[0][1];
      expect(init.headers["Last-Event-ID"]).toBe("ev-9");
    });

    it("解析 \\n\\n 分隔的 SSE 帧", async () => {
      const frames = [
        "event: assistant_message\ndata: {\"content\":\"hello\"}",
        "event: message_stop\ndata: {\"stop_reason\":\"end\"}",
      ];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\n\n"), { status: 200 }));
      const out = await collect(streamChat({ conversationId: 1, message: "x" }));
      expect(out).toHaveLength(2);
      expect(out[0]).toMatchObject({ type: "assistant_message", content: "hello" });
    });

    it("解析 \\r\\n\\r\\n 分隔的 SSE 帧（sse-starlette 默认）", async () => {
      const frames = [
        "event: assistant_message\r\ndata: {\"content\":\"x\"}",
      ];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\r\n\r\n"), { status: 200 }));
      const out = await collect(streamChat({ conversationId: 1, message: "x" }));
      expect(out).toHaveLength(1);
      expect(out[0]).toMatchObject({ type: "assistant_message" });
    });

    it("ping 心跳帧被过滤", async () => {
      const frames = [
        "event: ping\ndata: {}",
        "event: assistant_message\ndata: {\"content\":\"y\"}",
      ];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\n\n"), { status: 200 }));
      const out = await collect(streamChat({ conversationId: 1, message: "x" }));
      expect(out).toHaveLength(1);
      expect(out[0]).toMatchObject({ type: "assistant_message" });
    });

    it("无 data 行 / 坏 JSON → 跳过该帧不抛", async () => {
      const frames = [
        "event: assistant_message", // 缺 data
        "event: assistant_message\ndata: not json",
        "event: assistant_message\ndata: {\"content\":\"ok\"}",
      ];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\n\n"), { status: 200 }));
      const out = await collect(streamChat({ conversationId: 1, message: "x" }));
      expect(out).toHaveLength(1);
    });

    it("带 id: 行的帧把 _eventId 透传", async () => {
      const frames = ["id: 12\nevent: assistant_message\ndata: {\"content\":\"y\"}"];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\n\n"), { status: 200 }));
      const out = await collect(streamChat({ conversationId: 1, message: "x" }));
      expect((out[0] as { _eventId?: string })._eventId).toBe("12");
    });

    it("响应非 200 抛错", async () => {
      fetchMock.mockResolvedValue(new Response("", { status: 500 }));
      await expect(
        collect(streamChat({ conversationId: 1, message: "x" })),
      ).rejects.toThrow(/chat http 500/);
    });
  });

  describe("streamConversationMessages 常驻流", () => {
    it("调正确 URL + 解析事件", async () => {
      const frames = ["event: human_message\ndata: {\"content\":\"您好\"}"];
      fetchMock.mockResolvedValue(new Response(sseBody(frames, "\n\n"), { status: 200 }));
      const out = await collect(streamConversationMessages({ conversationId: 9 }));
      const url = fetchMock.mock.calls[0][0] as string;
      expect(url).toBe("/api/v1/conversations/9/messages-stream");
      expect(out[0]).toMatchObject({ type: "human_message", content: "您好" });
    });

    it("响应非 200 抛错", async () => {
      fetchMock.mockResolvedValue(new Response("", { status: 401 }));
      await expect(
        collect(streamConversationMessages({ conversationId: 1 })),
      ).rejects.toThrow(/messages-stream http 401/);
    });
  });

  describe("其它写操作", () => {
    it("sendFeedback POST 正确 body", async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
      await sendFeedback(1, 2, "up", "好");
      expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/conversations/1/feedback");
      const body = JSON.parse(fetchMock.mock.calls[0][1].body);
      expect(body).toEqual({ message_id: 2, rating: "up", reason: "好" });
    });

    it("cancelStream DELETE", async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
      await cancelStream(5);
      expect(fetchMock.mock.calls[0][1].method).toBe("DELETE");
      expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/chat/5/stream");
    });

    it("requestHuman 默认 reason", async () => {
      fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
      await requestHuman(7);
      expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ reason: expect.any(String) });
    });

    it("reportClientInfo 失败静默不抛", async () => {
      fetchMock.mockRejectedValue(new Error("net"));
      await expect(reportClientInfo(1, { platform: "ios" })).resolves.toBeUndefined();
    });

    it("sendTicketUserEvent POST 正确 url + body", async () => {
      fetchMock.mockResolvedValue(new Response("", { status: 200 }));
      await sendTicketUserEvent("T-1", "user_confirmed_resolved");
      expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/tickets/T-1/user-events");
      expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({
        event: "user_confirmed_resolved",
      });
    });
  });
});
