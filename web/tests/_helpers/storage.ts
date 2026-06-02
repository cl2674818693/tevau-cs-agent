/** 沙箱 jsdom 的 localStorage 不一定实现 .clear()；按 key 逐个删除。 */
export function clearLocalStorage(): void {
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (k) keys.push(k);
  }
  keys.forEach((k) => localStorage.removeItem(k));
}
