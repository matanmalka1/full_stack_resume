import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { settingsQueryOptions } from "@/api/settings";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { cardClasses } from "@/ui/surface";
import { AccountList, AccountSection, ChangePasswordDialog } from "../components/AccountSettings";
import { SettingsForm } from "../components/SettingsForm";

/* The areas the form opens with - display, the CV, AI - held at their own size while the
   read is in flight. The screen is reached directly from the navigation, so the wait is
   the reader's first sight of it, and a single line of muted text made that first sight
   look like a card that had failed to fill rather than one still filling. */
const settingsLoading = (
  <div className="flex flex-col gap-4.5 lg:gap-6">
    <LiveRegion>טוען הגדרות…</LiveRegion>
    {["display", "cv", "ai"].map((section) => (
      <div className="flex flex-col gap-2 lg:flex-row lg:gap-8" key={section}>
        <Skeleton className="block h-4 w-24 lg:flex-[1_1_13.75rem]" />
        <div className={cardClasses("flex flex-col gap-3 p-4 lg:flex-[2_1_23.75rem]")}>
          <Skeleton className="block h-4 w-32" />
          <Skeleton className="block h-10 w-full" />
        </div>
      </div>
    ))}
  </div>
);

/* Settings in the design's order: the account, then how the app looks, then the CV's
   defaults, then AI. A phone keeps the account's commands for a list at the end. */
export const SettingsPage = () => {
  const query = useQuery(settingsQueryOptions);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const openPassword = () => setPasswordOpen(true);

  return (
    <PageShell measure="form" title="הגדרות">
      <div className="flex flex-col gap-4.5 lg:gap-6">
        <AccountSection onChangePassword={openPassword} />
        <QueryState
          error={query.error}
          errorTitle="לא ניתן לטעון את ההגדרות"
          loading={query.data === undefined}
          loadingState={settingsLoading}
        >
          {query.data === undefined ? null : <SettingsForm etag={query.data.etag} settings={query.data.settings} />}
        </QueryState>
        <AccountList onChangePassword={openPassword} />
      </div>
      <ChangePasswordDialog onClose={() => setPasswordOpen(false)} open={passwordOpen} />
    </PageShell>
  );
};
