import { ArrowRight, FileText } from "lucide-react";
import { Link } from "react-router-dom";

import { ErrorCallout } from "../../app/ErrorCallout";
import { appRoutes } from "../../app/appRoutes";
import { useRequiredParam } from "../../app/useRequiredParam";
import { BackLink } from "../../ui/BackLink";
import { Button, buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Card } from "../../ui/Card";
import { PageShell } from "../../ui/PageShell";
import { QueryState } from "../../ui/QueryState";
import { SectionHeader } from "../../ui/SectionHeader";
import { reasonTitle } from "../application/applicationLabels";
import { FactLifecyclePanel } from "../facts/FactLifecyclePanel";
import { ActiveOperationPanel } from "../ActiveOperationPanel";
import { DraftApprovalDialog } from "./DraftApprovalDialog";
import { DraftClaimCard } from "./DraftClaimCard";
import { DraftConflictDialog } from "./DraftConflictDialog";
import { DraftFactPanel } from "./DraftFactPanel";
import { DraftHeaderCard } from "./DraftHeaderCard";
import { DraftPreview } from "./DraftPreview";
import { DraftRenderPanel } from "./DraftRenderPanel";
import { type ClaimHandlers, DraftSectionCard } from "./DraftSectionCard";
import { DraftValidationPanel } from "./DraftValidationPanel";
import { EditorLayout } from "./EditorLayout";
import { useDraftEditorState } from "./useDraftEditorState";

/* A.4 frame 3: the editor pane. Data and commands live in `useDraftEditorState`; what is
   left here is how they are drawn. */
export const DraftEditorPage = () => {
  const applicationId = useRequiredParam("applicationId");

  const {
    applicationQuery,
    approvalOpen,
    autosave,
    detail,
    draft,
    draftQuery,
    editClaim,
    exactPassingRunId,
    facts,
    includeFact,
    onExactPassingRun,
    operation,
    regeneration,
    regenerationAvailable,
    regenerationDisabled,
    removeClaim,
    renderRevisionId,
    selection,
    setApprovalOpen,
    setApprovedRevisionId,
    settingsPending,
    setValidationStale,
    unsaved,
    validationStale,
    watch,
    workingDraftId,
  } = useDraftEditorState(applicationId);

  const preparationHref = appRoutes.preparation(applicationId);

  return (
    <PageShell
      description={detail === undefined ? undefined : `תפקיד היעד: ${detail.application.target_role}`}
      eyebrow="סביבת עריכה"
      navigation={
        <BackLink label="חזרה להכנת קורות החיים" to={preparationHref}>
          הכנת קורות החיים
        </BackLink>
      }
      title="עריכה, אימות ואישור"
    >
      <QueryState
        error={applicationQuery.error}
        fallbackTitle="לא ניתן לטעון את מצב המועמדות"
        loading={detail === undefined}
        loadingLabel="טוען את מצב המועמדות…"
      />
      {draftQuery.error === null ? null : (
        <QueryState error={draftQuery.error} fallbackTitle="לא ניתן לטעון את הטיוטה" />
      )}

      {detail !== undefined && workingDraftId === null && renderRevisionId === null ? (
        <Callout
          action={
            <Link className={buttonClasses("primary")} to={preparationHref}>
              חזרה להכנת קורות החיים
            </Link>
          }
          title="אין כרגע טיוטה פעילה למועמדות הזו"
          tone="neutral"
        >
          מסך המועמדות מציג את המצב המדויק ואת הפעולה שיוצרת טיוטה.
        </Callout>
      ) : null}

      {detail === undefined ? null : (
        <DraftHeaderCard autosave={autosave} detail={detail} draft={draft} workingDraftId={workingDraftId} />
      )}

      {/* Live work, reported beside the draft it is rewriting rather than on a screen
            the user has to leave the text for. */}
      {operation === undefined ? null : <ActiveOperationPanel onQueued={watch} operation={operation} />}

      {/* The projection's own blockers. A claim with no fact behind it raises
            PENDING_FACT_REQUIRES_RESOLUTION there, and it is shown here as the reason it
            already is rather than as an approval rule this screen invented. */}
      {(detail?.review_reasons ?? []).map((reason) => (
        <Callout key={reason.code} title={reasonTitle(reason.code, "נדרשת החלטה לפני אישור הגרסה")} tone="blocker" />
      ))}

      {(detail?.stale_reasons ?? []).map((reason) => (
        <Callout
          key={reason.code}
          title={reasonTitle(reason.code, "הטיוטה אינה מעודכנת מול המקורות שלה")}
          tone="warning"
        />
      ))}

      {renderRevisionId !== null ? <DraftRenderPanel approvedRevisionId={renderRevisionId} onQueued={watch} /> : null}
      {renderRevisionId === null && draft === undefined && workingDraftId !== null && draftQuery.error === null ? (
        <QueryState loading loadingLabel="טוען את הטיוטה…" />
      ) : null}
      {renderRevisionId !== null || draft === undefined ? null : (() => {
        /* The five props every `DraftClaimCard` on this screen needs, bundled once: one
           draft, one facts read, one blur/edit/regenerate/remove policy for every claim,
           whichever section it sits in. */
        const claimHandlers: ClaimHandlers = {
          draft,
          facts,
          onBlur: autosave.flush,
          onEdit: editClaim,
          onRegenerate: (claim) => regeneration.mutate({ claimId: claim.claim_id }),
          onRemove: removeClaim,
          unsaved: regenerationDisabled,
        };

        return (
        <>
          <EditorLayout
            editor={
              <>
                <Card
                  aria-labelledby="draft-structure-heading"
                  className="flex flex-col gap-4 bg-cv-surface p-4 shadow-surface sm:p-5"
                >
                  <SectionHeader
                    actions={<span className="text-support text-cv-text-muted">מבוססים על הקשר המועמד</span>}
                    align="center"
                    gap="tight"
                    headingId="draft-structure-heading"
                    icon={FileText}
                    iconPresentation="inline"
                    title="כותרת ופרטי קשר"
                  />

                  <ul className="flex flex-col divide-y divide-cv-border">
                    <DraftClaimCard {...claimHandlers} claim={draft.outline.headline} />
                    {draft.outline.contacts.map((contact) => (
                      <DraftClaimCard {...claimHandlers} claim={contact} key={contact.claim_id} />
                    ))}
                  </ul>
                </Card>

                {draft.outline.sections.map((section, sectionIndex) => (
                  <DraftSectionCard
                    applicationId={applicationId}
                    claimHandlers={claimHandlers}
                    detail={detail}
                    key={section.name}
                    onRegenerateSection={() => regeneration.mutate({ section: section.name })}
                    regenerationDisabled={regenerationDisabled}
                    section={section}
                    sectionIndex={sectionIndex}
                  />
                ))}

                {regenerationAvailable || settingsPending ? null : (
                  <Callout title="יצירה מחדש באמצעות AI אינה זמינה" tone="neutral">
                    יש להגדיר ספק ולהפעיל AI במסך ההגדרות. לא יתבצע מעבר דטרמיניסטי שקט.
                    <div className="mt-3">
                      <Link className={buttonClasses("secondary")} to={appRoutes.settings}>
                        מעבר להגדרות
                      </Link>
                    </div>
                  </Callout>
                )}

                {regeneration.error === null ? null : (
                  <ErrorCallout
                    error={regeneration.error}
                    fallbackDetail="לא ניתן היה להפעיל יצירה מחדש. הטיוטה נשמרה כפי שהיא."
                    fallbackTitle="היצירה מחדש לא הופעלה"
                  />
                )}

                {unsaved ? (
                  <p className="text-support leading-6 text-cv-text-muted">
                    יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה הסתיימה.
                  </p>
                ) : null}

                {selection.error === null ? null : (
                  <ErrorCallout
                    error={selection.error}
                    fallbackDetail="לא ניתן היה לשנות את בחירת העובדות. הטיוטה נשמרה כפי שהיא."
                    fallbackTitle="שינוי הבחירה לא בוצע"
                  />
                )}

                <DraftFactPanel busy={selection.isPending} facts={facts} onInclude={includeFact} />

                <FactLifecyclePanel
                  profile={detail?.application.profile ?? null}
                  sections={draft.outline.sections.map((section) => section.name)}
                />

                <div>
                  <Link className={buttonClasses("secondary")} to={preparationHref}>
                    <ArrowRight aria-hidden="true" className="size-4" />
                    חזרה להכנת קורות החיים
                  </Link>
                </div>
              </>
            }
            preview={
              <>
                {/* The right pane is the document and everything said about it: the live
                      preview, the validation result for the exact version shown, and the
                      approval that follows from it. Those last two were screens; reaching
                      them meant leaving the text they describe. */}
                <DraftPreview draft={draft} />

                {/* One surface for the result and the decision it gates. The sentence
                      beside the button says only what the button cannot: why it is shut.
                      The panel's own heading already says whether the run passed, so the
                      second card that repeated it is gone. */}
                <DraftValidationPanel
                  applicationId={applicationId}
                  approval={
                    <>
                      {exactPassingRunId === null ? (
                        <p className="me-auto text-support leading-6 text-cv-text-muted">
                          האישור נפתח אחרי אימות שעבר על הגרסה המוצגת.
                        </p>
                      ) : null}
                      <Button disabled={exactPassingRunId === null} onClick={() => setApprovalOpen(true)}>
                        אישור הגרסה
                      </Button>
                    </>
                  }
                  draft={draft}
                  onExactPassingRun={onExactPassingRun}
                  stale={validationStale}
                />
              </>
            }
          />

          <DraftApprovalDialog
            applicationId={applicationId}
            detail={detail}
            draft={draft}
            onApproved={(revisionId) => {
              setApprovalOpen(false);
              setApprovedRevisionId(revisionId);
            }}
            onClose={() => setApprovalOpen(false)}
            onStale={() => {
              setApprovalOpen(false);
              setValidationStale(true);
            }}
            open={approvalOpen}
            validationRunId={exactPassingRunId}
          />

          <DraftConflictDialog
            current={draft}
            onDiscardLocal={autosave.discardLocal}
            onReapplyLocal={autosave.reapplyLocal}
            open={autosave.status === "conflict"}
            pending={autosave.pending}
            pendingRemovals={autosave.pendingRemovals}
          />
        </>
        );
      })()}
    </PageShell>
  );
};
