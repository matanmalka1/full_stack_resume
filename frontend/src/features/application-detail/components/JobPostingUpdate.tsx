import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";

import { invalidateApplicationViews, updateJobText } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { useAppForm } from "@/hooks/useAppForm";
import { useServerFieldErrors } from "@/hooks/useServerFieldErrors";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { Field } from "@/ui/Field";
import { Input, Textarea } from "@/ui/Input";
import { SuccessNotice } from "@/ui/SuccessNotice";
import {
  isJobTextWithinBudget,
  JOB_TEXT_REQUIRED_MESSAGE,
  normalizedSourceUrl,
  SOURCE_URL_MAX_CHARACTERS,
  validateSourceUrl,
} from "../model/applicationInput";

interface PostingFields {
  job_text: string;
  source_url: string;
}

const serverFields = { job_text: "job_text", source_url: "source_url" } as const satisfies Record<
  string,
  keyof PostingFields
>;

/* A posting that changed after the Application was opened, without opening a second one.

   The alternative was creating a new Application for the same job, which is the one thing
   the duplicate check exists to discourage - and it would have left the recruitment
   timeline, the analyses, the CV document, and the Submissions of the original behind.

   The edit replaces the text in place and names the text it replaces by hash, so an edit
   made against a text that already changed is refused rather than overwriting it. The
   engine's own projection decides the consequences: the analysis of the earlier text stops
   being current, and a document built on it is reported as built on an older analysis.
   Nothing here re-derives that - this screen only sends the posting.

   Once the Application has a Submission the text is locked: what was sent stays tied to
   the posting it was sent for. The control is then replaced by a note saying so.

   The current text is loaded into the field because the common case is a posting that was
   amended rather than rewritten. An unchanged text and URL are refused before the request
   is sent, as a field error rather than a round trip that would change nothing. */
export const JobPostingUpdate = ({
  detail,
  operationLive,
}: {
  detail: ApplicationDetail;
  /* The host screen's own watch, which also knows about work the projection has not
     reported yet - a run queued a moment ago - and about a success still being read. */
  operationLive: boolean;
}) => {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const posting = detail.job_posting;
  const originalJobText = posting.job_text;
  const originalSourceUrl = posting.source_url ?? null;
  const [open, setOpen] = useState(false);
  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    setError,
  } = useAppForm<PostingFields>({
    defaultValues: {
      job_text: originalJobText,
      source_url: posting.source_url ?? "",
    },
  });

  /* A courtesy, not the safety mechanism: an Operation freezes the job text it named, so
     an edit made mid-run makes that run fail its source check rather than silently
     swapping what it is working from. The disabled control keeps the reader from
     walking into that. */
  const workInFlight =
    operationLive || (detail.active_operation != null && !isTerminalOperation(detail.active_operation));

  const create = useMutation({
    mutationFn: (fields: PostingFields) =>
      updateJobText(applicationId, {
        /* The stored text is the posting's exact content, so it is never trimmed. */
        jobText: fields.job_text,
        sourceUrl: normalizedSourceUrl(fields.source_url),
        expectedJobTextHash: posting.job_text_hash,
      }),
    /* The projection is what reports the edited text, the analysis it superseded, and
       the action now recommended. Nothing from the response is seeded into the cache. */
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
    },
  });

  const inlineFields = useServerFieldErrors(create.error, setError, serverFields);

  const closeDialog = () => setOpen(false);

  if (posting.locked) {
    return (
      <p className="mt-3 text-support leading-6 text-cv-text-muted">
        נוסח המשרה נעול: המועמדות כבר הוגשה, והנוסח נשמר כפי שהיה בעת ההגשה.
      </p>
    );
  }

  return (
    <div className="mt-3">
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <h3 className="text-support font-semibold text-cv-text">המודעה השתנתה?</h3>
          <p className="mt-1 text-support leading-6 text-cv-text-muted">
            אפשר לערוך את הנוסח עד להגשת המועמדות. אחרי העריכה יש להריץ ניתוח מחדש.
          </p>
        </div>
        <Button
          aria-label="עדכון נוסח המשרה"
          aria-expanded={open}
          className="w-11 !px-0"
          onClick={() => {
            create.reset();
            setOpen(true);
          }}
          title="עדכון נוסח המשרה"
          variant="ghost"
        >
          <Pencil aria-hidden="true" className="size-icon-lg shrink-0" />
        </Button>
      </div>

      {create.isSuccess && !open ? (
        <SuccessNotice className="mt-4" onDismiss={() => create.reset()} title="נוסח המשרה עודכן">
          הניתוח הקודם נעשה על הנוסח הקודם ואינו פעיל יותר, ולכן יש להריץ ניתוח מחדש.
        </SuccessNotice>
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
              pendingLabel="שומר…"
              type="submit"
            >
              שמירת הנוסח
            </Button>
          </>
        }
        headingId="job-posting-update-heading"
        onClose={closeDialog}
        open={open}
        title="עריכת נוסח המשרה"
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
            הנוסח החדש מחליף את הנוסח הנוכחי. הניתוחים שנעשו על הנוסח הקודם נשמרים אך אינם פעילים עוד. מסמך קורות החיים
            לא משתנה ויסומן כמבוסס על ניתוח קודם, וניתוח מחדש נשאר פעולה נפרדת.
          </p>

          <Field error={errors.job_text?.message} label="טקסט המשרה">
            {(control) => (
              /* Mixed Hebrew/English posting text picks its own direction (A.3). */
              <Textarea
                {...control}
                {...register("job_text", {
                  validate: (value) => {
                    if (value.trim() === "") return JOB_TEXT_REQUIRED_MESSAGE;
                    if (!isJobTextWithinBudget(value)) {
                      return "טקסט המשרה חורג מהגודל המותר. יש לקצר אותו לפני השמירה.";
                    }
                    /* The save rule: text is sent verbatim and an empty URL becomes `null`.
                       Comparing in that same shape is what "unchanged" means - trimming the
                       text first would call a whitespace-only edit unchanged too. */
                    const unchanged =
                      value === originalJobText && normalizedSourceUrl(getValues("source_url")) === originalSourceUrl;
                    return !unchanged || "הנוסח והכתובת זהים לנוסח השמור. יש לערוך את אחד השדות לפני השמירה.";
                  },
                })}
                className="min-h-48 max-h-[55vh] [field-sizing:content]"
                dir="auto"
              />
            )}
          </Field>

          <Field
            error={errors.source_url?.message}
            hint="נשמרת כתיעוד מקור בלבד, המערכת אינה פותחת את הכתובת או מייבאת ממנה טקסט."
            label="כתובת המשרה"
            optional
          >
            {(control) => (
              /* A.3: a URL is an LTR island even inside the RTL shell. */
              <Input
                {...control}
                {...register("source_url", { validate: validateSourceUrl })}
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
              fallbackDetail="הנוסח לא עודכן, והטקסט נשאר בטופס. אפשר לנסות שוב."
              inlineFields={inlineFields}
              title="נוסח המשרה לא נשמר"
            />
          )}

          {/* Why the control is inert rather than missing, on the same reasoning the draft
              commands state it: the command is offered, later. */}
          {workInFlight ? (
            <p className="text-support leading-6 text-cv-text-muted">
              פעולה מתבצעת כעת על המועמדות. עריכת הנוסח תהיה זמינה שוב כשהיא תסתיים.
            </p>
          ) : null}
        </form>
      </Dialog>
    </div>
  );
};
