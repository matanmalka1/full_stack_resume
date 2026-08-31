import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "../api/applications";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { Card } from "../ui/Card";
import { PageHeading } from "../ui/PageHeading";
import { StatusBadge } from "../ui/StatusBadge";
import { ApplicationViews } from "./ApplicationViews";
import { RecruitmentPanel } from "./RecruitmentPanel";
import {
  recruitmentStatusIcon,
  recruitmentStatusLabel,
  recruitmentStatusTone,
} from "./applicationLabels";

/* The recruitment axis on its own screen.

   It shares the Application's context - the header names the company and the role, and
   the local switch reaches the preparation screen - but nothing else. The two axes are
   independent: a document can be Ready while the recruitment status is still `saved`, and
   an Application can be `closed` with no draft ever written. Showing them in one card made
   the reader ask, every visit, which of the two states in front of them the screen was
   about (product-spec §399: preparation and recruitment are separate views).

   The preparation stage is not published here. This screen is not on the workflow path, so
   `none` is the honest landmark answer - the same one Settings gives. */
export const TrackingPage = () => {
  const { applicationId } = useParams();

  if (applicationId === undefined) {
    throw new Error("TrackingPage rendered without an applicationId route parameter");
  }

  const query = useQuery(applicationDetailQueryOptions(applicationId));
  const detail = query.data;

  useWorkflowStage("none");

  return (
    <Card aria-labelledby="route-heading">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3 border-b border-cv-border pb-4">
        <div className="min-w-0">
          <PageHeading
            description={detail === undefined ? "טוען את מעקב הגיוס…" : undefined}
            id="route-heading"
          >
            מעקב גיוס
          </PageHeading>
        </div>
        {detail === undefined ? null : (
          <StatusBadge
            icon={recruitmentStatusIcon(detail.recruitment_status)}
            tone={recruitmentStatusTone(detail.recruitment_status)}
          >
            {recruitmentStatusLabel(detail.recruitment_status)}
          </StatusBadge>
        )}
      </div>

      <ApplicationViews applicationId={applicationId} current="tracking" />

      {query.error === null ? null : (
        <ErrorCallout
          className="mt-6"
          error={query.error}
          fallbackDetail="הפנייה לשרת נכשלה. אפשר לרענן את העמוד ולנסות שוב."
          fallbackTitle="לא ניתן לטעון את מעקב הגיוס"
        />
      )}

      {detail === undefined ? (
        query.error === null ? (
          <p className="mt-6 text-body text-cv-text-muted">טוען את מעקב הגיוס…</p>
        ) : null
      ) : (
        <div className="mt-5">
          <RecruitmentPanel detail={detail} />
        </div>
      )}
    </Card>
  );
};
