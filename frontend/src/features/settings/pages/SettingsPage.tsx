import { useQuery } from "@tanstack/react-query";
import { KeyRound, Lock, User } from "lucide-react";

import { meQueryOptions } from "@/api/auth";
import { settingsQueryOptions } from "@/api/settings";
import { ChangePasswordForm, SignOutButton } from "@/features/auth";
import { Card } from "@/ui/Card";
import { PageShell } from "@/ui/PageShell";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { SectionHeader } from "@/ui/SectionHeader";
import { Skeleton } from "@/ui/Skeleton";
import { cx } from "@/ui/cx";
import { PhoneFoldRow, usePhoneFold } from "../components/PhoneFold";
import {
  SettingsForm,
  settingsCardClasses,
  settingsSectionBodyClasses,
  settingsSectionHeaderClasses,
} from "../components/SettingsForm";

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
  /* Already read by the session gate this screen renders inside. The query only reads that
     cache (`enabled: false`): the card is a courtesy, not a reason for a request. */
  const me = useQuery({ ...meQueryOptions, enabled: false });
  const passwordFold = usePhoneFold({ wide: true });

  return (
    <PageShell
      description="מדיניות ביצוע ותצוגת הממשק."
      /* The two-column sections want more room than a single column of inputs does. */
      measure="wizard"
      title="הגדרות המערכת"
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
      {/* The account, in one tree for both widths. A phone opens Settings on whose they
          are, as a phone's own settings do, and closes it on the account card: the wrapper
          is `contents` there, so the identity card leads the column and the account card
          ends it. A wide screen leads with the account as the first two-column section -
          its name beside one card holding the identity above the password and sign-out -
          laid out by grid placement rather than drawn twice. */}
      <div className="max-lg:contents lg:order-first lg:grid lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] lg:items-start lg:gap-x-10 lg:border-b lg:border-cv-hairline lg:pb-8">
        {me.data == null ? null : (
          <Card
            className={cx(
              settingsCardClasses,
              "flex items-center gap-3 max-lg:order-first lg:col-start-2 lg:row-start-1 lg:rounded-t-surface lg:p-4 lg:shadow-none",
            )}
          >
            <span
              aria-hidden="true"
              className="flex size-12 shrink-0 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent"
            >
              <User className="size-icon-lg" />
            </span>
            <span className="min-w-0 truncate text-body font-bold text-cv-text" dir="ltr">
              {me.data.email}
            </span>
          </Card>
        )}
        <Card className={cx(settingsCardClasses, "lg:contents")}>
          <SectionHeader
            className={cx("mb-5 lg:col-start-1 lg:row-span-2 lg:row-start-1", settingsSectionHeaderClasses)}
            description="שינוי הסיסמה מנתק את כל ההתחברויות האחרות."
            icon={KeyRound}
            title="חשבון"
          />
          <div
            className={cx(
              "lg:row-start-2 lg:flex lg:flex-wrap lg:items-center lg:gap-2",
              settingsSectionBodyClasses,
              me.data == null ? undefined : "lg:rounded-t-none lg:border-t-0",
            )}
          >
            <PhoneFoldRow {...passwordFold.rowProps} icon={Lock} label="שינוי סיסמה" />
            <div
              className={cx("max-lg:mt-3 lg:order-last lg:mt-3 lg:basis-full", passwordFold.panelProps.className)}
              id={passwordFold.panelProps.id}
            >
              <ChangePasswordForm />
            </div>
            {/* A narrow screen's masthead keeps only the wordmark and the quick switcher, so
                sign-out lives here; a wide screen sets it beside the password command. */}
            <div className="mt-6 border-t border-cv-hairline pt-4 max-lg:mt-3 max-lg:pt-1 lg:mt-0 lg:border-t-0 lg:pt-0">
              <SignOutButton wideButton />
            </div>
          </div>
        </Card>
      </div>
    </PageShell>
  );
};
