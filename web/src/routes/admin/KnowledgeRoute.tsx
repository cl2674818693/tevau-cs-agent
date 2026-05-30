import { useEffect, useState } from "react";

import {
  createKnowledge, deleteKnowledge, type KnowledgeEntry, listKnowledge, publishKnowledge,
} from "../../api/adminKnowledge";
import { Alert } from "../../components/ui/alert";
import { Button } from "../../components/ui/button";
import { Card } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import { useStaffSession } from "../../hooks/useStaffSession";

const TYPES = ["api_doc", "error_code", "faq"];

function EntryForm({ onCreated, onError }: {
  onCreated: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  const [type, setType] = useState("faq");
  const [key, setKey] = useState("");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  async function submit() {
    if (!token || !key || !title) return;
    try {
      await createKnowledge(token, { type, key, title, content });
      setKey(""); setTitle(""); setContent("");
      onCreated();
    } catch (e) { onError(e instanceof Error ? e.message : "创建失败"); }
  }
  return (
    <Card>
      <div className="flex flex-col gap-2 px-page py-block-sm">
        <div className="flex flex-wrap items-end gap-2">
          <select value={type} onChange={(e) => setType(e.target.value)}
            className="rounded border border-line px-2 py-1 text-body2">
            {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <Input placeholder="key（错误码/路径/slug）" value={key} className="w-56"
            onChange={(e) => setKey(e.target.value)} />
          <Input placeholder="标题" value={title} className="w-72"
            onChange={(e) => setTitle(e.target.value)} />
          <Button size="md" onClick={submit} disabled={!key || !title}>新建草稿</Button>
        </div>
        <textarea className="rounded border border-line px-2 py-1 font-mono text-body3"
          rows={5} placeholder="内容（Markdown）" value={content}
          aria-label="内容"
          onChange={(e) => setContent(e.target.value)} />
      </div>
    </Card>
  );
}

function EntryRow({ e, onChanged, onError }: {
  e: KnowledgeEntry; onChanged: () => void; onError: (m: string) => void;
}) {
  const { token } = useStaffSession();
  async function pub() {
    if (!token) return;
    try { await publishKnowledge(token, e.id); onChanged(); }
    catch (err) { onError(err instanceof Error ? err.message : "发布失败"); }
  }
  async function rm() {
    if (!token) return;
    try { await deleteKnowledge(token, e.id); onChanged(); }
    catch (err) { onError(err instanceof Error ? err.message : "删除失败"); }
  }
  return (
    <tr className="border-b border-line last:border-0">
      <td className="px-3 py-2">{e.id}</td>
      <td className="px-3 py-2">{e.type}</td>
      <td className="px-3 py-2 text-ink-primary">{e.key}</td>
      <td className="px-3 py-2 text-ink-secondary">{e.title}</td>
      <td className="px-3 py-2">{e.status}</td>
      <td className="px-3 py-2 text-ink-tertiary">{e.source_gap_signal ?? "—"}</td>
      <td className="px-3 py-2">
        <div className="flex gap-2">
          {e.status === "draft" && <button className="text-brand" onClick={pub}>发布</button>}
          <button className="text-status-error" onClick={rm}>删除</button>
        </div>
      </td>
    </tr>
  );
}

function EntriesTable({ entries, onChanged, onError }: {
  entries: KnowledgeEntry[]; onChanged: () => void; onError: (m: string) => void;
}) {
  return (
    <Card className="mt-3">
      <table className="w-full text-body3">
        <thead>
          <tr className="border-b border-line text-ink-secondary">
            <th className="px-3 py-2 text-left font-normal">ID</th>
            <th className="px-3 py-2 text-left font-normal">类型</th>
            <th className="px-3 py-2 text-left font-normal">key</th>
            <th className="px-3 py-2 text-left font-normal">标题</th>
            <th className="px-3 py-2 text-left font-normal">状态</th>
            <th className="px-3 py-2 text-left font-normal">来源</th>
            <th className="px-3 py-2 text-left font-normal">操作</th>
          </tr>
        </thead>
        <tbody>
          {entries.length === 0 && (
            <tr><td colSpan={7} className="px-3 py-4 text-center text-ink-tertiary">无</td></tr>
          )}
          {entries.map((e) => <EntryRow key={e.id} e={e} onChanged={onChanged} onError={onError} />)}
        </tbody>
      </table>
    </Card>
  );
}

export function KnowledgeRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "supervisor" || role === "engineer" || role === "admin";
  const [filter, setFilter] = useState("");
  const [entries, setEntries] = useState<KnowledgeEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");

  function reload() {
    if (!token) return;
    setLoading(true);
    listKnowledge(token, filter ? { type: filter } : undefined)
      .then(setEntries).catch(() => setErr("加载失败")).finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) { setErr("需要主管/工程/管理员权限"); setLoading(false); return; }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, filter]);

  return (
    <PageContainer width="wide">
      <PageHeader title="知识库" />
      {err && <Alert variant="error" className="mb-2">{err}</Alert>}
      {allowed && <EntryForm onCreated={reload} onError={setErr} />}
      {allowed && (
        <Card className="mt-3">
          <div className="flex items-end gap-2 px-page py-block-sm">
            <select value={filter} onChange={(e) => setFilter(e.target.value)}
              className="rounded border border-line px-2 py-1 text-body2">
              <option value="">全部类型</option>
              {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </Card>
      )}
      {loading ? <LoadingState /> : allowed && (
        <EntriesTable entries={entries} onChanged={reload} onError={setErr} />
      )}
    </PageContainer>
  );
}
