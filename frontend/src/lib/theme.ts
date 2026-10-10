import { useEffect, useState } from "react";

// Theme lives on the <html> class list (`dark`), matching the @custom-variant in
// index.css. The stored choice wins; otherwise the operating system decides.

export type Theme = "light" | "dark";

const STORAGE_KEY = "rounds-theme";

function readTheme(): Theme {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

// Called from main.tsx before the first render so there is no flash of the wrong theme.
export function applyStoredTheme() {
  document.documentElement.classList.toggle("dark", readTheme() === "dark");
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = () => setTheme((current) => (current === "dark" ? "light" : "dark"));

  return { theme, toggle };
}
