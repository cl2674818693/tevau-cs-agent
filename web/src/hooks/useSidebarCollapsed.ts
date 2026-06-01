import { useCallback, useState } from "react";

const KEY = "sidebar-collapsed";

function readSet(): Set<string> {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set();
  }
}

export function useSidebarCollapsed() {
  const [set, setSet] = useState<Set<string>>(readSet);

  const toggle = useCallback((groupId: string) => {
    setSet((prev) => {
      const next = new Set(prev);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      localStorage.setItem(KEY, JSON.stringify([...next]));
      return next;
    });
  }, []);

  const collapsed = useCallback((groupId: string) => set.has(groupId), [set]);

  return { collapsed, toggle };
}
