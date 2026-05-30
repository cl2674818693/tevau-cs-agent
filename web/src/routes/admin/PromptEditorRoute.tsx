import { useEffect, useState } from "react";

import {
  createDraft, deleteDraft, listDrafts, type PromptDraft, publishDraft,
} from "../../api/adminPromptEditor";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const KNOWN_VERSIONS = ["v1.0.0", "v1.1.0", "v2.0.0"];

function DraftEditor({ version, onCreated, onError }: {
  version: string; onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [fname, setFname] = useState("reply_style.c.md");
  const [content, setContent] = useState("");
  async function submit() {
    if (!token || !fname) return;
    try {
      await createDraft(token, { version, file_name: fname, content });
      setContent("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <Input placeholder="文件名 reply_style.c.md" value={fname} className="w-72"
            onChange={(e) => setFname(e.target.value)} />
          <Button size="md" onClick={submit} disabled={!fname || !content}>新建草稿</Button>
        </div>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={8} placeholder="Prompt 内容（Markdown）" value={content}
          aria-label="Prompt 内容"
          onChange={(e) => setContent(e.target.value)} />
      </div>
    </Card>
  );
}

function DraftRow({ d, onChanged, onError }: {
  d: PromptDraft; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function pub() {
    if (!token) return;
    try { await publishDraft(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "发布失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteDraft(token, d.id); onChanged(); }
    catch (e) { onError(e instanceof Error ? e.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{d.id}</td>
      <td className="px-3 py-2 text-ink-primary">{d.file_name}</td>
      <td className="px-3 py-2">{d.status}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.editor ?? "—"}</td>
      <td className="px-3 py-2 text-ink-tertiary">{d.created_at}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          {d.status === "draft" && <button className="text-brand" onClick={pub}>发布</button>}
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

function DraftsTable({ drafts, onChanged, onError }: {
  drafts: PromptDraft[]; onChanged: () => void; onError: (m: string) => void;
}) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">ID</th>
            <th className="px-3 py-2 text-left font-normal">文件</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">编辑人</th>
            <th className="px-3 py-2 text-left font-normal">时间</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {drafts.length === 0 && (
            <tr><td colSpan={6} className="px-3 py-4 text-center text-ink-tertiary">该版本无草稿</td></tr>
          )}
          {drafts.map((d) => <DraftRow key={d.id} d={d} onChanged={onChanged} onError={onError} />)}
        </tbody>
      </table>
    </Card>
  );
}

export function PromptEditorRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [version, setVersion] = useState("v2.0.0");
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listDrafts(token, version).then(setDrafts).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要工程或管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, version]);

  return (
    <PageContainer width="wide">
      <PageHeader title="Prompt 在线编辑" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && (
        <Card className="mb-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <span className="text-body3 text-ink-secondary">版本：</span>
            <select value={version} onChange={(e) => setVersion(e.target.value)}
              className="rounded border border-line px-2 py-1 text-body2">
              {KNOWN_VERSIONS.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
        </Card>
      )}
      {allowed && <DraftEditor version={version} onCreated={reload} onError={setErr} />}
      {loading ? <LoadingState /> : allowed && (
        <DraftsTable drafts={drafts} onChanged={reload} onError={setErr} />
      )}
    </PageContainer>
  );
}
