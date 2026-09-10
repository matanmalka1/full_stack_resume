import { useQuery } from "@tanstack/react-query";
import { Settings, ShieldCheck } from "lucide-react";

import { settingsQueryOptions } from "@/api/settings";
import { boardPath } from "@/app/boardReturn";
import { Breadcrumbs } from "@/ui/Breadcrumbs";
import { Card } from "@/ui/Card";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { Skeleton } from "@/ui/Skeleton";
import { SettingsForm } from "../components/SettingsForm";

/* The three `FormSection`s the form opens with - automation, AI, display - held at their
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
    {/* `ActionBar` defaults to the closing edge, so the placeholder stands where the save
        button will actually land rather than on the opposite side of the card. */}
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
      navigation={<Breadcrumbs items={[{ label: "מועמדויות", to: boardPath() }, { label: "הגדרות" }]} />}
      title={
        <span className="inline-flex items-center gap-2">
          <Settings aria-hidden="true" className="size-6 text-cv-accent" />
          הגדרות המערכת
        </span>
      }
    >
      <Card className="bg-cv-surface p-5 shadow-surface sm:p-6">
        <SectionHeader
          className="mb-5"
          description="השינויים נשמרים באפליקציה ומשפיעים מיד על הממשק."
          icon={ShieldCheck}
          title="מדיניות הפעלה ותצוגה"
        />
        <QueryState
          error={query.error}
          fallbackTitle="ההגדרות לא נטענו"
          loading={query.data === undefined}
          loadingState={settingsLoading}
        >
          {query.data === undefined ? null : <SettingsForm etag={query.data.etag} settings={query.data.settings} />}
        </QueryState>
      </Card>
    </PageShell>
  );
};
