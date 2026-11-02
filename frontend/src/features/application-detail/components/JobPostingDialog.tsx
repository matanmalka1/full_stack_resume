import { useMutation, useQueryClient } from "@tanstack/react-query";

import { invalidateApplicationViews, updateJobText } from "@/api/applications";
import type { ApplicationDetail } from "@/api/contracts";
import { isTerminalOperation } from "@/api/operations";
import { useAppForm } from "@/hooks/useAppForm";
import { useServerFieldErrors } from "@/hooks/useServerFieldErrors";
import { Button } from "@/ui/Button";
import { Dialog } from "@/ui/Dialog";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Input, Textarea } from "@/ui/Input";
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

/* Whether the record's menu offers the edit at all: once the Application has a
   Submission the text is locked - what was sent stays tied to the posting it was sent
   for (`lock_submitted_job_text`) - and a deleted record takes no commands. */
export const jobPostingEditable = (detail: ApplicationDetail): boolean =>
  !detail.job_posting.locked && detail.application.deleted_at == null;

/* A posting that changed after the Application was opened, edited in place rather than
   by opening a second Application for the same job - which the duplicate check exists to
   discourage, and which would leave the timeline, analyses, document and Submissions of
   the first behind.

   The edit names the text it replaces by hash, so one made against a text that already
   changed is refused rather than overwriting it. The engine's projection decides the
   consequences - the analysis of the earlier text stops being current, a document built
   on it is reported as built on an older analysis - and this dialog only sends the text.

   Opened from the record's menu; a sheet on a phone, a centred card on a wide screen. The
   current text is loaded into the field, since a posting is usually amended rather than
   rewritten, and an unchanged text and URL are refused as a field error before any
   request. */
export const JobPostingDialog = ({
  detail,
  onClose,
  onSaved,
}: {
  detail: ApplicationDetail;
  onClose: () => void;
  onSaved: () => void;
}) => {
  const queryClient = useQueryClient();
  const applicationId = detail.application.id;
  const posting = detail.job_posting;
  const originalJobText = posting.job_text;
  const originalSourceUrl = posting.source_url ?? null;
  const {
    formState: { errors },
    getValues,
    handleSubmit,
    register,
    setError,
  } = useAppForm<PostingFields>({
    defaultValues: { job_text: originalJobText, source_url: posting.source_url ?? "" },
  });

  /* A courtesy, not the safety mechanism: an Operation freezes the job text it named, so
     an edit made mid-run fails that run's source check rather than swapping what it reads.
     The inert command keeps the reader from walking into that. */
  const workInFlight = detail.active_operation != null && !isTerminalOperation(detail.active_operation);

  const save = useMutation({
    mutationFn: (fields: PostingFields) =>
      updateJobText(applicationId, {
        /* The stored text is the posting's exact content, so it is never trimmed. */
        jobText: fields.job_text,
        sourceUrl: normalizedSourceUrl(fields.source_url),
        expectedJobTextHash: posting.job_text_hash,
      }),
    /* The projection reports the edited text, the analysis it superseded and the action
       now recommended; nothing from the response is seeded into the cache. */
    onSuccess: async () => {
      await invalidateApplicationViews(queryClient, applicationId);
      onSaved();
    },
  });
  const inlineFields = useServerFieldErrors(save.error, setError, serverFields);

  return (
    <Dialog
      description="עד להגשת המועמדות אפשר לעדכן את הנוסח שהמשרה נשמרה בו."
      dismissible={!save.isPending}
      footer={
        <>
          {/* A phone's sheet closes by its own mark and leaves the row to the command. */}
          <Button
            className="max-lg:hidden"
            disabled={save.isPending}
            onClick={onClose}
            size="default"
            variant="secondary"
          >
            ביטול
          </Button>
          <Button
            disabled={workInFlight}
            form="job-posting-form"
            pending={save.isPending}
            pendingLabel="שומר…"
            size="default"
            type="submit"
          >
            שמירת הנוסח
          </Button>
        </>
      }
      headingId="job-posting-heading"
      onClose={onClose}
      open
      size="wide"
      title="עריכת נוסח המשרה"
    >
      <form
        className="flex flex-col gap-4"
        id="job-posting-form"
        noValidate
        onSubmit={handleSubmit((fields) => save.mutate(fields))}
      >
        {/* What the command costs, before it is sent. Re-analysis is not started by the
            save: the analysis step stays the one place a run begins. */}
        <p className="text-label leading-relaxed text-cv-text-muted">
          הנוסח החדש מחליף את הנוסח הנוכחי. הניתוחים שנעשו על הנוסח הקודם נשמרים אך אינם פעילים עוד, ומסמך קורות החיים
          יסומן כמבוסס על ניתוח קודם עד שתריצו ניתוח מחדש.
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
              className="max-h-[50dvh] min-h-48 [field-sizing:content]"
              dir="auto"
            />
          )}
        </Field>

        <Field
          error={errors.source_url?.message}
          hint="נשמרת כתיעוד מקור בלבד. המערכת אינה פותחת את הכתובת ואינה מייבאת ממנה טקסט."
          label="כתובת המשרה"
          optional
        >
          {(control) => (
            /* A.3: a URL is an LTR island even inside the RTL shell. */
            <Input
              {...control}
              {...register("source_url", { validate: validateSourceUrl })}
              className="ltr-island"
              dir="ltr"
              inputMode="url"
              maxLength={SOURCE_URL_MAX_CHARACTERS}
            />
          )}
        </Field>

        {save.error === null ? null : (
          <ErrorCallout
            error={save.error}
            fallbackDetail="הנוסח לא עודכן, והטקסט נשאר בטופס. אפשר לנסות שוב."
            inlineFields={inlineFields}
            title="נוסח המשרה לא נשמר"
          />
        )}

        {/* Why the command is inert rather than missing: it is offered, later. */}
        {workInFlight ? (
          <p className="text-support leading-relaxed text-cv-text-muted">
            פעולה מתבצעת כעת על המועמדות. אפשר יהיה לשמור את הנוסח כשהיא תסתיים.
          </p>
        ) : null}
      </form>
    </Dialog>
  );
};
