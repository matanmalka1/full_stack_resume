import { Moon } from "lucide-react";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { settingsQueryOptions } from "@/api/settings";
import { SettingsForm } from "@/features/settings/components/SettingsForm";
import { buttonClasses, Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { Tooltip } from "@/ui/Tooltip";
import { settingValueLabel } from "@/features/settings/settings.model";

export const ThemeToggle = () => {
  const [open, setOpen] = useState(false);
  const query = useQuery(settingsQueryOptions);
  const label = `ערכת נושא: ${settingValueLabel(query.data?.settings.ui_theme ?? "system")}`;
  return (
    <>
      <Tooltip label={label} placement="shell">
        <button
          aria-label={label}
          className={buttonClasses("secondary", "shrink-0", "icon")}
          disabled={query.data === undefined}
          onClick={() => setOpen(true)}
          type="button"
        >
          <Moon aria-hidden="true" className="size-icon-md" />
        </button>
      </Tooltip>
      <Dialog
        dismissible={false}
        open={open}
        onClose={() => setOpen(false)}
        headingId="theme-settings-heading"
        title="ערכת נושא"
      >
        {open && query.data !== undefined && (
          <SettingsForm themeOnly settings={query.data.settings} etag={query.data.etag} />
        )}
        <Button className="mt-4" variant="secondary" onClick={() => setOpen(false)}>
          סגירה וחזרה לערך השמור
        </Button>
      </Dialog>
    </>
  );
};
