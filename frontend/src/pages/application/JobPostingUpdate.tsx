import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { applicationDetailQueryKey, createJobSnapshot } from "../../api/applications";
import type { ApplicationDetail } from "../../api/contracts";
import { isTerminalOperation } from "../../api/operations";
import { ErrorCallout } from "../../app/ErrorCallout";
import { useAppForm } from "../../forms/useAppForm";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";
import { Dialog } from "../../ui/Dialog";
import { Field } from "../../ui/Field";
import { TextArea, TextInput } from "../../ui/TextInput";
import { JobTextFileField } from "./JobTextFileField";

/* Native input affordance, not a second validation policy - the server stays the
   authority on the URL, exactly as it is on the intake screen. */
const SOURCE_URL_MAX_CHARACTERS = 2048;

interface PostingFields {
  job_text: string;
  source_url: string;
}

/* A posting that changed after the Application was opened, without opening a second one.

   The alternative was creating a new Application for the same job, which is the one thing
   the duplicate check exists to discourage - and it would have left the recruitment
   timeline, the analyses, and the approved revisions of the original behind.

   What it creates from Job Detail is a new immutable JobSnapshot, never an edit of the existing one. The
   snapshot on record is evidence of what the posting said when it was captured, and a
   posting that later vanishes from the web is exactly what that evidence is for. So the
   old snapshot stays, the new one becomes the active one, and the engine's own projection
   is what decides the consequences: the analysis of the older snapshot stops being the
   active analysis, and a draft built from it is reported stale. Nothing here re-derives
   that - this screen only sends the posting.

   The current text is loaded into the field because the common case is a posting that was
   amended rather than rewritten. Submitting it unchanged is refused by the server, which
   holds a snapshot per exact content; that refusal is shown as it arrives. */
export const JobPostingUpdate = ({ detail }: { detail: ApplicationDetail }) => {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const snapshot = detail.latest_snapshot;
  const [open, setOpen] = useState(false);
  const {
    formState: { errors },
    handleSubmit,
    register,
    setValue,
  } = useAppForm<PostingFields>({
    defaultValues: {
      job_text: typeof snapshot.job_text === "string" ? snapshot.job_text : "",
      source_url: snapshot.source_url ?? "",
    },
  });

  /* A courtesy, not the safety mechanism: an Operation freezes the sources it named, so
     a snapshot created mid-run is refused by the engine rather than silently swapping
     what that run is working from. The disabled control keeps the reader from walking
     into that refusal. */
  const workInFlight = detail.active_operation != null && !isTerminalOperation(detail.active_operation);

  const create = useMutation({
    mutationFn: (fields: PostingFields) => {
      const sourceUrl = fields.source_url.trim();

      return createJobSnapshot(applicationId, {
        /* The snapshot is the posting's exact content, so the text is never trimmed. */
        jobText: fields.job_text,
        sourceUrl: sourceUrl === "" ? null : sourceUrl,
      });
    },
    /* The projection is what reports the new snapshot, the analysis it superseded, and
       the action now recommended. Nothing from the response is seeded into the cache. */
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: applicationDetailQueryKey(applicationId) });
    },
  });

  const closeDialog = () => setOpen(false);

  return (
    <div className="border-t border-cv-border pt-4">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h3 className="text-support font-semibold text-cv-text">המודעה השתנתה?</h3>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            יצירת תצלום חדש מוסיפה את הנוסח המעודכן ושומרת את הגרסה הקודמת ללא שינוי.
          </p>
        </div>
        <Button
          aria-expanded={open}
          onClick={() => {
            create.reset();
            setOpen(true);
          }}
          variant="secondary"
        >
          עדכון נוסח המשרה
        </Button>
      </div>

      {create.isSuccess && !open ? (
        <Callout
          action={
            <Button onClick={() => create.reset()} variant="ghost">
              סגירת ההודעה
            </Button>
          }
          className="mt-4"
          role="status"
          title="נשמר תצלום משרה חדש"
          tone="success"
        >
          התצלום הקודם נשמר כפי שהוא. הניתוח שנעשה עליו אינו הניתוח הפעיל יותר, ולכן נדרש ניתוח מחדש מול הנוסח החדש.
        </Callout>
      ) : null}

      <Dialog
        footer={
          <>
            <Button onClick={closeDialog} variant="secondary">
              חזרה ללא שמירה
            </Button>
            <Button
              disabled={workInFlight}
              form="job-posting-update-form"
              pending={create.isPending}
              pendingLabel="שומר תצלום…"
              type="submit"
            >
              יצירת התצלום החדש
            </Button>
          </>
        }
        headingId="job-posting-update-heading"
        onClose={closeDialog}
        open={open}
        title="יצירת תצלום משרה חדש"
      >
        <form
          className="flex max-h-[75vh] flex-col gap-4 overflow-y-auto pe-1"
          id="job-posting-update-form"
          noValidate
          onSubmit={handleSubmit((fields) => {
            create.mutate(fields, { onSuccess: () => setOpen(false) });
          })}
        >
          {/* What the command costs, before it is sent. Re-analysis is not implied by the
              save and is not started by it: the analyze action on this screen stays the
              one place a run begins. */}
          <p className="text-support leading-6 text-cv-text-muted">
            הנוסח נשמר כתצלום חדש ובלתי משתנה. התצלום הקודם, הניתוחים שנעשו עליו והגרסאות שאושרו נשמרים כפי שהם. טיוטה
            פעילה תסומן כלא מעודכנת, וניתוח מחדש נשאר פעולה נפרדת.
          </p>

          <JobTextFileField
            onText={(text) => setValue("job_text", text, { shouldDirty: true, shouldValidate: true })}
          />

          <Field error={errors.job_text?.message} label="טקסט המשרה">
            {(control) => (
              /* Mixed Hebrew/English posting text picks its own direction (A.3). */
              <TextArea
                {...control}
                {...register("job_text", {
                  validate: (value) => value.trim() !== "" || "יש להזין את טקסט המשרה.",
                })}
                className="min-h-48 max-h-[55vh] [field-sizing:content]"
                dir="auto"
              />
            )}
          </Field>

          <Field
            hint="נשמרת כתיעוד מקור בלבד, המערכת אינה פותחת את הכתובת או מייבאת ממנה טקסט."
            label="כתובת המשרה — אופציונלי"
          >
            {(control) => (
              /* A.3: a URL is an LTR island even inside the RTL shell. */
              <TextInput
                {...control}
                {...register("source_url")}
                className="ltr-island max-w-xl"
                dir="ltr"
                inputMode="url"
                maxLength={SOURCE_URL_MAX_CHARACTERS}
              />
            )}
          </Field>

          {create.error === null ? null : (
            <ErrorCallout
              error={create.error}
              fallbackDetail="הפנייה לשרת נכשלה. שום תצלום לא נוצר, מה שהוזן נשמר בטופס ואפשר לנסות שוב."
              fallbackTitle="התצלום לא נשמר"
            />
          )}

          {/* Why the control is inert rather than missing, on the same reasoning the draft
              commands state it: the command is offered, later. */}
          {workInFlight ? (
            <p className="text-support leading-6 text-cv-text-muted">
              פעולה מתבצעת כעת על המועמדות. יצירת תצלום חדש תהיה זמינה שוב כשהיא תסתיים.
            </p>
          ) : null}
        </form>
      </Dialog>
    </div>
  );
};
