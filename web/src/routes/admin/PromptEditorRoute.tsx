import {
  App,
  Button,
  Card,
  Flex,
  Input,
  Skeleton,
  Space,
  Table,
  Tabs,
  Tag,
  Typography,
} from "antd";
import type { ColumnsType } from "antd/es/table";
import { useEffect, useMemo, useState } from "react";

import {
  createDraft,
  deleteDraft,
  listDrafts,
  type PromptDraft,
  publishDraft,
} from "../../api/adminPromptEditor";
import { useStaffSession } from "../../hooks/useStaffSession";

const { Title, Text } = Typography;
const { TextArea } = Input;

const KNOWN_VERSIONS = ["v1.0.0", "v1.1.0", "v2.0.0"];

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
  const draftVersions = new Set(
    drafts.filter((d) => d.status === "draft").map((d) => d.version),
  );
  const publishedVersions = new Set(
    drafts.filter((d) => d.status === "published").map((d) => d.version),
  );

  return (
    <div
      className="hidden md:block"
      style={{ width: 260, flexShrink: 0 }}
    >
      <Card size="small" title="版本">
        <Flex vertical gap="small">
          {versions.map((v) => (
            <Button
              key={v}
              type={selected === v ? "primary" : "text"}
              onClick={() => onSelect(v)}
              style={{ justifyContent: "space-between", textAlign: "left" }}
              block
            >
              <span style={{ fontFamily: "ui-monospace, monospace" }}>{v}</span>
              <Space size={4}>
                {draftVersions.has(v) && <Tag>草稿</Tag>}
                {publishedVersions.has(v) && <Tag color="green">已发布</Tag>}
              </Space>
            </Button>
          ))}
        </Flex>
      </Card>
    </div>
  );
}

function EditorTab({
  version,
  drafts,
  onChanged,
}: {
  version: string;
  drafts: PromptDraft[];
  onChanged: () => void;
}) {
  const { token } = useStaffSession();
  const { message } = App.useApp();
  const [selectedDraftId, setSelectedDraftId] = useState<number | null>(null);
  const [fname, setFname] = useState("reply_style.c.md");
  const [content, setContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [publishingId, setPublishingId] = useState<number | null>(null);

  useEffect(() => {
    setSelectedDraftId(null);
    setContent("");
    setFname("reply_style.c.md");
  }, [version]);

  useEffect(() => {
    if (selectedDraftId === null) return;
    const d = drafts.find((x) => x.id === selectedDraftId);
    if (d) {
      setContent(d.content);
      setFname(d.file_name);
    }
  }, [selectedDraftId, drafts]);

  const selectedDraft =
    selectedDraftId !== null ? drafts.find((d) => d.id === selectedDraftId) : null;

  async function handleSave() {
    if (!token || !fname) return;
    setSaving(true);
    try {
      await createDraft(token, { version, file_name: fname, content });
      message.success("草稿已保存");
      setContent("");
      setSelectedDraftId(null);
      onChanged();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish(id: number) {
    if (!token) return;
    setPublishingId(id);
    try {
      await publishDraft(token, id);
      message.success("已发布");
      onChanged();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "发布失败");
    } finally {
      setPublishingId(null);
    }
  }

  const draftsOfThisVersion = drafts.filter((d) => d.status === "draft");

  return (
    <div className="flex flex-col gap-3">
      <Flex wrap="wrap" align="center" gap="small">
        <Text strong style={{ fontFamily: "ui-monospace, monospace" }}>
          {version}
        </Text>
        {selectedDraft ? (
          <Tag color={selectedDraft.status === "draft" ? "default" : "green"}>
            {selectedDraft.status === "draft" ? "草稿" : "已发布"}
          </Tag>
        ) : (
          <Tag>新草稿</Tag>
        )}
        <div style={{ flex: 1 }} />
        <Input
          value={fname}
          onChange={(e) => setFname(e.target.value)}
          placeholder="文件名 reply_style.c.md"
          style={{
            width: 220,
            fontFamily: "ui-monospace, monospace",
            fontSize: 13,
          }}
        />
        <Button
          onClick={handleSave}
          loading={saving}
          disabled={!fname || !content}
        >
          保存草稿
        </Button>
        {selectedDraft?.status === "draft" && (
          <Button
            type="primary"
            onClick={() => handlePublish(selectedDraft.id)}
            loading={publishingId === selectedDraft.id}
          >
            发布
          </Button>
        )}
      </Flex>

      {draftsOfThisVersion.length > 0 && (
        <Flex wrap="wrap" gap="small" align="center">
          <Text type="secondary" style={{ fontSize: 12 }}>
            加载草稿：
          </Text>
          {draftsOfThisVersion.map((d) => (
            <Button
              key={d.id}
              size="small"
              type={selectedDraftId === d.id ? "primary" : "default"}
              onClick={() => setSelectedDraftId(d.id)}
              style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
            >
              #{d.id} {d.file_name}
            </Button>
          ))}
        </Flex>
      )}

      <TextArea
        rows={20}
        placeholder="Prompt 内容（Markdown）"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}
      />
    </div>
  );
}

function HistoryTab({
  drafts,
  onPublish,
  onDelete,
  publishingId,
}: {
  drafts: PromptDraft[];
  onPublish: (id: number) => void;
  onDelete: (id: number) => void;
  publishingId: number | null;
}) {
  const columns: ColumnsType<PromptDraft> = useMemo(
    () => [
      {
        title: "ID",
        dataIndex: "id",
        width: 60,
        render: (v: number) => (
          <span style={{ fontFamily: "ui-monospace, monospace" }}>{v}</span>
        ),
      },
      { title: "文件", dataIndex: "file_name" },
      {
        title: "状态",
        dataIndex: "status",
        width: 100,
        render: (s: string) =>
          s === "draft" ? <Tag>草稿</Tag> : <Tag color="green">已发布</Tag>,
      },
      {
        title: "编辑人",
        dataIndex: "editor",
        render: (v: string | null) => v ?? "—",
      },
      { title: "时间", dataIndex: "created_at" },
      {
        title: "操作",
        key: "actions",
        width: 140,
        render: (_: unknown, d: PromptDraft) => (
          <Space size="small">
            {d.status === "draft" && (
              <Button
                type="link"
                size="small"
                onClick={() => onPublish(d.id)}
                loading={publishingId === d.id}
                style={{ padding: 0 }}
              >
                发布
              </Button>
            )}
            <Button
              type="link"
              size="small"
              danger
              onClick={() => onDelete(d.id)}
              style={{ padding: 0 }}
            >
              删除
            </Button>
          </Space>
        ),
      },
    ],
    [onPublish, onDelete, publishingId],
  );

  return (
    <Table<PromptDraft>
      rowKey="id"
      size="small"
      columns={columns}
      dataSource={drafts}
      pagination={false}
      locale={{ emptyText: "该版本无记录" }}
      scroll={{ x: "max-content" }}
    />
  );
}

export function PromptEditorRoute() {
  const { token, role } = useStaffSession();
  const { message } = App.useApp();
  const allowed = role === "engineer" || role === "admin";
  const [version, setVersion] = useState("v2.0.0");
  const [drafts, setDrafts] = useState<PromptDraft[]>([]);
  const [loading, setLoading] = useState(true);
  const [publishingId, setPublishingId] = useState<number | null>(null);

  function reload() {
    if (!token) return;
    setLoading(true);
    listDrafts(token, version)
      .then(setDrafts)
      .catch(() => message.error("加载失败"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token || !allowed) {
      setLoading(false);
      return;
    }
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, role, version]);

  async function handlePublish(id: number) {
    if (!token) return;
    setPublishingId(id);
    try {
      await publishDraft(token, id);
      message.success("已发布");
      reload();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "发布失败");
    } finally {
      setPublishingId(null);
    }
  }

  async function handleDelete(id: number) {
    if (!token) return;
    try {
      await deleteDraft(token, id);
      message.success("已删除");
      reload();
    } catch (e) {
      message.error(e instanceof Error ? e.message : "删除失败");
    }
  }

  return (
    <div className="space-y-4 p-6">
      <Title level={3} style={{ margin: 0 }}>
        Prompt 编辑
      </Title>
      <Flex gap="middle" align="flex-start">
        {allowed && (
          <VersionSidebar
            versions={KNOWN_VERSIONS}
            selected={version}
            onSelect={setVersion}
            drafts={drafts}
          />
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          {loading ? (
            <Card>
              <Skeleton active paragraph={{ rows: 10 }} />
            </Card>
          ) : allowed ? (
            <Card>
              <Tabs
                defaultActiveKey="editor"
                items={[
                  {
                    key: "editor",
                    label: "编辑器",
                    children: (
                      <EditorTab
                        version={version}
                        drafts={drafts}
                        onChanged={reload}
                      />
                    ),
                  },
                  {
                    key: "history",
                    label: "历史版本",
                    children: (
                      <HistoryTab
                        drafts={drafts}
                        onPublish={handlePublish}
                        onDelete={handleDelete}
                        publishingId={publishingId}
                      />
                    ),
                  },
                ]}
              />
            </Card>
          ) : (
            <Card>
              <Text type="secondary">需要工程或管理员权限</Text>
            </Card>
          )}
        </div>
      </Flex>
    </div>
  );
}
