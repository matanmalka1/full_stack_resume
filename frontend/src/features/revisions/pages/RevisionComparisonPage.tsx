import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { applicationDetailQueryOptions } from "@/api/applications";
import {
  approvedRevisionQueryOptions,
  approvedRevisionsQueryOptions,
  revisionComparisonQueryOptions,
} from "@/api/revisions";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Field } from "@/ui/Field";
import { LiveRegion } from "@/ui/LiveRegion";
import { PageShell } from "@/ui/PageShell";
import { QueryState } from "@/ui/QueryState";
import { Select } from "@/ui/Select";
import { Skeleton } from "@/ui/Skeleton";
import { formatDateTime } from "@/utils/formatDateTime";
import { applicationLabel } from "@/features/applications";
import { RevisionComparisonView } from "../components/RevisionComparisonView";

const comparisonLoading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>משווה בין הגרסאות…</LiveRegion>
    <Skeleton className="block h-20 w-full" />
    <Skeleton className="block h-56 w-full" />
  </div>
);

/* Two approved versions side by side in time: what the newer one added, removed,
   reworded or moved relative to the older. The page belongs to the newer revision - it is
   reached from that revision's history - and the base is a choice made on it. */
const RevisionComparisonContent = ({ baseRevisionId, revisionId }: { baseRevisionId: string; revisionId: string }) => {
  const navigate = useNavigate();
  const revisionQuery = useQuery(approvedRevisionQueryOptions(revisionId));
  const applicationId = revisionQuery.data?.application_id;
  const revisionsQuery = useQuery({
    ...approvedRevisionsQueryOptions(applicationId ?? ""),
    enabled: applicationId !== undefined,
  });
  const applicationQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId ?? ""),
    enabled: applicationId !== undefined,
  });
  const comparisonQuery = useQuery(revisionComparisonQueryOptions(revisionId, baseRevisionId));

  const ordered = [...(revisionsQuery.data?.items ?? [])];
  // oxlint-disable-next-line unicorn/no-array-sort -- local copy; toSorted needs ES2023.
  ordered.sort((left, right) => right.version_number - left.version_number);
  const target = revisionQuery.data;
  const detail = applicationQuery.data;

  const choose = (nextTarget: string, nextBase: string) =>
    navigate(routePaths.revisionComparison(nextTarget, nextBase), { replace: true });

  return (
    <PageShell
      actions={
        target === undefined ? undefined : (
          <Link className={buttonClasses("ghost")} to={routePaths.revision(target.id)}>
            <ArrowRight aria-hidden="true" className="size-icon-md" />
            חזרה לגרסה {target.version_number}
          </Link>
        )
      }
      description="השורות מושוות לפי העובדות שהן מציגות, כך שניסוח חדש לאותה עובדה מסומן כשורה שנוסחה מחדש ולא כשורה שהוסרה ונוספה. שתי הגרסאות עצמן אינן משתנות."
      eyebrow={
        detail === undefined ? (
          <Skeleton className="inline-block w-56 max-w-full align-middle" />
        ) : (
          <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
        )
      }
      measure="wizard"
      title="השוואת גרסאות"
    >
      {ordered.length < 2 ? null : (
        <div className="grid gap-field-gap sm:grid-cols-2">
          <Field label="מגרסה (הישנה)">
            {(control) => (
              <Select {...control} onChange={(event) => choose(revisionId, event.target.value)} value={baseRevisionId}>
                {ordered
                  .filter((revision) => revision.id !== revisionId)
                  .map((revision) => (
                    <option key={revision.id} value={revision.id}>
                      גרסה {revision.version_number} · {formatDateTime(revision.approved_at, "short")}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
          <Field label="לגרסה (החדשה)">
            {(control) => (
              <Select {...control} onChange={(event) => choose(event.target.value, baseRevisionId)} value={revisionId}>
                {ordered
                  .filter((revision) => revision.id !== baseRevisionId)
                  .map((revision) => (
                    <option key={revision.id} value={revision.id}>
                      גרסה {revision.version_number} · {formatDateTime(revision.approved_at, "short")}
                    </option>
                  ))}
              </Select>
            )}
          </Field>
        </div>
      )}

      <QueryState
        error={revisionQuery.error ?? comparisonQuery.error}
        fallbackDetail="שתי הגרסאות נשמרו כפי שהן; רק ההשוואה ביניהן לא נטענה."
        fallbackTitle="לא ניתן להשוות בין הגרסאות"
        loading={comparisonQuery.data === undefined}
        loadingState={comparisonLoading}
      >
        {comparisonQuery.data === undefined ? null : <RevisionComparisonView comparison={comparisonQuery.data} />}
      </QueryState>
    </PageShell>
  );
};

export const RevisionComparisonPage = () => {
  const { revisionId } = useParams();
  const [searchParams] = useSearchParams();
  const baseRevisionId = searchParams.get("base");

  if (revisionId === undefined) {
    throw new Error("RevisionComparisonPage requires a revisionId route parameter");
  }
  /* Without a base there is nothing to compare against; the revision itself is the
     honest destination rather than an empty comparison. */
  if (baseRevisionId === null || baseRevisionId === "") {
    return <RevisionComparisonRedirect revisionId={revisionId} />;
  }

  return <RevisionComparisonContent baseRevisionId={baseRevisionId} revisionId={revisionId} />;
};

const RevisionComparisonRedirect = ({ revisionId }: { revisionId: string }) => (
  <PageShell measure="wizard" title="השוואת גרסאות">
    <p className="text-support text-cv-text-muted">
      לא נבחרה גרסה להשוואה.{" "}
      <Link className="font-semibold text-cv-accent underline" to={routePaths.revision(revisionId)}>
        חזרה לגרסה
      </Link>
    </p>
  </PageShell>
);
