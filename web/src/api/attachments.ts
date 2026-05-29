import { authHeaders } from "./identity";

async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = await authHeaders();
  return fetch(input, {
    ...init,
    credentials: "include",
    headers: { ...(init.headers ?? {}), ...auth },
  });
}

/** 看图端点（后端同源代理图片字节）。需带鉴权访问，<img> 不能直接当 src。 */
export function attachmentUrl(conversationId: number, attachmentId: number): string {
  return `/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
}

export function staffAttachmentUrl(conversationId: number, attachmentId: number): string {
  return `/staff/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
}

/**
 * 用户侧：带鉴权头取图片字节，转 objectURL 供 <img> 显示。
 * 裸 <img> GET 带不上 Bearer/X-Guest-ID 头会被 403，故走带鉴权 fetch。
 */
export async function resolveAttachmentSrc(endpoint: string): Promise<string> {
  const resp = await authedFetch(endpoint);
  if (!resp.ok) throw new Error(`view http ${resp.status}`);
  return URL.createObjectURL(await resp.blob());
}

/** 客服侧：Bearer 取图片字节，转 objectURL。 */
export async function resolveStaffAttachmentSrc(endpoint: string, token: string): Promise<string> {
  const resp = await fetch(endpoint, {
    credentials: "include",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) throw new Error(`staff view http ${resp.status}`);
  return URL.createObjectURL(await resp.blob());
}

/** 用户侧上传单张图，返回 attachment_id。multipart 不要手动设 Content-Type，浏览器自动带 boundary。 */
export async function uploadAttachment(conversationId: number, file: File): Promise<number> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await authedFetch(`/api/v1/conversations/${conversationId}/attachments`, {
    method: "POST",
    body: fd,
  });
  if (!resp.ok) throw new Error(`upload http ${resp.status}`);
  return (await resp.json()).attachment_id;
}

/** 客服侧上传单张图（Bearer token），返回 attachment_id。 */
export async function uploadStaffAttachment(
  conversationId: number,
  file: File,
  token: string,
): Promise<number> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetch(`/staff/api/v1/conversations/${conversationId}/attachments`, {
    method: "POST",
    credentials: "include",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!resp.ok) throw new Error(`staff upload http ${resp.status}`);
  return (await resp.json()).attachment_id;
}
