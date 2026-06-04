import { App, Space, Switch, Typography } from "antd";
import { useEffect, useRef, useState } from "react";

import { postPresence } from "../api/staffPresence";

const HEARTBEAT_INTERVAL_MS = 5 * 60 * 1000;

export function PresenceToggle({ token }: { token: string }) {
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(false);
  const heartbeatRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const { message } = App.useApp();

  useEffect(() => {
    return () => {
      if (heartbeatRef.current) clearInterval(heartbeatRef.current);
    };
  }, []);

  async function toggle(checked: boolean) {
    setLoading(true);
    try {
      const r = await postPresence(token, checked ? "online" : "offline");
      setOnline(checked);
      if (checked) {
        if (heartbeatRef.current) clearInterval(heartbeatRef.current);
        heartbeatRef.current = setInterval(() => {
          postPresence(token, "online").catch(() => {});
        }, HEARTBEAT_INTERVAL_MS);
      } else {
        if (heartbeatRef.current) {
          clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }
        if (r.released_count > 0) {
          message.info(`已释放 ${r.released_count} 个未接管会话给其他客服`);
        }
      }
    } catch (e) {
      message.error(e instanceof Error ? e.message : "切换失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Space>
      <Switch checked={online} loading={loading} onChange={toggle} />
      <Typography.Text type={online ? "success" : "secondary"}>
        {online ? "在线" : "离线"}
      </Typography.Text>
    </Space>
  );
}
