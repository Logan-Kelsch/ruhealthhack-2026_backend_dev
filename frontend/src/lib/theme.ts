import { useEffect, useState } from "react";

// Theme lives on the <html> class list (`dark`), matching the @custom-variant in
// index.css.
//
// @deprecated Dark mode is retired: the app always renders light and the toggle is gone.
// The dark tokens and this hook stay until the team decides whether to delete them.

export type Theme = "light" | "dark";

const STORAGE_KEY = "rounds-theme";

// Always light, whatever was stored before or what the operating system prefers.
function readTheme(): Theme {
  return "light";
}

// Called from main.tsx before the first render so there is no flash of the wrong theme.
export function applyStoredTheme() {
  document.documentElement.classList.toggle("dark", readTheme() === "dark");
}

/** @deprecated Dark mode is retired; nothing renders a toggle any more. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(readTheme);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const toggle = () => setTheme((current) => (current === "dark" ? "light" : "dark"));

  return { theme, toggle };
}
