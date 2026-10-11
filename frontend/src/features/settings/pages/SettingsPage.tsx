import { useQuery } from "@tanstack/react-query";
import { KeyRound, Settings } from "lucide-react";

import { settingsQueryOptions } from "@/api/settings";
import { ChangePasswordForm, SignOutButton } from "@/features/auth";
import { Card } from "@/ui/Card";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { Skeleton } from "@/ui/Skeleton";
import { SettingsForm, settingsCardClasses } from "../components/SettingsForm";

/* The sections the form opens with - AI, automation, display - held at their
   own size while the read is in flight, and the row of controls that closes it. The screen
   is reached directly from the navigation, so the wait is the reader's first sight of it,
   and a single line of muted text under a section heading made that first sight look like
   a card that had failed to fill rather than one still filling. */
const settingsLoading = (
  <div className="flex flex-col gap-6">
    <LiveRegion>טוען הגדרות…</LiveRegion>
    {["automation", "ai", "display"].map((section) => (
      <div className="flex flex-col gap-2" key={section}>
        <Skeleton className="block h-4 w-32" />
        <Skeleton className="block h-3 w-64 max-w-full" />
        <Skeleton className="mt-2 block h-11 w-full" />
      </div>
    ))}
    {/* The save row's button stands at its closing edge. */}
    <div className="flex justify-end">
      <Skeleton className="block h-11 w-40" />
    </div>
  </div>
);

export const SettingsPage = () => {
  const query = useQuery(settingsQueryOptions);

  return (
    <PageShell
      description="מדיניות ביצוע ותצוגת הממשק."
      measure="form"
      title={
        <span className="inline-flex items-center gap-2">
          <Settings aria-hidden="true" className="size-6 text-cv-accent" />
          הגדרות המערכת
        </span>
      }
    >
      {/* One card per area - AI, display, account - instead of one long card. The two
          settings cards are one form with one save, so they come from `SettingsForm`. */}
      <QueryState
        error={query.error}
        errorTitle="לא ניתן לטעון את ההגדרות"
        loading={query.data === undefined}
        loadingState={<Card className={settingsCardClasses}>{settingsLoading}</Card>}
      >
        {query.data === undefined ? null : <SettingsForm etag={query.data.etag} settings={query.data.settings} />}
      </QueryState>
      <Card className={settingsCardClasses}>
        <SectionHeader
          className="mb-5"
          description="שינוי הסיסמה מנתק את כל ההתחברויות האחרות."
          icon={KeyRound}
          title="חשבון"
        />
        <ChangePasswordForm />
        {/* On a wide screen sign-out sits in the sidebar; a narrow screen's masthead keeps
            only the wordmark and the new-job command, so it lives here instead. */}
        <div className="mt-6 border-t border-cv-hairline pt-4 lg:hidden">
          <SignOutButton />
        </div>
      </Card>
    </PageShell>
  );
};
