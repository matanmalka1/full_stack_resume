import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import { applicationDetailQueryKey } from "../api/applications";
import type {
  ApplicationDetail,
  RecruitmentStatus,
  RecruitmentTimelineItem,
  TransitionableRecruitmentStatus,
} from "../api/contracts";
import {
  correctRecruitmentStatus,
  recordExternalSubmission,
  setNextAction,
  transitionRecruitmentStatus,
} from "../api/tracking";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Dialog } from "../ui/Dialog";
import { Field } from "../ui/Field";
import { Select } from "../ui/Select";
import { TextArea, TextInput } from "../ui/TextInput";
import { recruitmentStatusLabel, recruitmentStatusLabels } from "./applicationLabels";

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

const statusEventLabel = (event: RecruitmentTimelineItem): string =>
  `${formatDateTime(event.occurred_at)} · ${recruitmentStatusLabel(event.to_status ?? "saved")}`;

const timelineDescription = (
  event: RecruitmentTimelineItem,
  byId: ReadonlyMap<string, RecruitmentTimelineItem>,
): string => {
  if (event.item_type === "submission") {
    return event.submission_type === "internal"
      ? "נרשמה הגשה של הגרסה המוכנה"
      : "נרשמה הגשה שבוצעה מחוץ למערכת";
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
  const [transitionTarget, setTransitionTarget] = useState<TransitionableRecruitmentStatus | "">(
    detail.allowed_recruitment_transitions[0] ?? "",
  );
  const [transitionReason, setTransitionReason] = useState("");
  const statusEvents = detail.recruitment_timeline.filter(
    (event) => event.item_type === "status_transition" || event.item_type === "status_correction",
  );
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [externalOpen, setExternalOpen] = useState(false);
  const [correctsEventId, setCorrectsEventId] = useState(statusEvents.at(-1)?.id ?? "");
  const [correctionTarget, setCorrectionTarget] = useState<RecruitmentStatus>(
    (detail.recruitment_status as RecruitmentStatus) ?? "saved",
  );
  const [correctionReason, setCorrectionReason] = useState("");
  const [nextAction, setNextActionValue] = useState(detail.application.next_action ?? "");
  const [nextActionDate, setNextActionDate] = useState(detail.application.next_action_date ?? "");
  const [externalSubmittedAt, setExternalSubmittedAt] = useState(localDateTimeValue);
  const [externalNote, setExternalNote] = useState("");

  useEffect(() => {
    setTransitionTarget(detail.allowed_recruitment_transitions[0] ?? "");
  }, [detail.allowed_recruitment_transitions.join("|")]);
  useEffect(() => {
    setNextActionValue(detail.application.next_action ?? "");
    setNextActionDate(detail.application.next_action_date ?? "");
  }, [detail.application.next_action, detail.application.next_action_date]);
  /* The correction dialog opens on the latest recorded event, which is the one a mistake
     is almost always in. Bound to the events rather than set once, so a transition made
     while the screen is open does not leave the dialog offering to correct a stale row. */
  useEffect(() => {
    setCorrectsEventId(statusEvents.at(-1)?.id ?? "");
  }, [statusEvents.map((event) => event.id).join("|")]);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    void queryClient.invalidateQueries({ queryKey: ["applications"] });
  };
  const transition = useMutation({
    mutationFn: () => {
      if (transitionTarget === "") throw new Error("No transition target");
      return transitionRecruitmentStatus(applicationId, {
        target_status: transitionTarget,
        reason: transitionReason,
      });
    },
    onSuccess: () => {
      setTransitionReason("");
      refresh();
    },
  });
  const correction = useMutation({
    mutationFn: () =>
      correctRecruitmentStatus(applicationId, {
        target_status: correctionTarget,
        corrects_event_id: correctsEventId,
        reason: correctionReason,
      }),
    onSuccess: () => {
      setCorrectionReason("");
      setCorrectionOpen(false);
      refresh();
    },
  });
  const nextActionMutation = useMutation({
    mutationFn: (clear: boolean) =>
      setNextAction(applicationId, {
        next_action: clear ? null : nextAction.trim() || null,
        next_action_date: clear ? null : nextActionDate || null,
      }),
    onSuccess: refresh,
  });
  const externalSubmission = useMutation({
    mutationFn: () =>
      recordExternalSubmission(applicationId, {
        submitted_at: new Date(externalSubmittedAt).toISOString(),
        artifact_version_id: null,
        metadata: externalNote.trim() === "" ? {} : { note: externalNote.trim() },
      }),
    onSuccess: () => {
      setExternalNote("");
      setExternalOpen(false);
      refresh();
    },
  });
  const error =
    transition.error ?? correction.error ?? nextActionMutation.error ?? externalSubmission.error;
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
          onSubmit={(event) => {
            event.preventDefault();
            transition.mutate();
          }}
        >
          <h3 className="font-semibold text-cv-text">עדכון שלב</h3>
          {detail.allowed_recruitment_transitions.length === 0 ? (
            <p className="text-support text-cv-text-muted">אין מעבר ישיר זמין מהמצב הנוכחי.</p>
          ) : (
            <>
              <Field label="השלב הבא">
                {(control) => (
                  <Select
                    {...control}
                    onChange={(event) =>
                      setTransitionTarget(event.target.value as TransitionableRecruitmentStatus)
                    }
                    value={transitionTarget}
                  >
                    {detail.allowed_recruitment_transitions.map((status) => (
                      <option key={status} value={status}>
                        {recruitmentStatusLabel(status)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
              <Field label="סיבה (רשות)">
                {(control) => (
                  <TextInput
                    {...control}
                    onChange={(event) => setTransitionReason(event.target.value)}
                    value={transitionReason}
                  />
                )}
              </Field>
              <Button disabled={transition.isPending} type="submit">
                {transition.isPending ? "שומר…" : "שמירת השלב"}
              </Button>
            </>
          )}
        </form>

        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            nextActionMutation.mutate(false);
          }}
        >
          <h3 className="font-semibold text-cv-text">הפעולה הבאה</h3>
          <Field label="מה לעשות">
            {(control) => (
              <TextInput
                {...control}
                onChange={(event) => setNextActionValue(event.target.value)}
                value={nextAction}
              />
            )}
          </Field>
          <Field label="תאריך">
            {(control) => (
              <TextInput
                {...control}
                onChange={(event) => setNextActionDate(event.target.value)}
                type="date"
                value={nextActionDate}
              />
            )}
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button disabled={nextActionMutation.isPending} type="submit">
              שמירת הפעולה
            </Button>
            <Button
              disabled={
                nextActionMutation.isPending ||
                (detail.application.next_action == null && detail.application.next_action_date == null)
              }
              onClick={() => nextActionMutation.mutate(true)}
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
            onSubmit={(event) => {
              event.preventDefault();
              correction.mutate();
            }}
          >
            <Field label="האירוע השגוי">
              {(control) => (
                <Select
                  {...control}
                  onChange={(event) => setCorrectsEventId(event.target.value)}
                  value={correctsEventId}
                >
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
                <Select
                  {...control}
                  onChange={(event) => setCorrectionTarget(event.target.value as RecruitmentStatus)}
                  value={correctionTarget}
                >
                  {allStatuses.map((status) => (
                    <option key={status} value={status}>
                      {recruitmentStatusLabel(status)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field className="lg:col-span-2" label="למה נדרש תיקון">
              {(control) => (
                <TextArea
                  {...control}
                  onChange={(event) => setCorrectionReason(event.target.value)}
                  required
                  value={correctionReason}
                />
              )}
            </Field>
            <div className="flex flex-wrap justify-end gap-3 lg:col-span-2">
              <Button onClick={() => setCorrectionOpen(false)} variant="secondary">
                ביטול
              </Button>
              <Button
                disabled={correction.isPending || correctionReason.trim() === ""}
                type="submit"
              >
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
          onSubmit={(event) => {
            event.preventDefault();
            externalSubmission.mutate();
          }}
        >
          <Callout title="הרישום קבוע" tone="warning">
            ההגשה תתווסף להיסטוריה בלי להמציא גרסת קורות חיים או קובץ שלא נוצרו במערכת.
          </Callout>
          <Field label="מועד ההגשה">
            {(control) => (
              <TextInput
                {...control}
                onChange={(event) => setExternalSubmittedAt(event.target.value)}
                required
                type="datetime-local"
                value={externalSubmittedAt}
              />
            )}
          </Field>
          <Field label="הערה (רשות)">
            {(control) => (
              <TextArea
                {...control}
                onChange={(event) => setExternalNote(event.target.value)}
                value={externalNote}
              />
            )}
          </Field>
          <div className="flex flex-wrap justify-end gap-3">
            <Button onClick={() => setExternalOpen(false)} variant="secondary">
              ביטול
            </Button>
            <Button disabled={externalSubmission.isPending} type="submit">
              {externalSubmission.isPending ? "רושם…" : "רישום ההגשה החיצונית"}
            </Button>
          </div>
        </form>
      </Dialog>
    </section>
  );
};
