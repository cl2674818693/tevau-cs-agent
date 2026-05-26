import { authHeaders } from "./identity";

async function authedFetch(input: string, init: RequestInit = {}): Promise<Response> {
  const auth = await authHeaders();
  return fetch(input, {
    ...init,
    credentials: "include",
    headers: { ...(init.headers ?? {}), ...auth },
  });
}

/** 用户/客服侧看图 URL（浏览器自动跟随 302 到预签名 URL）。 */
export function attachmentUrl(conversationId: number, attachmentId: number): string {
  return `/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
}

export function staffAttachmentUrl(conversationId: number, attachmentId: number): string {
  return `/staff/api/v1/conversations/${conversationId}/attachments/${attachmentId}`;
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
