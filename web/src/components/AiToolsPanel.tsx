import { Alert, Button, Card, Input, Select, Typography } from "antd";
import { useState } from "react";

import { runAiTool, type AiToolResult } from "../api/staff";

const { TextArea } = Input;
const { Text } = Typography;

const TOOLS = [
  "query_user",
  "query_card",
  "query_api_call",
  "search_code",
  "lookup_api_doc",
];

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
    <Card
      size="small"
      title={
        <Text type="secondary" style={{ fontSize: 12 }}>
          代查工具（结果仅你可见）
        </Text>
      }
    >
      <Select
        value={tool}
        onChange={setTool}
        style={{ width: "100%", marginBottom: 8 }}
        options={TOOLS.map((t) => ({ value: t, label: t }))}
      />
      <TextArea
        value={paramsText}
        onChange={(e) => setParamsText(e.target.value)}
        rows={3}
        aria-label="工具参数 JSON"
        style={{
          marginBottom: 8,
          fontFamily: "ui-monospace, monospace",
          fontSize: 12,
        }}
      />
      <Button type="primary" size="small" onClick={run} loading={running}>
        运行
      </Button>
      {err && (
        <Alert
          type="error"
          showIcon
          title={err}
          style={{ marginTop: 8 }}
        />
      )}
      {result && (
        <pre
          style={{
            marginTop: 8,
            maxHeight: 240,
            overflow: "auto",
            borderRadius: 6,
            background: "rgba(0,0,0,0.03)",
            padding: 8,
            fontSize: 12,
          }}
        >
          {result.ok
            ? JSON.stringify(result.data, null, 2)
            : `错误：${result.error}`}
        </pre>
      )}
    </Card>
  );
}
