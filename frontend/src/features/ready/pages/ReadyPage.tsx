import { useQuery } from "@tanstack/react-query";
import { Check, ChevronLeft, Download, FileCheck2, PencilLine, Send, ShieldCheck } from "lucide-react";
import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import { decisionExportQueryOptions, documentPdfHref, documentQueryOptions } from "@/api/documents";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { applicationLabel } from "@/features/application-detail";
import { ValidationReportView } from "@/features/drafts";
import { PreparationAlerts, WizardStepShell } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Card } from "@/ui/Card";
import { cx } from "@/ui/cx";
import { CommitBar, NEXT_STEP_LABEL } from "@/ui/CommitBar";
import { Disclosure } from "@/ui/Disclosure";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { LiveRegion } from "@/ui/LiveRegion";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { SuccessNotice } from "@/ui/SuccessNotice";
import { formatDateTime } from "@/utils/formatDateTime";
import { DecisionDocument } from "../components/DecisionDocument";
import { ReadyDocumentSummary } from "../components/ReadyDocumentSummary";
import { SubmissionDialog } from "../components/SubmissionDialog";

const readyLoading = (
  <div className="flex flex-col gap-6">
    <LiveRegion>טוען את קורות החיים המוכנים…</LiveRegion>
    <Skeleton className="block h-40 w-full" />
    <Skeleton className="block h-64 w-full" />
  </div>
);

const CardHeading = ({
  children,
  className,
  icon: Icon,
  id,
}: {
  children: ReactNode;
  className?: string;
  icon: typeof FileCheck2;
  id: string;
}) => (
  <h2 className={cx("flex items-center gap-2 font-semibold text-cv-text", className)} id={id}>
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
  const [submissionNoticeOpen, setSubmissionNoticeOpen] = useState(false);
  const [downloadStarted, setDownloadStarted] = useState(false);

  const applicationQuery = useQuery(watchedApplicationDetailQueryOptions(applicationId));
  const detail = applicationQuery.data;
  const ready = detail?.preparation_state === "ready";
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
  /* A fact is listed by its own words; one the read carries without them has nothing
     to show the reader but an identifier, so it is left out. */
  const chosenFacts = (document?.facts ?? []).filter((fact) => fact.text != null && fact.text.trim() !== "");

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

  /* The way back to the editor is one of the ways into the document, listed with the
     decision and the facts behind it, rather than the bar's opening edge: the bar keeps
     the two things done with the file - download it, record the send - and on a phone the
     three together left none of them room to read. */
  const backLink = (
    <Link
      className={buttonClasses(
        "ghost",
        "w-fit max-lg:min-h-14 max-lg:w-full max-lg:justify-start max-lg:gap-2.5 max-lg:rounded-surface max-lg:border max-lg:border-cv-border max-lg:bg-cv-surface max-lg:px-4 max-lg:text-body max-lg:font-bold",
      )}
      to={routePaths.draft(applicationId)}
    >
      <PencilLine aria-hidden="true" className="size-icon-md" />
      <span className="max-lg:flex-1">חזרה לעריכת הטיוטה</span>
      <ChevronLeft aria-hidden="true" className="size-icon-md lg:hidden" />
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
            <Link className={buttonClasses("primary")} state={boardReturnState(applicationId)} to={boardPath()}>
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
      /* The design keeps this step's own title and line under the phone header: the
         finished document is the step's statement, not just its position. */
      phoneHeading="full"
      queryError={applicationQuery.error}
      stage="ready"
      title={detail !== undefined && !ready ? "קורות החיים אינם מוכנים כרגע" : undefined}
    >
      <QueryState
        error={applicationQuery.error}
        errorTitle="לא ניתן לטעון את קורות החיים המוכנים"
        loading={detail === undefined}
        loadingState={readyLoading}
        onRetry={() => void applicationQuery.refetch()}
      >
        {detail === undefined ? null : (
          <>
            {/* A phone's mark that the step is done, at the top of the body: the wide
                screen's spine shows it as its last step filled. */}
            {ready ? (
              <p className="-mb-3 flex w-fit items-center gap-1 rounded-pill bg-cv-surface-muted px-2.5 py-0.5 text-caption font-bold text-cv-text lg:hidden">
                <Check aria-hidden="true" className="size-icon-sm" />
                מוכן
              </p>
            ) : null}

            <PreparationAlerts detail={detail} screen="ready" />

            {/* The end of the flow, at the top of the step where the eye lands after the
                dialog closes. It used to be an edge-marked line under the cards and the
                folded extras, the same weight as any other notice on the page. */}
            {submissionNoticeOpen ? (
              <SuccessNotice emphasis="milestone" onDismiss={() => setSubmissionNoticeOpen(false)} title="ההגשה נרשמה">
                התוכן וקובצי ה־HTML וה־PDF שנשלחו נשמרו בהיסטוריית המועמדות.
              </SuccessNotice>
            ) : null}

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
                  className="flex min-w-0 flex-col gap-4 rounded-surface bg-cv-surface p-5 max-lg:p-4"
                >
                  {/* On a phone the file speaks through its summary below; the heading stays
                      for assistive tech, which reads the card by it. */}
                  <CardHeading className="max-lg:sr-only" icon={FileCheck2} id="ready-file-heading">
                    קובץ קורות החיים
                  </CardHeading>
                  {document === undefined ? null : (
                    <ReadyDocumentSummary approvedAt={detail.approved_at ?? null} language={document.language} />
                  )}
                  <p className="text-support leading-6 text-cv-text-muted max-lg:hidden">
                    הקובץ נוצר מהמסמך כפי שאושר
                    {detail.approved_at == null ? "" : ` ב־${formatDateTime(detail.approved_at)}`}. השרת בודק בעת ההורדה
                    שהמסמך עדיין מוכן, ולכן הקובץ שיורד הוא תמיד זה שמתאים לו.
                  </p>
                  {submittedAt === null ? null : (
                    <p className="text-support text-cv-text-muted">
                      ההגשה האחרונה של המסמך הזה נרשמה ב־{formatDateTime(submittedAt)}.
                    </p>
                  )}
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
                    <Disclosure summary="אפשרויות נוספות" variant="card">
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

                  <Disclosure flush summary="הסבר ההחלטות" variant="card">
                    <Card className="rounded-surface bg-cv-surface p-4 max-lg:border-0 max-lg:p-0 max-lg:pt-1">
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
                          fallbackDetail="קורות החיים עצמם זמינים. אפשר לרענן את העמוד ולנסות שוב."
                          title="לא ניתן לטעון את הסבר ההחלטה"
                        />
                      )}
                    </Card>
                  </Disclosure>

                  {/* The facts the document was built from, by their own words. */}
                  {chosenFacts.length === 0 ? null : (
                    <Disclosure summary={`העובדות שנבחרו לקורות החיים (${chosenFacts.length})`} variant="card">
                      <ul className="flex list-disc flex-col gap-1.5 ps-4 text-support text-cv-text">
                        {chosenFacts.map((fact) => (
                          <li dir="auto" key={fact.fact_id}>
                            {fact.text}
                          </li>
                        ))}
                      </ul>
                    </Disclosure>
                  )}

                  {backLink}
                </aside>
              </div>
            )}
          </>
        )}
      </QueryState>

      {/* The ready step's own bar, the same surface the two steps before it close with:
          what to do with the finished CV. */}
      {detail === undefined ? null : (
        <CommitBar
          label={NEXT_STEP_LABEL}
          /* The step's one command, with the download as its secondary beside it - the
             two things done with the finished file, in one place. The download once sat
             here beside the same button in the file card - two equal buttons for one
             action - so the card no longer carries one. */
          primary={nextStep === null ? undefined : nextStep.primary}
          {...(downloadButton === null ? {} : { secondary: downloadButton })}
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
          onRecorded={() => {
            setSubmissionRecorded(true);
            setSubmissionNoticeOpen(true);
          }}
          open={submissionOpen}
          previousSubmittedAt={submittedAt}
        />
      )}
    </WizardStepShell>
  );
};
