import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  createDraft, deleteDraft, listDrafts, type PromptDraft, publishDraft,
} from "../../api/adminPromptEditor";
import { Badge } from "../../components/ui/badge";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { LoadingState } from "../../components/ui/spinner";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "../../components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../../components/ui/tabs";
import { Textarea } from "../../components/ui/textarea";
import { useStaffSession } from "../../hooks/useStaffSession";

const KNOWN_VERSIONS = ["v1.0.0", "v1.1.0", "v2.0.0"];

// ── 版本侧边栏 ──────────────────────────────────────────────────────────────

function VersionSidebar({
  versions,
  selected,
  onSelect,
  drafts,
}: {
  versions: string[];
  selected: string;
  onSelect: (v: string) => void;
  drafts: PromptDraft[];
}) {
  // group by version for draft count
  const draftVersions = new Set(drafts.filter((d) => d.status === "draft").map((d) => d.version));
  const publishedVersions = new Set(drafts.filter((d) => d.status === "published").map((d) => d.version));

  return (
    <aside className="hidden w-72 flex-col gap-1 border-r pr-4 md:flex">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">版本</p>
      {versions.map((v) => (
        <button
          key={v}
          onClick={() => onSelect(v)}
          className={[
            "flex items-center justify-between rounded-md px-3 py-2 text-sm transition-colors",
            selected === v
              ? "bg-primary text-primary-foreground"
              : "hover:bg-muted",
          ].join(" ")}
        >
          <span className="font-mono">{v}</span>
          <span className="flex gap-1">
            {draftVersions.has(v) && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">草稿</Badge>
            )}
            {publishedVersions.has(v) && (
              <Badge variant="success" className="text-[10px] px-1.5 py-0">已发布</Badge>
            )}
          </span>
        </button>
      ))}
    </aside>
  );
}

// ── 编辑器面板 ──────────────────────────────────────────────────────────────

function EditorPanel({
  version,
  drafts,
  onChanged,
}: {
  version: string;
  drafts: PromptDraft[];
  onChanged: () => void;
}) {
  const { token } = useStaffSession();

  // 当前选中的草稿（默认 first draft or null）
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [fname, setFname] = useState("reply_style.c.md");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState<number | null>(null);

  // 当版本切换时，把编辑框清空并重置选择
  useEffect(() => {
    setSelectedDraftId(null);
    setContent("");
    setFname("reply_style.c.md");
  }, [version]);

  // 选中某草稿时，把内容填入编辑框
  useEffect(() => {
    if (selectedDraftId === null) return;
    const d = drafts.find((x) => x.id === selectedDraftId);
    if (d) { setContent(d.content); setFname(d.file_name); }
  }, [selectedDraftId, drafts]);

  const selectedDraft = selectedDraftId !== null ? drafts.find((d) => d.id === selectedDraftId) : null;

  async function handleSave() {
    if (!token || !fname) return;
    setSaving(true);
    try {
      await createDraft(token, { version, file_name: fname, content });
      toast.success("草稿已保存");
      setContent("");
      setSelectedDraftId(null);
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish(id: number) {
    if (!token) return;
    setPublishing(id);
    try {
      await publishDraft(token, id);
      toast.success("已发布");
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "发布失败");
    } finally {
      setPublishing(null);
    }
  }

  async function handleDelete(id: number) {
    if (!token) return;
    try {
      await deleteDraft(token, id);
      toast.success("已删除");
      if (selectedDraftId === id) setSelectedDraftId(null);
      onChanged();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "删除失败");
    }
  }

  return (
    <Tabs defaultValue="editor" className="flex flex-1 flex-col gap-3">
      <TabsList className="self-start">
        <TabsTrigger value="editor">编辑器</TabsTrigger>
        <TabsTrigger value="history">历史版本</TabsTrigger>
      </TabsList>

      {/* ── Tab1: 编辑器 ── */}
      <TabsContent value="editor" className="flex flex-1 flex-col gap-3">
        {/* 状态行 */}
        <div className="flex flex-wrap items-center gap-3">
          <span className="font-mono text-sm font-semibold">{version}</span>
          {selectedDraft ? (
            <Badge variant={selectedDraft.status === "draft" ? "secondary" : "success"}>
              {selectedDraft.status === "draft" ? "草稿" : "已发布"}
            </Badge>
          ) : (
            <Badge variant="secondary">新草稿</Badge>
          )}
          <span className="flex-1" />
          <Input
            value={fname}
            onChange={(e) => setFname(e.target.value)}
            placeholder="文件名 reply_style.c.md"
            className="w-52 font-mono text-sm"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={handleSave}
            disabled={saving || !fname || !content}
          >
            {saving ? "保存中…" : "保存草稿"}
          </Button>
          {selectedDraft?.status === "draft" && (
            <Button
              size="sm"
              onClick={() => handlePublish(selectedDraft.id)}
              disabled={publishing === selectedDraft.id}
            >
              {publishing === selectedDraft.id ? "发布中…" : "发布"}
            </Button>
          )}
        </div>

        {/* 快速选已有草稿 */}
        {drafts.filter((d) => d.status === "draft").length > 0 && (
          <div className="flex flex-wrap gap-2">
            <span className="text-xs text-muted-foreground self-center">加载草稿：</span>
            {drafts.filter((d) => d.status === "draft").map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedDraftId(d.id)}
                className={[
                  "rounded border px-2 py-0.5 font-mono text-xs transition-colors",
                  selectedDraftId === d.id
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border hover:bg-muted",
                ].join(" ")}
              >
                #{d.id} {d.file_name}
              </button>
            ))}
          </div>
        )}

        {/* 编辑框 */}
        <Textarea
          className="min-h-[500px] flex-1 font-mono text-sm"
          placeholder="Prompt 内容（Markdown）"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          aria-label="Prompt 内容"
        />
      </TabsContent>

      {/* ── Tab2: 历史版本 ── */}
      <TabsContent value="history">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>ID</TableHead>
              <TableHead>文件</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>编辑人</TableHead>
              <TableHead>时间</TableHead>
              <TableHead>操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {drafts.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="text-center text-muted-foreground">
                  该版本无记录
                </TableCell>
              </TableRow>
            )}
            {drafts.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-mono">{d.id}</TableCell>
                <TableCell>{d.file_name}</TableCell>
                <TableCell>
                  <Badge variant={d.status === "draft" ? "secondary" : "success"}>
                    {d.status === "draft" ? "草稿" : "已发布"}
                  </Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{d.editor ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{d.created_at}</TableCell>
                <TableCell>
                  <div className="flex gap-2">
                    {d.status === "draft" && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="text-primary h-auto px-2 py-0.5 text-xs"
                        onClick={() => handlePublish(d.id)}
                        disabled={publishing === d.id}
                      >
                        发布
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive h-auto px-2 py-0.5 text-xs"
                      onClick={() => handleDelete(d.id)}
                    >
                      删除
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TabsContent>
    </Tabs>
  );
}

// ── 主路由 ──────────────────────────────────────────────────────────────────

export function PromptEditorRoute() {
  const { token, role } = useStaffSession();
  const allowed = role === "engineer" || role === "admin";
  const [version, setVersion] = useState("v2.0.0");
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [loading, setLoading] = useState(true);

  function reload() {
    if (!token) return;
    setLoading(true);
    listDrafts(token, version)
      .then(setDrafts)
      .catch(() => toast.error("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      toast.error("需要工程或管理员权限");
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, version]);

  return (
    <PageContainer width="wide">
      <PageHeader title="Prompt 编辑" />
      <div className="flex gap-6">
        {/* 左侧版本列表 */}
        {allowed && (
          <VersionSidebar
            versions={KNOWN_VERSIONS}
            selected={version}
            onSelect={setVersion}
            drafts={drafts}
          />
        )}

        {/* 右侧内容 */}
        <div className="flex flex-1 flex-col">
          {loading ? (
            <LoadingState />
          ) : allowed ? (
            <EditorPanel version={version} drafts={drafts} onChanged={reload} />
          ) : (
            <p className="text-muted-foreground">需要工程或管理员权限</p>
          )}
        </div>
      </div>
    </PageContainer>
  );
}
