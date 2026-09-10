import { Moon, Sun } from "lucide-react";
import { useState } from "react";

import { buttonClasses } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";

type Theme = "dark" | "light";

const STORAGE_KEY = "cv-theme";

const systemTheme = (): Theme =>
  typeof window.matchMedia === "function" && window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";

const storedTheme = (): Theme | undefined => {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "dark" || value === "light" ? value : undefined;
  } catch {
    return undefined;
  }
};

const initialTheme = (): Theme => {
  const theme = storedTheme() ?? systemTheme();
  const saved = storedTheme();

  if (saved === undefined) {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.dataset.theme = saved;
  }

  return theme;
};

export const ThemeToggle = () => {
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const nextTheme: Theme = theme === "dark" ? "light" : "dark";
  const Icon = theme === "dark" ? Sun : Moon;
  const label = theme === "dark" ? "מעבר למצב בהיר" : "מעבר למצב כהה";

  const toggle = () => {
    document.documentElement.dataset.theme = nextTheme;
    try {
      window.localStorage.setItem(STORAGE_KEY, nextTheme);
    } catch {
      // The selected theme still applies for this session when storage is unavailable.
    }
    setTheme(nextTheme);
  };

  return (
    <Tooltip label={label} placement="bottom">
      <button
        aria-label={label}
        className={buttonClasses("secondary", "shrink-0", "icon")}
        onClick={toggle}
        type="button"
      >
        <Icon aria-hidden="true" className="size-icon-md" />
      </button>
    </Tooltip>
  );
};
