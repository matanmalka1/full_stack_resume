import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { applicationDetailQueryKey, applicationListQueryPrefix } from "../../api/applications";
import type {
  ApplicationDetail,
  RecruitmentStatus,
  RecruitmentTimelineItem,
  TransitionableRecruitmentStatus,
} from "../../api/contracts";
import {
  correctRecruitmentStatus,
  recordExternalSubmission,
  setNextAction,
  transitionRecruitmentStatus,
} from "../../api/tracking";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { Select } from "../../ui/Select";
import { TextArea, TextInput } from "../../ui/TextInput";
import { recruitmentStatusLabel, recruitmentStatusLabels } from "../application/applicationLabels";
import { useServerSyncedField } from "./useServerSyncedField";

const dateTimeFormat = new Intl.DateTimeFormat("he-IL", {
  dateStyle: "medium",
  timeStyle: "short",
});

const formatDateTime = (value: string): string => {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : dateTimeFormat.format(parsed);
};

const localDateTimeValue = (): string => {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
};

const allStatuses = Object.keys(recruitmentStatusLabels) as RecruitmentStatus[];

interface TransitionFields {
  reason: string;
  target: TransitionableRecruitmentStatus | "";
}

interface NextActionFields {
  action: string;
  date: string;
}

interface CorrectionFields {
  correctsEventId: string;
  reason: string;
  target: RecruitmentStatus;
}

interface ExternalSubmissionFields {
  note: string;
  submittedAt: string;
}

const statusEventLabel = (event: RecruitmentTimelineItem): string =>
  `${formatDateTime(event.occurred_at)} · ${recruitmentStatusLabel(event.to_status ?? "saved")}`;

const timelineDescription = (
  event: RecruitmentTimelineItem,
  byId: ReadonlyMap<string, RecruitmentTimelineItem>,
): string => {
  if (event.item_type === "submission") {
    return event.submission_type === "internal" ? "נרשמה הגשה של הגרסה המוכנה" : "נרשמה הגשה שבוצעה מחוץ למערכת";
  }
  if (event.item_type === "next_action") {
    return event.next_action == null
      ? "הפעולה הבאה נוקתה"
      : `הפעולה הבאה נקבעה: ${event.next_action}${
          event.next_action_date == null ? "" : ` · ${event.next_action_date}`
        }`;
  }
  if (event.item_type === "status_correction") {
    const corrected = event.corrects_event_id == null ? undefined : byId.get(event.corrects_event_id);
    const target = recruitmentStatusLabel(event.to_status ?? "saved");
    return corrected === undefined
      ? `מצב הגיוס תוקן ל־${target}`
      : `האירוע „${statusEventLabel(corrected)}” תוקן ל־${target}`;
  }
  return `מצב הגיוס עבר מ־${recruitmentStatusLabel(
    event.from_status ?? "saved",
  )} ל־${recruitmentStatusLabel(event.to_status ?? "saved")}`;
};

/* The two everyday recruitment controls, the timeline they write into, and two dialogs.

   Correction and external submission are behind dialogs rather than disclosures because
   neither is part of the ordinary rhythm of the screen: one repairs a record that was
   entered wrong, the other logs a submission this system did not produce. As `<details>`
   they sat permanently between the controls and the history, two closed boxes the reader
   scrolled past every visit to reach the timeline. They keep their exact commands and
   their exact warnings; only where they live changed. */
export const RecruitmentPanel = ({ detail }: { detail: ApplicationDetail }) => {
  const applicationId = detail.application.id;
  const queryClient = useQueryClient();
  const statusEvents = detail.recruitment_timeline.filter(
    (event) => event.item_type === "status_transition" || event.item_type === "status_correction",
  );
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [externalOpen, setExternalOpen] = useState(false);
  const transitionForm = useAppForm<TransitionFields>({
    defaultValues: {
      reason: "",
      target: detail.allowed_recruitment_transitions[0] ?? "",
    },
  });
  const nextActionForm = useAppForm<NextActionFields>({
    defaultValues: {
      action: detail.application.next_action ?? "",
      date: detail.application.next_action_date ?? "",
    },
  });
  const correctionForm = useAppForm<CorrectionFields>({
    defaultValues: {
      correctsEventId: statusEvents.at(-1)?.id ?? "",
      reason: "",
      target: (detail.recruitment_status as RecruitmentStatus) ?? "saved",
    },
  });
  const externalForm = useAppForm<ExternalSubmissionFields>({
    defaultValues: { note: "", submittedAt: localDateTimeValue() },
  });
  const transitionFields = transitionForm.watch();
  const nextActionFields = nextActionForm.watch();
  const correctionFields = correctionForm.watch();

  const transitionChangedOnServer = useServerSyncedField({
    changeToken: detail.allowed_recruitment_transitions.join("|"),
    isDirty: transitionForm.formState.dirtyFields.target === true,
    localValue: transitionFields.target,
    onSync: (value) =>
      transitionForm.resetField("target", {
        defaultValue: value as TransitionableRecruitmentStatus | "",
      }),
    serverValue: detail.allowed_recruitment_transitions[0] ?? "",
  });
  const nextActionChangedOnServer = useServerSyncedField({
    isDirty: nextActionForm.formState.dirtyFields.action === true,
    localValue: nextActionFields.action,
    onSync: (value) => nextActionForm.resetField("action", { defaultValue: value }),
    serverValue: detail.application.next_action ?? "",
  });
  const nextActionDateChangedOnServer = useServerSyncedField({
    isDirty: nextActionForm.formState.dirtyFields.date === true,
    localValue: nextActionFields.date,
    onSync: (value) => nextActionForm.resetField("date", { defaultValue: value }),
    serverValue: detail.application.next_action_date ?? "",
  });
  /* The correction dialog opens on the latest recorded event. Once the user chooses an
     older event, append-only timeline refreshes may offer a newer default but may not
     replace that explicit choice. */
  const correctionEventChangedOnServer = useServerSyncedField({
    isDirty: correctionForm.formState.dirtyFields.correctsEventId === true,
    localValue: correctionFields.correctsEventId,
    onSync: (value) => correctionForm.resetField("correctsEventId", { defaultValue: value }),
    serverValue: statusEvents.at(-1)?.id ?? "",
  });
  const hasTransitionChoice = detail.allowed_recruitment_transitions.length > 0 || transitionFields.target !== "";

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    void queryClient.invalidateQueries({ queryKey: applicationListQueryPrefix });
  };
  const transition = useMutation({
    mutationFn: (fields: TransitionFields) => {
      if (fields.target === "") throw new Error("No transition target");
      return transitionRecruitmentStatus(applicationId, {
        target_status: fields.target,
        reason: fields.reason,
      });
    },
    onSuccess: () => {
      transitionForm.resetField("reason", { defaultValue: "" });
      refresh();
    },
  });
  const correction = useMutation({
    mutationFn: (fields: CorrectionFields) =>
      correctRecruitmentStatus(applicationId, {
        target_status: fields.target,
        corrects_event_id: fields.correctsEventId,
        reason: fields.reason,
      }),
    onSuccess: () => {
      correctionForm.resetField("reason", { defaultValue: "" });
      setCorrectionOpen(false);
      refresh();
    },
  });
  const nextActionMutation = useMutation({
    mutationFn: ({ clear, fields }: { clear: boolean; fields: NextActionFields }) =>
      setNextAction(applicationId, {
        next_action: clear ? null : fields.action.trim() || null,
        next_action_date: clear ? null : fields.date || null,
      }),
    onSuccess: refresh,
  });
  const externalSubmission = useMutation({
    mutationFn: (fields: ExternalSubmissionFields) =>
      recordExternalSubmission(applicationId, {
        submitted_at: new Date(fields.submittedAt).toISOString(),
        artifact_version_id: null,
        metadata: fields.note.trim() === "" ? {} : { note: fields.note.trim() },
      }),
    onSuccess: () => {
      externalForm.resetField("note", { defaultValue: "" });
      setExternalOpen(false);
      refresh();
    },
  });
  const error = transition.error ?? correction.error ?? nextActionMutation.error ?? externalSubmission.error;
  const timelineById = useMemo(
    () => new Map(detail.recruitment_timeline.map((event) => [event.id, event])),
    [detail.recruitment_timeline],
  );

  return (
    <section aria-labelledby="recruitment-heading" className="flex flex-col gap-6">
      <h2 className="sr-only" id="recruitment-heading">
        מעקב גיוס
      </h2>

      {error === null ? null : (
        <ErrorCallout
          error={error}
          fallbackDetail="העדכון לא נשמר. הרשומות הקיימות לא השתנו."
          fallbackTitle="לא ניתן לעדכן את מעקב הגיוס"
        />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <form
          className="flex flex-col gap-3"
          onSubmit={transitionForm.handleSubmit((fields) => transition.mutate(fields))}
        >
          <h3 className="font-semibold text-cv-text">עדכון שלב</h3>
          {transitionChangedOnServer ? (
            <Callout role="status" title="אפשרויות המעבר השתנו בשרת" tone="warning">
              הבחירה שלך נשמרה בטופס ולא הוחלפה. כדאי לבדוק אותה לפני השמירה.
            </Callout>
          ) : null}
          {!hasTransitionChoice ? (
            <p className="text-support text-cv-text-muted">אין מעבר ישיר זמין מהמצב הנוכחי.</p>
          ) : (
            <>
              <Field label="השלב הבא">
                {(control) => (
                  <Select {...control} {...transitionForm.register("target")}>
                    {transitionFields.target !== "" &&
                    !detail.allowed_recruitment_transitions.includes(transitionFields.target) ? (
                      <option value={transitionFields.target}>
                        {recruitmentStatusLabel(transitionFields.target)} · הבחירה שלך
                      </option>
                    ) : null}
                    {detail.allowed_recruitment_transitions.map((status) => (
                      <option key={status} value={status}>
                        {recruitmentStatusLabel(status)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="סיבה (רשות)">
                {(control) => <TextInput {...control} {...transitionForm.register("reason")} />}
              </Field>
              <Button pending={transition.isPending} pendingLabel="שומר…" type="submit">
                שמירת השלב
              </Button>
            </>
          )}
        </form>

        <form
          className="flex flex-col gap-3"
          onSubmit={nextActionForm.handleSubmit((fields) => nextActionMutation.mutate({ clear: false, fields }))}
        >
          <h3 className="font-semibold text-cv-text">הפעולה הבאה</h3>
          {nextActionChangedOnServer || nextActionDateChangedOnServer ? (
            <Callout role="status" title="הפעולה הבאה השתנתה בשרת" tone="warning">
              הערכים שהקלדת נשמרו בטופס ולא הוחלפו. כדאי לבדוק אותם לפני השמירה.
            </Callout>
          ) : null}
          <Field label="מה לעשות">
            {(control) => <TextInput {...control} {...nextActionForm.register("action")} />}
          </Field>
          <Field label="תאריך">
            {(control) => <TextInput {...control} {...nextActionForm.register("date")} type="date" />}
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button pending={nextActionMutation.isPending} type="submit">
              שמירת הפעולה
            </Button>
            <Button
              disabled={
                nextActionMutation.isPending ||
                (detail.application.next_action == null && detail.application.next_action_date == null)
              }
              onClick={() => nextActionMutation.mutate({ clear: true, fields: nextActionForm.getValues() })}
              variant="secondary"
            >
              סימון כהושלם וניקוי
            </Button>
          </div>
        </form>
      </div>

      <div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="font-semibold text-cv-text">ציר הזמן</h3>
          {/* The two exceptional records, offered beside the history they write into
              rather than as forms of their own. */}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => setCorrectionOpen(true)} variant="secondary">
              תיקון אירוע שנרשם
            </Button>
            <Button onClick={() => setExternalOpen(true)} variant="secondary">
              רישום הגשה חיצונית
            </Button>
          </div>
        </div>
        {detail.recruitment_timeline.length === 0 ? (
          <p className="mt-3 text-support text-cv-text-muted">עדיין אין אירועים.</p>
        ) : (
          <ol className="mt-4 flex flex-col gap-3">
            {[...detail.recruitment_timeline].reverse().map((event) => (
              <li className="border-s-2 border-cv-border ps-4" key={event.id}>
                <p className="font-medium text-cv-text" dir="auto">
                  {timelineDescription(event, timelineById)}
                </p>
                <p className="text-support text-cv-text-muted">
                  {formatDateTime(event.occurred_at)}
                  {event.actor_type === "user" ? " · אתה" : ""}
                </p>
                {event.reason === "" ? null : (
                  <p className="mt-1 text-support text-cv-text-muted" dir="auto">
                    {event.reason}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* A correction adds an event; it never rewrites the one it corrects. Escape may
          cancel it for exactly that reason: nothing is discarded but a form. */}
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
            {correctionEventChangedOnServer ? (
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
            <div className="flex flex-wrap justify-end gap-3 lg:col-span-2">
              <Button onClick={() => setCorrectionOpen(false)} variant="secondary">
                ביטול
              </Button>
              <Button disabled={correctionFields.reason.trim() === ""} pending={correction.isPending} type="submit">
                הוספת אירוע תיקון
              </Button>
            </div>
          </form>
        )}
      </Dialog>

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
          <Callout title="הרישום קבוע" tone="warning">
            ההגשה תתווסף להיסטוריה בלי להמציא גרסת קורות חיים או קובץ שלא נוצרו במערכת.
          </Callout>
          <Field label="מועד ההגשה">
            {(control) => (
              <TextInput {...control} {...externalForm.register("submittedAt")} required type="datetime-local" />
            )}
          </Field>
          <Field label="הערה (רשות)">{(control) => <TextArea {...control} {...externalForm.register("note")} />}</Field>
          <div className="flex flex-wrap justify-end gap-3">
            <Button onClick={() => setExternalOpen(false)} variant="secondary">
              ביטול
            </Button>
            <Button pending={externalSubmission.isPending} pendingLabel="רושם…" type="submit">
              רישום ההגשה החיצונית
            </Button>
          </div>
        </form>
      </Dialog>
    </section>
  );
};
