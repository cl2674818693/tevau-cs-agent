import {
  Alert,
  Card,
  Flex,
  Input,
  Segmented,
  Skeleton,
  Table,
  Typography,
} from "antd";
import { useEffect, useMemo, useState } from "react";

import {
  getPromptAbStats,
  getPromptVersions,
  type PromptAbStat,
} from "../../api/admin";
import { useStaffSession } from "../../hooks/useStaffSession";

import { buildPromptColumns, type PromptRow } from "./PromptsRoute.columns";
import { RolloutSheet } from "./PromptsRoute.rolloutSheet";

const { Title } = Typography;

type WindowOption = "7d" | "30d";

function windowFrom(opt: WindowOption): string {
  const days = opt === "7d" ? 7 : 30;
  const ms = Date.now() - days * 24 * 60 * 60 * 1000;
  return new Date(ms).toISOString().slice(0, 19).replace("T", " ");
}

function usePromptsData(
  token: string | null,
  role: string | null,
  abWindow: WindowOption,
) {
  const [defaultVersion, setDefaultVersion] = useState("");
  const [rollout, setRollout] = useState<Record<string, number>>({});
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);
  const [abStats, setAbStats] = useState<PromptAbStat[]>([]);

  useEffect(() => {
    if (!token || role !== "admin") {
      setLoadError("需要 admin 权限");
      setLoading(false);
      return;
    }
    setLoading(true);
    getPromptVersions(token)
      .then((d) => {
        setDefaultVersion(d.default);
        setRollout(d.rollout);
      })
      .catch(() => setLoadError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, role]);

  useEffect(() => {
    if (!token || role !== "admin") return;
    getPromptAbStats(token, { from: windowFrom(abWindow) })
      .then((d) => setAbStats(d.versions))
      .catch(() => {
        /* non-critical */
      });
  }, [token, role, abWindow]);

  return { defaultVersion, rollout, setRollout, loadError, loading, abStats };
}

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const [abWindow, setAbWindow] = useState<WindowOption>("7d");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<PromptRow | null>(null);
  const [search, setSearch] = useState("");

  const { defaultVersion, rollout, setRollout, loadError, loading, abStats } =
    usePromptsData(token, role, abWindow);

  const rows: PromptRow[] = useMemo(() => {
    const statMap = new Map(abStats.map((s) => [s.version, s]));
    const kw = search.trim().toLowerCase();
    return Object.keys(rollout)
      .filter((v) => !kw || v.toLowerCase().includes(kw))
      .map((v) => ({
        version: v,
        rollout: rollout[v] ?? 0,
        isDefault: v === defaultVersion,
        stat: statMap.get(v),
      }));
  }, [rollout, defaultVersion, abStats, search]);

  const columns = useMemo(
    () =>
      buildPromptColumns((row) => {
        setEditingRow(row);
        setSheetOpen(true);
      }),
    [],
  );

  return (
    <div className="space-y-4 p-6">
      <Flex justify="space-between" align="flex-start" wrap="wrap" gap="middle">
        <Title level={3} style={{ margin: 0 }}>
          Prompt 灰度
        </Title>
        <Segmented<WindowOption>
          value={abWindow}
          onChange={setAbWindow}
          options={[
            { value: "7d", label: "近 7 天" },
            { value: "30d", label: "近 30 天" },
          ]}
        />
      </Flex>

      {loadError && <Alert type="error" showIcon title={loadError} />}

      {loading ? (
        <Card>
          <Skeleton active paragraph={{ rows: 4 }} />
        </Card>
      ) : (
        <Card>
          <Flex style={{ marginBottom: 12 }}>
            <Input.Search
              placeholder="搜索版本…"
              allowClear
              style={{ width: 240 }}
              onChange={(e) => setSearch(e.target.value)}
            />
          </Flex>
          <Table<PromptRow>
            rowKey="version"
            size="middle"
            columns={columns}
            dataSource={rows}
            pagination={false}
            locale={{ emptyText: "无版本配置" }}
          />
        </Card>
      )}

      {token && (
        <RolloutSheet
          open={sheetOpen}
          onOpenChange={setSheetOpen}
          row={editingRow}
          token={token}
          currentRollout={rollout}
          onSuccess={setRollout}
        />
      )}
    </div>
  );
}
