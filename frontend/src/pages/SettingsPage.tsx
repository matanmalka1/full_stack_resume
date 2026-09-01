import { useQuery } from "@tanstack/react-query";

import { settingsQueryOptions } from "../api/settings";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { PageShell } from "../ui/PageShell";
import { QueryState } from "../ui/QueryState";
import { ReconciliationPanel } from "./settings/ReconciliationPanel";
import { SettingsForm } from "./settings/SettingsForm";

export const SettingsPage = () => {
  /* Settings stands outside the workflow, so it reports no stage rather than leaving the
     landmark showing whichever one the previous screen published. */
  useWorkflowStage("none");
  const query = useQuery(settingsQueryOptions);

  return (
    <PageShell
      description="השינויים נשמרים באפליקציה ומשפיעים מיד על מסכי ה־Web."
      title="הגדרות"
    >
      <QueryState
        error={query.error}
        fallbackTitle="ההגדרות לא נשמרו"
        loading={query.data === undefined}
        loadingLabel="טוען הגדרות…"
      >
        {query.data === undefined ? null : (
          <SettingsForm etag={query.data.etag} settings={query.data.settings} />
        )}
      </QueryState>
      <ReconciliationPanel />
    </PageShell>
  );
};
