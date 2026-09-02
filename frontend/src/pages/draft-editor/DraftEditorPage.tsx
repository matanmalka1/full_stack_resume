import { ArrowRight, FileText, Layers3, RefreshCw } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ErrorCallout } from "../../app/ErrorCallout";
import { appRoutes } from "../../app/appRoutes";
import { BackLink } from "../../ui/BackLink";
import { Button, buttonClasses } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Card } from "../../ui/Card";
import { LtrText } from "../../ui/LtrText";
import { PageShell } from "../../ui/PageShell";
import { QueryState } from "../../ui/QueryState";
import { StatusBadge } from "../../ui/StatusBadge";
import { SectionHeader } from "../../ui/SectionHeader";
import { reasonTitle, workingDraftStateLabels, workingDraftStateTones } from "../application/applicationLabels";
import { FactLifecyclePanel } from "../FactLifecyclePanel";
import { ClaimFactResolution } from "./ClaimFactResolution";
import { DraftApprovalDialog } from "./DraftApprovalDialog";
import { DraftClaimCard } from "./DraftClaimCard";
import { DraftConflictDialog } from "./DraftConflictDialog";
import { DraftFactPanel } from "./DraftFactPanel";
import { DraftPreview } from "./DraftPreview";
import { DraftRenderPanel } from "./DraftRenderPanel";
import { DraftSaveState } from "./DraftSaveState";
import { DraftValidationPanel } from "./DraftValidationPanel";
import { EditorLayout } from "./EditorLayout";
import { useDraftEditorState } from "./useDraftEditorState";

/* A.4 frame 3: the editor pane. Data and commands live in `useDraftEditorState`; what is
   left here is how they are drawn. */
export const DraftEditorPage = () => {
  const { applicationId } = useParams();

  if (applicationId === undefined) {
    throw new Error("DraftEditorPage rendered without an applicationId route parameter");
  }

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
    operationPanel,
    regeneration,
    regenerationAvailable,
    regenerationDisabled,
    removeClaim,
    renderRevisionId,
    selection,
    setApprovalOpen,
    setApprovedRevisionId,
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
        <Card className="flex flex-wrap items-center justify-between gap-4 bg-cv-surface p-4 shadow-surface">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid size-10 shrink-0 place-items-center rounded-control bg-cv-accent-soft text-cv-accent">
              <FileText aria-hidden="true" className="size-5" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-body font-bold text-cv-text" dir="auto">
                {detail.application.company}
              </p>
              <p className="truncate text-support text-cv-text-muted" dir="auto">
                {detail.application.target_role}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-end gap-2">
            {draft === undefined ? null : (
              <LtrText
                className="rounded-pill border border-cv-border bg-cv-surface-muted px-2.5 py-1 text-support text-cv-text-muted"
                mono
                title={draft.content_hash}
              >
                v{draft.edit_version} · {draft.content_hash.slice(0, 10)}
              </LtrText>
            )}
            <StatusBadge tone={workingDraftStateTones[detail.working_draft_state]}>
              {workingDraftStateLabels[detail.working_draft_state]}
            </StatusBadge>
            {workingDraftId === null ? null : <DraftSaveState state={autosave} />}
          </div>
        </Card>
      )}

      {/* Live work, reported beside the draft it is rewriting rather than on a screen
            the user has to leave the text for. */}
      {operationPanel}

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
      {renderRevisionId === null && draft !== undefined ? (
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
                    <DraftClaimCard
                      claim={draft.outline.headline}
                      draft={draft}
                      facts={facts}
                      onBlur={autosave.flush}
                      onEdit={editClaim}
                      onRegenerate={(claim) => regeneration.mutate({ claimId: claim.claim_id })}
                      onRemove={removeClaim}
                      unsaved={regenerationDisabled}
                    />
                    {draft.outline.contacts.map((contact) => (
                      <DraftClaimCard
                        claim={contact}
                        draft={draft}
                        facts={facts}
                        key={contact.claim_id}
                        onBlur={autosave.flush}
                        onEdit={editClaim}
                        onRegenerate={(claim) => regeneration.mutate({ claimId: claim.claim_id })}
                        onRemove={removeClaim}
                        unsaved={regenerationDisabled}
                      />
                    ))}
                  </ul>
                </Card>

                {draft.outline.sections.map((section, sectionIndex) => (
                  <Card
                    aria-labelledby={`draft-section-${sectionIndex}`}
                    className="flex flex-col gap-2 bg-cv-surface p-4 shadow-surface sm:p-5"
                    key={section.name}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-cv-border pb-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <Layers3 aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
                        <h3
                          className="truncate text-heading-sm font-bold text-cv-text"
                          dir="auto"
                          id={`draft-section-${sectionIndex}`}
                        >
                          {section.name}
                        </h3>
                        <span className="shrink-0 text-support text-cv-text-muted">{section.claims.length} שורות</span>
                      </div>
                      <Button
                        disabled={regenerationDisabled}
                        onClick={() => regeneration.mutate({ section: section.name })}
                        variant="secondary"
                      >
                        <RefreshCw aria-hidden="true" className="size-4" />
                        יצירה מחדש של הפרק
                      </Button>
                    </div>
                    {section.claims.length === 0 ? (
                      <p className="text-support leading-6 text-cv-text-muted">אין כרגע שורות בסעיף הזה.</p>
                    ) : (
                      <ul className="flex flex-col divide-y divide-cv-border">
                        {section.claims.map((claim) => (
                          <DraftClaimCard
                            claim={claim}
                            draft={draft}
                            factResolution={
                              <ClaimFactResolution
                                analysisId={detail?.active_analysis_id ?? null}
                                applicationId={applicationId}
                                claim={claim}
                                draft={draft}
                                language={facts?.language ?? detail?.application.language ?? "en"}
                                profile={detail?.application.profile ?? null}
                                section={section.name}
                              />
                            }
                            facts={facts}
                            key={claim.claim_id}
                            onBlur={autosave.flush}
                            onEdit={editClaim}
                            onRegenerate={(claim) => regeneration.mutate({ claimId: claim.claim_id })}
                            onRemove={removeClaim}
                            unsaved={regenerationDisabled}
                          />
                        ))}
                      </ul>
                    )}
                  </Card>
                ))}

                {regenerationAvailable ? null : (
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
      ) : null}
    </PageShell>
  );
};
