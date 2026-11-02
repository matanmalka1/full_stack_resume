import { useState } from "react";

import type { GapQuestion, GapQuestionSet } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Textarea } from "@/ui/Input";
import { StatusBadge } from "@/ui/StatusBadge";
import { useAnswerGapQuestion, useSkipGapQuestion } from "../../../api/gapQuestions";
import { coverageLabels, coverageTones } from "../../../model/analysisLabels";
import {
  GAP_ANSWER_MAX_LENGTH,
  type GapDraftFailure,
  gapQuestionView,
  importanceLabels,
} from "../../../model/gapQuestions";
import { GapFactPanel, type GapFactUseTarget } from "./GapFactPanel";

const DraftFailure = ({ failure }: { failure: GapDraftFailure }) => (
  <Callout role="alert" title="התשובה לא הפכה לעובדה" tone="warning">
    {failure.wording ? (
      <>
        <p>הניסוח שהוצע הוסיף פרטים שלא הופיעו בתשובה, ולכן לא נשמר דבר.</p>
        {failure.unsupported.length === 0 ? null : (
          <p className="mt-1">
            פרטים שלא הופיעו בתשובה:{" "}
            {failure.unsupported.map((term, index) => (
              <span key={term}>
                {index === 0 ? null : ", "}
                <bdi className="font-semibold">{term}</bdi>
              </span>
            ))}
          </p>
        )}
        <p className="mt-1">אפשר לענות שוב, במילים שלך ועם הפרטים שנכונים לגביך.</p>
      </>
    ) : (
      <p>ניסוח העובדה לא הושלם ולא נשמר דבר. אפשר לשלוח את התשובה שוב.</p>
    )}
  </Callout>
);

/* One question about one unmet requirement, and its outcome. The requirement it is about
   heads the card, so the reader answers the employer's ask, not the question's wording
   alone. An answer is final for the question once a fact is drafted from it, and so is a
   skip (§9.1); a draft the engine refused leaves the question open to answer again. */
export const GapQuestionCard = ({
  applicationId,
  language,
  question,
  useTarget,
}: {
  applicationId: string;
  language: GapQuestionSet["language"];
  question: GapQuestion;
  useTarget: GapFactUseTarget | null;
}) => {
  const view = gapQuestionView(question);
  const [answer, setAnswer] = useState("");
  const answering = useAnswerGapQuestion(applicationId, question.id, question.draft_operation?.id ?? null);
  const skipping = useSkipGapQuestion(applicationId, question.id);
  const headingId = `gap-question-${question.id}`;
  const trimmed = answer.trim();

  return (
    <article
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-surface border border-cv-border bg-cv-surface p-4 max-lg:p-3.5"
    >
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge tone={coverageTones[question.coverage]}>{coverageLabels[question.coverage]}</StatusBadge>
          <span className="text-support text-cv-text-muted">דרישה {importanceLabels[question.importance]}</span>
        </div>
        <p className="text-support leading-6 text-cv-text-muted">
          <span className="font-semibold text-cv-text">הדרישה: </span>
          <bdi>{question.requirement_text}</bdi>
        </p>
        <h4 className="text-body font-semibold leading-7 text-cv-text" dir="auto" id={headingId}>
          {question.question}
        </h4>
      </div>

      {view.kind === "open" ? (
        <form
          className="flex flex-col gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (trimmed !== "") answering.mutate(trimmed);
          }}
        >
          {view.failure === null ? null : <DraftFailure failure={view.failure} />}
          <Field hint="רק מה שקרה באמת, במילים שלך. העובדה תנוסח מהתשובה הזו בלבד." label="התשובה שלך">
            {(control) => (
              <Textarea
                {...control}
                dir="auto"
                maxLength={GAP_ANSWER_MAX_LENGTH}
                onChange={(event) => setAnswer(event.target.value)}
                rows={3}
                value={answer}
              />
            )}
          </Field>
          <div className="flex flex-wrap gap-2 max-lg:grid max-lg:grid-cols-2">
            <Button
              className="max-lg:min-h-11"
              disabled={trimmed === "" || skipping.isPending}
              pending={answering.isPending}
              pendingLabel="שולח…"
              type="submit"
            >
              שליחה
            </Button>
            <Button
              className="max-lg:min-h-11"
              disabled={answering.isPending}
              onClick={() => skipping.mutate()}
              pending={skipping.isPending}
              variant="secondary"
            >
              דילוג
            </Button>
          </div>
          {answering.error === null && skipping.error === null ? null : (
            <ErrorCallout
              error={answering.error ?? skipping.error}
              fallbackDetail="התשובה נשארה בטופס. אפשר לנסות שוב."
              title={answering.error === null ? "הדילוג לא נשמר" : "התשובה לא נשלחה"}
            />
          )}
        </form>
      ) : view.kind === "drafting" ? (
        <output className="text-support text-cv-text-muted">מנסחים עובדה מהתשובה שלך…</output>
      ) : view.kind === "skipped" ? (
        <p className="text-support text-cv-text-muted">דילגת על השאלה הזו.</p>
      ) : (
        <>
          <blockquote className="border-s-2 border-cv-border ps-3 text-support leading-6 text-cv-text-muted" dir="auto">
            {view.answer}
          </blockquote>
          {view.fact === null ? null : (
            <GapFactPanel applicationId={applicationId} fact={view.fact} language={language} useTarget={useTarget} />
          )}
        </>
      )}
    </article>
  );
};
