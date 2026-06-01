import { useEffect, useMemo, useState } from "react";

import { getPromptAbStats, getPromptVersions, type PromptAbStat } from "../../api/admin";
import { DataTable } from "../../components/admin/data-table/DataTable";
import { DataTableToolbar } from "../../components/admin/data-table/DataTableToolbar";
import { Alert } from "../../components/ui/alert";
import { PageContainer, PageHeader } from "../../components/ui/page";
import { Skeleton } from "../../components/ui/skeleton";
import { useStaffSession } from "../../hooks/useStaffSession";
import { buildPromptColumns, type PromptRow } from "./PromptsRoute.columns";
import { RolloutSheet } from "./PromptsRoute.rolloutSheet";

// ── Types / helpers ───────────────────────────────────────────────────────────

type WindowOption = "7d" | "30d";

function windowFrom(opt: WindowOption): string {
  const days = opt === "7d" ? 7 : 30;
  const ms = Date.now() - days * 24 * 60 * 60 * 1000;
  return new Date(ms).toISOString().slice(0, 19).replace("T", " ");
}

// ── Skeleton ─────────────────────────────────────────────────────────────────

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full rounded-md" />
      ))}
    </div>
  );
}

// ── Data hook ─────────────────────────────────────────────────────────────────

function usePromptsData(token: string | null, role: string | null, abWindow: WindowOption) {
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
      .then((d) => { setDefaultVersion(d.default); setRollout(d.rollout); })
      .catch(() => setLoadError("加载失败"))
      .finally(() => setLoading(false));
  }, [token, role]);

  useEffect(() => {
    if (!token || role !== "admin") return;
    getPromptAbStats(token, { from: windowFrom(abWindow) })
      .then((d) => setAbStats(d.versions))
      .catch(() => { /* non-critical */ });
  }, [token, role, abWindow]);

  return { defaultVersion, rollout, setRollout, loadError, loading, abStats };
}

// ── Route ─────────────────────────────────────────────────────────────────────

export function PromptsRoute() {
  const { token, role } = useStaffSession();
  const [abWindow, setAbWindow] = useState<WindowOption>("7d");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editingRow, setEditingRow] = useState<PromptRow | null>(null);

  const { defaultVersion, rollout, setRollout, loadError, loading, abStats } =
    usePromptsData(token, role, abWindow);

  const rows: PromptRow[] = useMemo(() => {
    const statMap = new Map(abStats.map((s) => [s.version, s]));
    return Object.keys(rollout).map((v) => ({
      version: v,
      rollout: rollout[v] ?? 0,
      isDefault: v === defaultVersion,
      stat: statMap.get(v),
    }));
  }, [rollout, defaultVersion, abStats]);

  const columns = useMemo(
    () => buildPromptColumns((row) => { setEditingRow(row); setSheetOpen(true); }),
    [],
  );

  const windowToggle = (
    <div className="flex items-center gap-1">
      {(["7d", "30d"] as WindowOption[]).map((opt) => (
        <button
          key={opt}
          onClick={() => setAbWindow(opt)}
          className={[
            "rounded px-2 py-0.5 text-xs transition-colors",
            abWindow === opt ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
          ].join(" ")}
        >
          {opt === "7d" ? "近 7 天" : "近 30 天"}
        </button>
      ))}
    </div>
  );

  return (
    <PageContainer width="wide">
      <PageHeader title="Prompt 灰度" actions={windowToggle} />
      {loadError && <Alert variant="destructive" className="mb-4">{loadError}</Alert>}
      {loading ? (
        <TableSkeleton />
      ) : (
        <DataTable
          columns={columns}
          data={rows}
          toolbar={(t) => (
            <DataTableToolbar table={t} searchColumn="version" placeholder="搜索版本…" />
          )}
        />
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
    </PageContainer>
  );
}
