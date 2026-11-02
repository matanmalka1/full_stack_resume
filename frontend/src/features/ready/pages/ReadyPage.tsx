import { useQuery } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, CircleHelp, Download, PencilLine, Send } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { watchedApplicationDetailQueryOptions } from "@/api/applications";
import {
  decisionExportQueryOptions,
  documentPageCountQueryOptions,
  documentPdfHref,
  documentQueryOptions,
} from "@/api/documents";
import { boardPath, boardReturnState } from "@/navigation/boardReturn";
import { routePaths } from "@/navigation/routePaths";
import { useRequiredParam } from "@/navigation/useRequiredParam";
import { PreparationAlerts } from "@/features/preparation";
import { Button, buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { CommitBar } from "@/ui/CommitBar";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { ListCard, ListRow } from "@/ui/ListCard";
import { LiveRegion } from "@/ui/LiveRegion";
import { PageHeading } from "@/ui/PageHeading";
import { QueryState } from "@/ui/QueryState";
import { Skeleton } from "@/ui/Skeleton";
import { SuccessNotice } from "@/ui/SuccessNotice";
import { useIsPhone } from "@/ui/useIsPhone";
import { formatDateTime } from "@/utils/formatDateTime";
import { DecisionDocument } from "../components/DecisionDocument";
import { ReadyFileFacts, ReadyPageSketch } from "../components/ReadyDocumentSummary";
import { SubmissionDialog } from "../components/SubmissionDialog";

const readyLoading = (
  <div className="flex flex-col gap-4">
    <LiveRegion>טוען את קורות החיים המוכנים…</LiveRegion>
    <Skeleton className="block h-24 w-full" />
    <Skeleton className="block h-48 w-full" />
  </div>
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
   the system: recording a submission copies the content and files it sent.

   Drawn as the design draws it, without the wizard's stage bar: the finished page at the
   start of a wide screen, and beside it the statement, the file's facts, the two things
   done with it, and the ways into how it was made. On a phone the page shrinks to a
   thumbnail beside those facts and the two commands pin to the screen's bottom edge. */
export const ReadyPage = () => {
  const applicationId = useRequiredParam("applicationId");
  const isPhone = useIsPhone();
  const [submissionOpen, setSubmissionOpen] = useState(false);
  const [submissionRecorded, setSubmissionRecorded] = useState(false);
  const [submissionNoticeOpen, setSubmissionNoticeOpen] = useState(false);
  const [downloadStarted, setDownloadStarted] = useState(false);
  const [decisionOpen, setDecisionOpen] = useState(false);
  const [factsOpen, setFactsOpen] = useState(false);

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
  /* The render's own measure of the file. A count the server could not make leaves the
     format to stand alone. */
  const pagesQuery = useQuery({
    ...documentPageCountQueryOptions(applicationId, documentHash ?? ""),
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

  if (applicationQuery.error !== null) {
    /* A failed read owns the whole route surface, including its 404 frame. */
    return (
      <QueryState
        error={applicationQuery.error}
        errorTitle="לא ניתן לטעון את קורות החיים המוכנים"
        onRetry={() => void applicationQuery.refetch()}
      />
    );
  }

  const role = detail?.application.target_role;

  /* Download is the secondary command beside recording the submission, never a gate in
     front of it: both are offered together - download the file, and record the send it
     was for. */
  const downloadButton =
    !canDownload || documentHash === null ? null : (
      <a
        className={buttonClasses("secondary", "w-full", isPhone ? "large" : "default")}
        href={documentPdfHref(applicationId, documentHash)}
        key="download-pdf"
        onClick={() => setDownloadStarted(true)}
      >
        <Download aria-hidden="true" className="size-icon-lg" />
        {downloadStarted || submissionExists ? "הורדת PDF שוב" : "הורדת PDF"}
      </a>
    );

  const primary = !ready ? null : submissionExists ? (
    <Link
      className={buttonClasses("primary", "w-full shadow-action", isPhone ? "large" : "default")}
      state={boardReturnState(applicationId)}
      to={boardPath()}
    >
      <Check aria-hidden="true" className="size-icon-lg" />
      סיום וחזרה ללוח
    </Link>
  ) : (
    <Button
      className="w-full shadow-action"
      disabled={!canSubmit}
      onClick={() => setSubmissionOpen(true)}
      size={isPhone ? "large" : "default"}
    >
      <Send aria-hidden="true" className="size-icon-lg" />
      רישום הגשה
    </Button>
  );

  const statement = !ready
    ? "קורות החיים יחזרו להיות מוכנים לאחר בדיקה, אישור ויצירת הקבצים מחדש בעורך. הגשות שכבר נרשמו אינן משתנות."
    : submissionExists
      ? "ההגשה נרשמה. תהליך הכנת קורות החיים הושלם."
      : "הורידו את הקובץ ומסרו אותו למגייס, ואז רשמו כאן שההגשה בוצעה.";

  return (
    <section
      aria-labelledby="route-heading"
      className="page-frame max-lg:flex max-lg:min-h-[calc(100dvh-2.5rem)] max-lg:flex-col"
    >
      {/* Where the screen sits: on a phone the top bar's way back to the Application with
          who the CV is for beside it, on a wide screen the trail from the board. */}
      <header className="-mx-2 -mt-1.5 mb-1 flex items-center gap-1 lg:hidden">
        <Link
          aria-label="חזרה לפרטי המועמדות"
          className="flex size-11 shrink-0 items-center justify-center rounded-control text-cv-text"
          to={routePaths.application(applicationId)}
        >
          <ChevronRight aria-hidden="true" className="size-icon-lg" />
        </Link>
        {detail === undefined ? null : (
          <p className="min-w-0 truncate text-caption text-cv-text-muted" dir="auto">
            {`${detail.application.target_role} · ${detail.application.company}`}
          </p>
        )}
      </header>
      <nav aria-label="מיקום" className="mb-5.5 text-support text-cv-text-muted max-lg:hidden">
        <ol className="flex flex-wrap items-center gap-1.5">
          <li>
            <Link className="underline hover:text-cv-text" state={boardReturnState(applicationId)} to={boardPath()}>
              לוח המועמדויות
            </Link>
          </li>
          <li aria-hidden="true">/</li>
          <li>
            {role === undefined ? (
              <Skeleton className="inline-block w-32 align-middle" />
            ) : (
              <Link className="underline hover:text-cv-text" dir="auto" to={routePaths.application(applicationId)}>
                {role}
              </Link>
            )}
          </li>
          <li aria-hidden="true">/</li>
          <li aria-current="page">מוכן למסירה</li>
        </ol>
      </nav>

      <div className="flex items-start gap-8">
        {ready ? <ReadyPageSketch className="max-w-130 flex-1 max-lg:hidden" size="large" /> : null}

        <div className="flex min-w-0 flex-1 flex-col gap-4.5 max-lg:gap-4 lg:max-w-150">
          <div>
            {ready ? (
              <p className="mb-2 inline-flex items-center gap-1.25 rounded-pill bg-cv-surface-muted px-2.5 py-1 text-caption font-bold text-cv-text lg:mb-2.5">
                <Check aria-hidden="true" className="size-icon-sm" />
                מוכן
              </p>
            ) : null}
            <PageHeading description={detail === undefined ? undefined : statement} id="route-heading">
              {detail !== undefined && !ready ? "קורות החיים אינם מוכנים כרגע" : "קורות החיים מוכנים"}
            </PageHeading>
          </div>

          <QueryState loading={detail === undefined} loadingState={readyLoading} />

          {detail === undefined ? null : (
            <>
              <PreparationAlerts detail={detail} screen="ready" />

              {/* The end of the flow, at the top of the step where the eye lands after the
                  dialog closes. */}
              {submissionNoticeOpen ? (
                <SuccessNotice
                  emphasis="milestone"
                  onDismiss={() => setSubmissionNoticeOpen(false)}
                  title="ההגשה נרשמה"
                >
                  התוכן וקובצי ה־HTML וה־PDF שנשלחו נשמרו בהיסטוריית המועמדות.
                </SuccessNotice>
              ) : null}

              {ready ? null : (
                /* Reached from a link after the document changed. Nothing here is lost: the
                   editor holds the document as it is now, and approving and rendering it
                   again brings this step back. */
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
                  הגשות שכבר נרשמו אינן משתנות.
                </Callout>
              )}

              {!ready ? null : (
                <>
                  <div className="flex items-stretch gap-3.5">
                    <ReadyPageSketch className="lg:hidden" size="small" />
                    {document === undefined ? (
                      <Skeleton className="block h-24 w-full" />
                    ) : (
                      <ReadyFileFacts
                        approvedAt={detail.approved_at ?? null}
                        language={document.language}
                        pages={pagesQuery.data?.pages ?? null}
                      />
                    )}
                  </div>

                  {/* A wide screen's two commands, under the file they act on. A phone pins
                      the same two to its bottom edge instead. */}
                  {isPhone ? null : (
                    <div className="flex gap-2.5 *:flex-1">
                      {downloadButton}
                      {primary}
                    </div>
                  )}

                  <ListCard label="על המסמך">
                    <ListRow
                      icon={isPhone ? CircleHelp : undefined}
                      label="הסבר ההחלטות"
                      onClick={() => setDecisionOpen(true)}
                    />
                    {chosenFacts.length === 0 ? null : (
                      <ListRow
                        icon={isPhone ? BookOpen : undefined}
                        label="העובדות שנבחרו לקורות החיים"
                        onClick={() => setFactsOpen(true)}
                        trailing={String(chosenFacts.length)}
                      />
                    )}
                    {/* Another send of the same file is a record of its own, kept out of
                        the way of the first. */}
                    {submissionExists ? (
                      <ListRow
                        icon={isPhone ? Send : undefined}
                        label="רישום הגשה נוספת"
                        onClick={canSubmit ? () => setSubmissionOpen(true) : undefined}
                      />
                    ) : null}
                    <ListRow
                      icon={isPhone ? PencilLine : undefined}
                      label="חזרה לעריכת הטיוטה"
                      to={routePaths.draft(applicationId)}
                    />
                  </ListCard>

                  <p className="text-support leading-6 text-cv-text-muted">
                    המסמך המוכן נשאר זמין כל עוד לא שונה. עריכה מחזירה אותו לטיוטה, וההגשות שנרשמו נשמרות כפי שנשלחו.
                    {submittedAt === null
                      ? null
                      : ` ההגשה האחרונה של המסמך הזה נרשמה ב־${formatDateTime(submittedAt)}.`}
                  </p>
                </>
              )}
            </>
          )}
        </div>
      </div>

      {/* A phone's two commands: the bar pinned to the screen's bottom edge. */}
      {isPhone && ready && primary !== null ? (
        <>
          {/* Takes what a short page leaves of the screen, so the bar stands at its bottom
              edge; the bar stays a child of the frame so `sticky` can pin it. */}
          <div aria-hidden="true" className="min-h-6 flex-1" />
          <CommitBar primary={primary} {...(downloadButton === null ? {} : { secondary: downloadButton })} />
        </>
      ) : null}

      <Dialog
        headingId="ready-decision-heading"
        onClose={() => setDecisionOpen(false)}
        open={decisionOpen}
        size="wide"
        title="הסבר ההחלטות"
      >
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
      </Dialog>

      <Dialog
        headingId="ready-facts-heading"
        onClose={() => setFactsOpen(false)}
        open={factsOpen}
        title="העובדות שנבחרו לקורות החיים"
      >
        {/* The facts the document was built from, by their own words. */}
        <ul className="flex list-disc flex-col gap-1.5 ps-4 text-support text-cv-text">
          {chosenFacts.map((fact) => (
            <li dir="auto" key={fact.fact_id}>
              {fact.text}
            </li>
          ))}
        </ul>
      </Dialog>

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
    </section>
  );
};
