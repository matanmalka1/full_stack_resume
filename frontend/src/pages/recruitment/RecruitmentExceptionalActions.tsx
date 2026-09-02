import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import type { ApplicationDetail, RecruitmentStatus } from "../../api/contracts";
import { correctRecruitmentStatus, recordExternalSubmission } from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { FormActions } from "../../ui/FormActions";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { localDateTimeInputValue } from "../../ui/localDateTimeInputValue";
import { recruitmentStatusLabel, recruitmentStatusLabels } from "../application/applicationLabels";
import { statusEventLabel } from "./RecruitmentTimeline";
import { useServerSyncedField } from "../useServerSyncedField";

const allStatuses = Object.keys(recruitmentStatusLabels) as RecruitmentStatus[];

interface CorrectionFields {
  correctsEventId: string;
  reason: string;
  target: RecruitmentStatus;
}

interface ExternalSubmissionFields {
  note: string;
  submittedAt: string;
}

interface RecruitmentExceptionalActionsProps {
  detail: ApplicationDetail;
  kind: "correction" | "external-submission";
  onChanged: () => void;
}

export const RecruitmentExceptionalActions = ({ detail, kind, onChanged }: RecruitmentExceptionalActionsProps) => {
  const statusEvents = detail.recruitment_timeline.filter(
    (event) => event.item_type === "status_transition" || event.item_type === "status_correction",
  );
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [externalOpen, setExternalOpen] = useState(false);
  const correctionForm = useAppForm<CorrectionFields>({
    defaultValues: {
      correctsEventId: statusEvents.at(-1)?.id ?? "",
      reason: "",
      target: detail.recruitment_status as RecruitmentStatus,
    },
  });
  const externalForm = useAppForm<ExternalSubmissionFields>({
    defaultValues: { note: "", submittedAt: localDateTimeInputValue(new Date()) },
  });
  const correctionFields = correctionForm.watch();
  const eventChangedOnServer = useServerSyncedField({
    isDirty: correctionForm.formState.dirtyFields.correctsEventId === true,
    localValue: correctionFields.correctsEventId,
    onSync: (value) => correctionForm.resetField("correctsEventId", { defaultValue: value }),
    serverValue: statusEvents.at(-1)?.id ?? "",
  });
  const correction = useMutation({
    mutationFn: (fields: CorrectionFields) =>
      correctRecruitmentStatus(detail.application.id, {
        target_status: fields.target,
        corrects_event_id: fields.correctsEventId,
        reason: fields.reason,
      }),
    onSuccess: () => {
      correctionForm.resetField("reason", { defaultValue: "" });
      setCorrectionOpen(false);
      onChanged();
    },
  });
  const externalSubmission = useMutation({
    mutationFn: (fields: ExternalSubmissionFields) =>
      recordExternalSubmission(detail.application.id, {
        submitted_at: new Date(fields.submittedAt).toISOString(),
        artifact_version_id: null,
        metadata: fields.note.trim() === "" ? {} : { note: fields.note.trim() },
      }),
    onSuccess: () => {
      externalForm.resetField("note", { defaultValue: "" });
      setExternalOpen(false);
      onChanged();
    },
  });

  return (
    <>
      {kind === "correction" ? (
        <Button onClick={() => setCorrectionOpen(true)} variant="secondary">
          תיקון אירוע שנרשם
        </Button>
      ) : (
        <Button onClick={() => setExternalOpen(true)} variant="secondary">
          רישום הגשה חיצונית
        </Button>
      )}

      {kind === "correction" ? (
        <Dialog
          headingId="recruitment-correction-heading"
          onClose={() => setCorrectionOpen(false)}
          open={correctionOpen}
          title="תיקון אירוע שנרשם"
        >
          {statusEvents.length === 0 ? (
            <p className="text-support text-cv-text-muted">אין אירוע מצב שניתן לתקן.</p>
          ) : (
            <form
              className="grid gap-3 lg:grid-cols-2"
              id="recruitment-correction-form"
              onSubmit={correctionForm.handleSubmit((fields) => correction.mutate(fields))}
            >
              {correction.error === null ? null : (
                <ErrorCallout
                  className="lg:col-span-2"
                  error={correction.error}
                  fallbackDetail="אירוע התיקון לא נוסף. הרשומות הקיימות לא השתנו."
                  fallbackTitle="לא ניתן לתקן את האירוע"
                />
              )}
              {eventChangedOnServer ? (
                <Callout className="lg:col-span-2" role="status" title="ציר הזמן השתנה בשרת" tone="warning">
                  האירוע שבחרת נשמר בטופס ולא הוחלף. כדאי לבדוק אותו לפני השמירה.
                </Callout>
              ) : null}
              <Field label="האירוע השגוי">
                {(control) => (
                  <Select {...control} {...correctionForm.register("correctsEventId")}>
                    {statusEvents.map((item) => (
                      <option key={item.id} value={item.id}>
                        {statusEventLabel(item)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="המצב הנכון">
                {(control) => (
                  <Select {...control} {...correctionForm.register("target")}>
                    {allStatuses.map((status) => (
                      <option key={status} value={status}>
                        {recruitmentStatusLabel(status)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field className="lg:col-span-2" label="למה נדרש תיקון">
                {(control) => <TextArea {...control} {...correctionForm.register("reason")} required />}
              </Field>
              <FormActions className="lg:col-span-2">
                <Button onClick={() => setCorrectionOpen(false)} variant="secondary">
                  ביטול
                </Button>
                <Button disabled={correctionFields.reason.trim() === ""} pending={correction.isPending} type="submit">
                  הוספת אירוע תיקון
                </Button>
              </FormActions>
            </form>
          )}
        </Dialog>
      ) : null}

      {kind === "external-submission" ? (
        <Dialog
          headingId="recruitment-external-heading"
          onClose={() => setExternalOpen(false)}
          open={externalOpen}
          title="רישום הגשה שבוצעה מחוץ למערכת"
        >
          <form
            className="flex flex-col gap-3"
            onSubmit={externalForm.handleSubmit((fields) => externalSubmission.mutate(fields))}
          >
            {externalSubmission.error === null ? null : (
              <ErrorCallout
                error={externalSubmission.error}
                fallbackDetail="ההגשה לא נרשמה. הרשומות הקיימות לא השתנו."
                fallbackTitle="לא ניתן לרשום את ההגשה"
              />
            )}
            <Callout title="הרישום קבוע" tone="warning">
              ההגשה תתווסף להיסטוריה בלי להמציא גרסת קורות חיים או קובץ שלא נוצרו במערכת.
            </Callout>
            <Field label="מועד ההגשה">
              {(control) => (
                <TextInput {...control} {...externalForm.register("submittedAt")} required type="datetime-local" />
              )}
            </Field>
            <Field label="הערה (רשות)">
              {(control) => <TextArea {...control} {...externalForm.register("note")} />}
            </Field>
            <FormActions>
              <Button onClick={() => setExternalOpen(false)} variant="secondary">
                ביטול
              </Button>
              <Button pending={externalSubmission.isPending} pendingLabel="רושם…" type="submit">
                רישום ההגשה החיצונית
              </Button>
            </FormActions>
          </form>
        </Dialog>
      ) : null}
    </>
  );
};
