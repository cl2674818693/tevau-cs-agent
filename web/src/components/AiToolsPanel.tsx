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
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 text-xs font-medium text-muted-foreground">代查工具（结果仅你可见）</div>
      <select
        value={tool}
        onChange={(e) => setTool(e.target.value)}
        className="mb-2 w-full rounded-md border border-input bg-background px-2 py-2 text-sm outline-none transition-colors focus:border-ring focus:ring-1 focus:ring-ring"
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
        className="mb-2 px-2 py-1 text-xs font-mono"
      />
      <Button size="sm" onClick={run} disabled={running}>
        {running ? "查询中…" : "运行"}
      </Button>
      {err && (
        <Alert variant="destructive" className="mt-2">
          {err}
        </Alert>
      )}
      {result && (
        <pre className="mt-2 max-h-60 overflow-auto rounded-md bg-muted p-2 text-xs">
          {result.ok ? JSON.stringify(result.data, null, 2) : `错误：${result.error}`}
        </pre>
      )}
    </div>
  );
}
