import type { Settings } from "@/api/contracts";

export const THEME_CACHE_KEY = "cv-theme-cache";
export const applyTheme = (theme: Settings["ui_theme"]) => {
  // CSS follows prefers-color-scheme live without an explicit theme.
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.dataset.theme = theme;
};
export const cacheTheme = (theme: Settings["ui_theme"]) => {
  try {
    localStorage.setItem(THEME_CACHE_KEY, theme);
  } catch {
    /* Optional startup cache. */
  }
};
