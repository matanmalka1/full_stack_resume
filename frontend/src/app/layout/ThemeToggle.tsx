import { Moon, Sun } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { readSettings, settingsQueryKey, settingsQueryOptions, updateSettings } from "@/api/settings";
import { editableSettings, settingValueLabel } from "@/features/settings/settings.model";
import { buttonClasses } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Tooltip } from "@/ui/Tooltip";

export const ThemeToggle = () => {
  const client = useQueryClient();
  const query = useQuery(settingsQueryOptions);
  const theme = query.data?.settings.ui_theme ?? "system";
  const dark =
    theme === "dark" ||
    (theme === "system" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches);
  const nextTheme = dark ? "light" : "dark";
  const Icon = dark ? Sun : Moon;
  const label = `ערכת נושא: ${settingValueLabel(theme)}`;
  const save = useMutation({
    mutationFn: async (selected: "light" | "dark") => {
      // Read the other preferences afresh; a click changes only the theme.
      // The write still uses If-Match and never retries a conflict automatically.
      const current = await readSettings();
      if (current.etag === null) throw new Error("Settings require a current ETag");
      return updateSettings({ ...editableSettings(current.settings), ui_theme: selected }, current.etag);
    },
    onSuccess: (result) => client.setQueryData(settingsQueryKey, result),
  });
  return (
    <>
      <Tooltip label={`${label} — ${nextTheme === "light" ? "מעבר למצב בהיר" : "מעבר למצב כהה"}`} placement="shell">
        <button
          aria-label={label}
          className={buttonClasses("secondary", "shrink-0", "icon")}
          disabled={query.data === undefined || save.isPending}
          onClick={() => save.mutate(nextTheme)}
          type="button"
        >
          <Icon aria-hidden="true" className="size-icon-md" />
        </button>
      </Tooltip>
      {save.error !== null && (
        <div>
          <ErrorCallout error={save.error} fallbackTitle="ערכת הנושא לא נשמרה" />
          <Link className="text-support text-cv-accent hover:underline" to="/settings">
            פתיחת ההגדרות לפתרון
          </Link>
        </div>
      )}
    </>
  );
};
