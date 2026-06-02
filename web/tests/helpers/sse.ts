// SSE 流测试辅助：构造一个 ReadableStream，并把其包成 Response 形态。
// 后端走 sse-starlette，帧分隔符为 \r\n\r\n；事件格式：
//   event: <name>\r\n
//   data: <json>\r\n
//   id: <eventId>\r\n
//   \r\n

/** 把若干已序列化好的 SSE 帧组装成一个 ReadableStream<Uint8Array>，并立即结束。 */
export function sseStreamFromFrames(frames: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let i = 0;
  return new ReadableStream({
    pull(controller) {
      if (i < frames.length) {
        controller.enqueue(encoder.encode(frames[i++]));
      } else {
        controller.close();
      }
    },
  });
}

/** 帧序列化：每帧含 event + data（+ 可选 id），用 \r\n\r\n 分隔。 */
export function frame(event: string, data: unknown, id?: string): string {
  const lines = [`event: ${event}`, `data: ${JSON.stringify(data)}`];
  if (id !== undefined) lines.push(`id: ${id}`);
  return lines.join("\r\n") + "\r\n\r\n";
}

/** 直接返回一个 Response，body 为给定帧序列。Content-Type 不严格校验。 */
export function sseResponse(frames: string[]): Response {
  return new Response(sseStreamFromFrames(frames), {
    status: 200,
    headers: { "Content-Type": "text/event-stream" },
  });
}

/** 永不结束的 SSE 响应：用于"流挂着"的场景。close 可手动结束。 */
export function pendingSseResponse(): { resp: Response; close: () => void; push: (f: string) => void } {
  const encoder = new TextEncoder();
  let controller: ReadableStreamDefaultController<Uint8Array> | null = null;
  const stream = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return {
    resp: new Response(stream, {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    }),
    close: () => controller?.close(),
    push: (f: string) => controller?.enqueue(encoder.encode(f)),
  };
}
