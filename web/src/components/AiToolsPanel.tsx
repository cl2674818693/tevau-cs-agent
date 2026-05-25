import { useState } from "react";

import { runAiTool, type AiToolResult } from "../api/staff";
import { Alert } from "./ui/alert";
import { Button } from "./ui/button";
import { Textarea } from "./ui/input";

const TOOLS = ["query_user", "query_card", "query_api_call", "search_code", "lookup_api_doc"];

type Props = {
  token: string;
  convId: number;
};

/** 客服上下文工具面板：代查 AI 工具，结果只在面板显示、不进对话流。 */
export function AiToolsPanel({ token, convId }: Props) {
  const [tool, setTool] = useState(TOOLS[0]);
  const [paramsText, setParamsText] = useState("{}");
  const [result, setResult] = useState<AiToolResult | null>(null);
  const [err, setErr] = useState("");
  const [running, setRunning] = useState(false);

  async function run() {
    setErr("");
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(paramsText || "{}");
    } catch {
      setErr("参数不是合法 JSON");
      return;
    }
    setRunning(true);
    try {
      setResult(await runAiTool(token, convId, tool, params));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="rounded border border-line bg-surface-card p-3">
      <div className="mb-2 text-footnote text-ink-secondary">代查工具（结果仅你可见）</div>
      <select
        value={tool}
        onChange={(e) => setTool(e.target.value)}
        className="focus-glow mb-2 w-full rounded border border-line bg-surface-card px-2 py-2 text-body2 outline-none transition-all duration-250"
      >
        {TOOLS.map((t) => (
          <option key={t} value={t}>
            {t}
          </option>
        ))}
      </select>
      <Textarea
        value={paramsText}
        onChange={(e) => setParamsText(e.target.value)}
        rows={3}
        aria-label="工具参数 JSON"
        className="mb-2 px-2 py-1 text-body3 font-mono"
      />
      <Button size="sm" onClick={run} disabled={running}>
        {running ? "查询中…" : "运行"}
      </Button>
      {err && (
        <Alert variant="error" className="mt-2">
          {err}
        </Alert>
      )}
      {result && (
        <pre className="mt-2 max-h-60 overflow-auto rounded bg-surface-subtle p-2 text-footnote">
          {result.ok ? JSON.stringify(result.data, null, 2) : `错误：${result.error}`}
        </pre>
      )}
    </div>
  );
}
