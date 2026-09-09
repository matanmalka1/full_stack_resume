import { useQuery } from "@tanstack/react-query";
import { Navigate } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import { useRequiredParam } from "@/app/useRequiredParam";
import { preparationResumeDestinationFromDetail } from "@/features/preparation";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";

/* Resolve a duplicate match through the current Application projection before entering
   the wizard. Duplicate evidence has no workflow fields of its own, and must not acquire
   them merely so one link can guess where current work lives. */
export const ApplicationResumePage = () => {
  const applicationId = useRequiredParam("applicationId");
  const query = useQuery(applicationDetailQueryOptions(applicationId));

  if (query.data !== undefined) {
    return <Navigate replace to={preparationResumeDestinationFromDetail(applicationId, query.data)} />;
  }

  return (
    /* This resolver belongs to the workflow geometry but does not claim a workflow stage:
       it only reads the projection and redirects to the screen that owns that stage. */
    <PageShell measure="wizard" title="ממשיך מהמקום שבו עצרת">
      <QueryState
        error={query.error}
        fallbackTitle="לא ניתן לפתוח את המועמדות"
        loading
        loadingLabel="בודק מהו השלב הפעיל…"
      />
    </PageShell>
  );
};
