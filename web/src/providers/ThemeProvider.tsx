import { createContext, useEffect, useMemo, useState, type ReactNode } from "react";

export type Theme = "light" | "dark" | "system";

type Ctx = {
  theme: Theme;
  setTheme: (t: Theme) => void;
};

export const ThemeContext = createContext<Ctx | null>(null);

function resolveSystemDark(): boolean {
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyDark(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

/** AppShell 外层包裹。ChatRoute 不包，进入时副作用清掉 dark 类。 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    const saved = localStorage.getItem("theme");
    return saved === "light" || saved === "dark" ? saved : "system";
  });

  useEffect(() => {
    if (theme === "system") {
      applyDark(resolveSystemDark());
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const listener = () => applyDark(resolveSystemDark());
      mq.addEventListener("change", listener);
      return () => mq.removeEventListener("change", listener);
    }
    applyDark(theme === "dark");
  }, [theme]);

  const value = useMemo<Ctx>(
    () => ({
      theme,
      setTheme: (t) => {
        if (t === "system") localStorage.removeItem("theme");
        else localStorage.setItem("theme", t);
        setThemeState(t);
      },
    }),
    [theme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
