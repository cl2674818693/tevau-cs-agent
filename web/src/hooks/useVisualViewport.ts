import { useEffect, useState } from "react";

/**
 * 监听虚拟键盘弹起。在 iOS Safari / Android webview 里键盘弹起时
 * window.innerHeight 不变，需要用 visualViewport.height 才能得到
 * 实际可见区域。返回 bottomInset = innerHeight - visualViewport.height。
 */
export function useKeyboardInset(): number {
  const [inset, setInset] = useState(0);
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const update = () => {
      const next = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      setInset(next);
    };
    vv.addEventListener("resize", update);
    vv.addEventListener("scroll", update);
    update();
    return () => {
      vv.removeEventListener("resize", update);
      vv.removeEventListener("scroll", update);
    };
  }, []);
  return inset;
}
