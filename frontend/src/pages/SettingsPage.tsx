import { useQuery } from "@tanstack/react-query";
import { Settings, ShieldCheck } from "lucide-react";

import { settingsQueryOptions } from "../api/settings";
import { appRoutes } from "../app/appRoutes";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { BackLink } from "../ui/BackLink";
import { Card } from "../ui/Card";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { StatusBadge } from "../ui/StatusBadge";
import { CanonicalFactsBrowser } from "./settings/CanonicalFactsBrowser";
import { ReconciliationPanel } from "./settings/ReconciliationPanel";
import { SettingsForm } from "./settings/SettingsForm";

export const SettingsPage = () => {
  /* Settings stands outside the workflow, so it reports no stage rather than leaving the
     landmark showing whichever one the previous screen published. */
  useWorkflowStage("none");
  const query = useQuery(settingsQueryOptions);

  return (
    <PageShell
      actions={
        query.data === undefined ? null : (
          <StatusBadge tone={query.data.settings.provider_configured ? "success" : "neutral"}>
            {query.data.settings.provider_configured ? "ספק AI מוגדר" : "מצב דטרמיניסטי זמין"}
          </StatusBadge>
        )
      }
      description="מדיניות ביצוע, תצוגת הממשק ובדיקות התקינות של מאגר הידע והתוצרים."
      measure="form"
      navigation={
        <BackLink label="חזרה ללוח המועמדויות" to={appRoutes.home}>
          לוח המועמדויות
        </BackLink>
      }
      title={
        <span className="inline-flex items-center gap-2">
          <Settings aria-hidden="true" className="size-6 text-cv-accent" />
          הגדרות המערכת
        </span>
      }
    >
      <Card className="bg-cv-surface p-5 shadow-surface sm:p-6">
        <div className="mb-5 flex items-start gap-2.5 border-b border-cv-border pb-3">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-cv-accent-soft text-cv-accent">
            <ShieldCheck aria-hidden="true" className="size-4" />
          </span>
          <div>
            <h2 className="text-heading-sm font-bold text-cv-text">מדיניות הפעלה ותצוגה</h2>
            <p className="mt-1 text-support text-cv-text-muted">השינויים נשמרים באפליקציה ומשפיעים מיד על הממשק.</p>
          </div>
        </div>
        <QueryState
          error={query.error}
          fallbackTitle="ההגדרות לא נטענו"
          loading={query.data === undefined}
          loadingLabel="טוען הגדרות…"
        >
          {query.data === undefined ? null : <SettingsForm etag={query.data.etag} settings={query.data.settings} />}
        </QueryState>
      </Card>
      <ReconciliationPanel />
      <CanonicalFactsBrowser />
    </PageShell>
  );
};
