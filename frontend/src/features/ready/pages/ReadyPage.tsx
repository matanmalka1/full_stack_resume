import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Download, FileCheck2, Lock, PencilLine, Send, ShieldCheck } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import { decisionExportQueryOptions, documentPdfHref, documentQueryOptions } from "@/api/documents";
import { boardPath } from "@/app/boardReturn";
import { routePaths } from "@/app/routePaths";
import { useRequiredParam } from "@/app/useRequiredParam";
import { applicationLabel } from "@/features/applications";
import { ValidationReportView } from "@/features/drafts";
import { PreparationAlerts, WizardStepShell } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { SummaryList } from "@/ui/SummaryList";
import { formatDateTime } from "@/utils/formatDateTime";
import { DecisionDocument } from "../components/DecisionDocument";
import { SubmissionDialog } from "../components/SubmissionDialog";

const readyLoading = (
  <div className="flex flex-col gap-6">
    <LiveRegion>טוען את קורות החיים המוכנים…</LiveRegion>
    <Skeleton className="block h-40 w-full" />
    <Skeleton className="block h-64 w-full" />
  </div>
);

const CardHeading = ({ children, icon: Icon, id }: { children: ReactNode; icon: typeof Lock; id: string }) => (
  <h2 className="flex items-center gap-2 font-semibold text-cv-text" id={id}>
    <Icon aria-hidden="true" className="size-icon-md shrink-0 text-cv-accent" />
    {children}
  </h2>
);

const downloadMarkdown = (markdown: string, filename: string) => {
  const href = URL.createObjectURL(new Blob([markdown], { type: "text/markdown;charset=utf-8" }));
  const anchor = window.document.createElement("a");
  anchor.href = href;
  anchor.download = filename;
  /* Firefox ignores a click on a detached anchor, and revoking the URL in the same task
     can cancel the download before the browser has read the blob. */
  anchor.hidden = true;
  window.document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 0);
};

/* The ready step: the Application's one document, once the projection says it is Ready.

   Ready is a state of the document, not a record of its own (§5): it holds exactly while
   the rendered files, the approval and the current basis agree. So this screen reads the
   state rather than deciding it, and the editor is always one press away - editing a
   Ready document is allowed and simply returns it to draft. What is frozen is what left
   the system: recording a submission copies the content and files it sent. */
export const ReadyPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submissionRecorded, setSubmissionRecorded] = useState(false);
  const [downloadStarted, setDownloadStarted] = useState(false);

  const applicationQuery = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = applicationQuery.data;
  const ready = detail?.document_state === "ready";
  const documentHash = detail?.document_hash ?? null;
  const documentQuery = useQuery({
    ...documentQueryOptions(applicationId),
    enabled: detail?.document_id != null,
  });
  const decisionQuery = useQuery({
    ...decisionExportQueryOptions(applicationId, documentHash ?? ""),
    enabled: ready && documentHash !== null,
  });
  const document = documentQuery.data?.document;

  /* Submissions of this exact document, read from the recruitment history the projection
     already carries. The hash is the document's identity, so a submission of an earlier
     state of it is not this one. */
  const submittedAt =
    documentHash === null
      ? null
      : (detail?.recruitment_timeline ?? []).reduceRight<string | null>(
          (found, item) =>
            found ?? (item.item_type === "submission" && item.document_hash === documentHash ? item.occurred_at : null),
          null,
        );
  const submissionExists = submittedAt !== null || submissionRecorded;
  const canSubmit = ready && detail?.available_actions.includes("submit") === true && documentHash !== null;
  const canDownload = ready && documentHash !== null;

  const backLink = (
    <Link className={buttonClasses("ghost")} to={routePaths.draft(applicationId)}>
      <ArrowRight aria-hidden="true" className="size-icon-md" />
      חזרה לעריכת הטיוטה
    </Link>
  );

  /* Download is a secondary action beside recording the submission, never a gate in front
     of it: both are offered together - download the file, and record the send it was for. */
  const downloadButton =
    !canDownload || documentHash === null ? null : (
      <a
        className={buttonClasses("secondary")}
        href={documentPdfHref(applicationId, documentHash)}
        key="download-pdf"
        onClick={() => setDownloadStarted(true)}
      >
        <Download aria-hidden="true" className="size-icon-md" />
        {downloadStarted || submissionExists ? "הורדת PDF שוב" : "הורדת PDF"}
      </a>
    );

  const nextStep = !ready
    ? null
    : submissionExists
      ? {
          note: "ההגשה נרשמה. תהליך הכנת קורות החיים הושלם.",
          primary: (
            <Link className={buttonClasses("primary")} to={boardPath()}>
              סיום וחזרה ללוח
            </Link>
          ),
        }
      : {
          note: "הורידו את הקובץ ומסרו אותו למגייס, ואז רשמו כאן שההגשה בוצעה.",
          primary: (
            <Button disabled={!canSubmit} onClick={() => setSubmissionOpen(true)}>
              <Send aria-hidden="true" className="size-icon-md" />
              רישום ההגשה
            </Button>
          ),
        };

  return (
    <WizardStepShell
      applicationId={applicationId}
      description="המסמך המוכן נשאר זמין כל עוד לא שונה. עריכה מחזירה אותו לטיוטה, וההגשות שנרשמו נשמרות כפי שנשלחו."
      detail={detail}
      eyebrow={
        detail === undefined ? (
          <Skeleton className="inline-block w-56 max-w-full align-middle" />
        ) : (
          <span dir="auto">{applicationLabel(detail.application.company, detail.application.target_role)}</span>
        )
      }
      measure="wide"
      queryError={applicationQuery.error}
      stage="ready"
      title={detail !== undefined && !ready ? "קורות החיים אינם מוכנים כרגע" : undefined}
    >
      <QueryState
        error={applicationQuery.error}
        fallbackTitle="לא ניתן לטעון את קורות החיים המוכנים"
        loading={detail === undefined}
        loadingState={readyLoading}
      >
        {detail === undefined ? null : (
          <>
            <PreparationAlerts detail={detail} screen="ready" />

            {ready ? null : (
              /* Reached from a link or the rail after the document changed. Nothing here is
                 lost: the editor holds the document as it is now, and approving and
                 rendering it again brings this step back. */
              <Callout
                action={
                  <Link className={buttonClasses("primary")} to={routePaths.draft(applicationId)}>
                    <PencilLine aria-hidden="true" className="size-icon-md" />
                    מעבר לעורך הטיוטה
                  </Link>
                }
                title="המסמך השתנה מאז שהופק"
                tone="neutral"
              >
                קורות החיים יחזרו להיות מוכנים לאחר בדיקה, אישור ויצירת הקבצים מחדש בעורך. הגשות שכבר נרשמו אינן משתנות.
              </Callout>
            )}

            {!ready ? null : (
              <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(19rem,1fr)]">
                <Card
                  aria-labelledby="ready-file-heading"
                  className="flex min-w-0 flex-col gap-4 rounded-surface bg-cv-surface p-5"
                >
                  <CardHeading icon={FileCheck2} id="ready-file-heading">
                    קובץ קורות החיים
                  </CardHeading>
                  <p className="text-support leading-6 text-cv-text-muted">
                    הקובץ נוצר מהמסמך כפי שאושר
                    {detail.approved_at == null ? "" : ` ב־${formatDateTime(detail.approved_at)}`}. השרת בודק בעת ההורדה
                    שהמסמך עדיין מוכן, ולכן הקובץ שיורד הוא תמיד זה שמתאים לו.
                  </p>
                  {submittedAt === null ? null : (
                    <p className="text-support text-cv-text-muted">
                      ההגשה האחרונה של המסמך הזה נרשמה ב־{formatDateTime(submittedAt)}.
                    </p>
                  )}
                  {downloadButton === null ? null : <div className="flex flex-wrap gap-3">{downloadButton}</div>}
                </Card>

                <aside aria-label="פרטי המסמך והבדיקה" className="flex min-w-0 flex-col gap-4">
                  <Card
                    aria-labelledby="ready-validation-heading"
                    className="flex flex-col gap-4 rounded-surface bg-cv-surface p-4"
                  >
                    <CardHeading icon={ShieldCheck} id="ready-validation-heading">
                      בדיקת התוכן
                    </CardHeading>
                    {document?.content_report == null ? (
                      <p className="text-support text-cv-text-muted">דוח הבדיקה נטען…</p>
                    ) : (
                      <ValidationReportView report={document.content_report} />
                    )}
                  </Card>

                  {submittedAt === null ? null : (
                    <Disclosure summary="אפשרויות נוספות">
                      <div className="pt-2">
                        <p className="mb-3 text-support text-cv-text-muted">
                          הפעולות כאן אינן חלק מהשלמת המסירה הנוכחית ואינן משנות את המסמך.
                        </p>
                        <Button disabled={!canSubmit} onClick={() => setSubmissionOpen(true)} variant="secondary">
                          <Send aria-hidden="true" className="size-icon-md" />
                          רישום הגשה נוספת
                        </Button>
                      </div>
                    </Disclosure>
                  )}

                  <Disclosure flush summary="פרטים טכניים">
                    <Card className="overflow-x-auto rounded-surface bg-cv-surface p-4">
                      <CardHeading icon={Lock} id="ready-record-heading">
                        המסמך המוכן
                      </CardHeading>
                      <SummaryList
                        className="mt-4"
                        items={[
                          { term: "חתימת המסמך", value: documentHash ?? "", ltr: true },
                          { term: "ניתוח", value: detail.document_analysis_id ?? "", ltr: true },
                          { term: "תצלום משרה", value: detail.active_job_snapshot_id, ltr: true },
                        ]}
                      />
                    </Card>
                  </Disclosure>

                  <Disclosure flush summary="הסבר ההחלטות">
                    <Card className="rounded-surface bg-cv-surface p-4">
                      {decisionQuery.error === null ? (
                        <DecisionDocument
                          decision={decisionQuery.data}
                          onDownload={() => {
                            if (decisionQuery.data !== undefined) {
                              downloadMarkdown(decisionQuery.data.markdown, "decision.md");
                            }
                          }}
                          pending={decisionQuery.isPending}
                        />
                      ) : (
                        <ErrorCallout
                          error={decisionQuery.error}
                          fallbackDetail="קורות החיים עצמם נשארו זמינים; רק מסמך הסבר ההחלטה לא נטען."
                          fallbackTitle="לא ניתן לטעון את הסבר ההחלטה"
                        />
                      )}
                    </Card>
                  </Disclosure>
                </aside>
              </div>
            )}

            {submissionRecorded ? (
              // role="status" is a Callout prop, not a DOM role; Callout already renders an
              // <output> for it.
              // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
              <Callout role="status" title="ההגשה נרשמה" tone="success">
                התוכן וקובצי ה־HTML וה־PDF המדויקים נשמרו בהיסטוריית המועמדות.
              </Callout>
            ) : null}
          </>
        )}
      </QueryState>

      {/* The ready step's own bar, the same surface the two steps before it close with: the
          way back to editing on one edge, what to do with the finished CV on the other. */}
      {detail === undefined ? null : (
        <CommitBar
          back={backLink}
          label={NEXT_STEP_LABEL}
          primary={
            nextStep === null ? undefined : (
              <>
                {downloadButton === null ? null : <div className="flex flex-wrap gap-3">{downloadButton}</div>}
                {nextStep.primary}
              </>
            )
          }
        >
          {nextStep === null ? undefined : (
            <p className="text-support leading-6 text-cv-text-muted" dir="auto">
              {nextStep.note}
            </p>
          )}
        </CommitBar>
      )}

      {documentHash === null ? null : (
        <SubmissionDialog
          applicationId={applicationId}
          documentHash={documentHash}
          onClose={() => setSubmissionOpen(false)}
          onRecorded={() => setSubmissionRecorded(true)}
          open={submissionOpen}
          previousSubmittedAt={submittedAt}
        />
      )}
    </WizardStepShell>
  );
};
