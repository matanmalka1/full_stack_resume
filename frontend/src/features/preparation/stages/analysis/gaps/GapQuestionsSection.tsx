import { MessageCircleQuestion } from "lucide-react";

import type { ApplicationDetail, ProfileName } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { QueryState } from "@/ui/QueryState";
import { useAskGapQuestions, useGapQuestions, useRefreshOnSettled } from "../../../api/gapQuestions";
import {
  askingOperationId,
  gapQuestionsAskable,
  gapQuestionsOffered,
  openQuestionCount,
} from "../../../model/gapQuestions";
import type { GapFactUseTarget } from "./GapFactPanel";
import { GapQuestionCard } from "./GapQuestionCard";

/* §9.1 gap questions on the analysis step: one question per requirement the analysis
   found unmet, each answered in the reader's own words or skipped. An answer becomes a
   pending fact, never a canonical one, and the analysis does not read it until it runs
   again - so the step says both before the reader starts.

   Rendered only while the projection offers the action: the questions are about the
   newest analysis, and an analysis with nothing unmet has nothing to ask. */
export const GapQuestionsSection = ({
  detail,
  profile,
}: {
  detail: ApplicationDetail;
  profile: ProfileName | null;
}) => {
  const applicationId = detail.application.id;
  const offered = gapQuestionsOffered(detail);
  const query = useGapQuestions(applicationId, offered);
  const ask = useAskGapQuestions(applicationId, detail.latest_analysis_id ?? null);
  const askingId = askingOperationId(detail) ?? ask.data?.operation.id ?? null;
  const { live: asking } = useRefreshOnSettled(applicationId, askingId);

  if (!offered) return null;

  const set = query.data;
  const useTarget: GapFactUseTarget | null =
    set?.job_analysis_id != null &&
    profile !== null &&
    detail.document_id != null &&
    detail.document_analysis_id === set.job_analysis_id
      ? { analysisId: set.job_analysis_id, profile }
      : null;

  return (
    <section aria-labelledby="gap-questions-heading" className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <h3 className="text-body font-semibold text-cv-text" id="gap-questions-heading">
          השלמת פערים בעובדות
        </h3>
        <p className="text-support leading-6 text-cv-text-muted">
          שאלה אחת לכל דרישה שלא כוסתה. מכל תשובה תנוסח עובדה ממתינה מתוך מה שכתבת בלבד. היא תיחשב רק אחרי שתאושר,
          והכיסוי של הדרישות יתעדכן רק אחרי הרצת הניתוח מחדש.
        </p>
      </div>

      <QueryState
        error={query.error}
        errorTitle="לא ניתן לטעון את השאלות על הפערים"
        loading={set === undefined}
        loadingLabel="טוען את השאלות…"
        onRetry={() => void query.refetch()}
      >
        {set === undefined ? null : set.questions.length === 0 ? (
          <div className="flex flex-col items-start gap-2">
            <Button
              className="max-lg:min-h-11 max-lg:w-full"
              disabled={!gapQuestionsAskable(detail) || asking}
              onClick={() => ask.mutate()}
              pending={ask.isPending || asking}
              pendingLabel="מנסחים שאלות…"
              variant="secondary"
            >
              <MessageCircleQuestion aria-hidden="true" className="size-icon-md shrink-0" />
              שאלות על פערים
            </Button>
            {ask.error === null ? null : (
              <ErrorCallout
                error={ask.error}
                fallbackDetail="לא נוצרו שאלות. אפשר לנסות שוב."
                title="השאלות לא נוסחו"
              />
            )}
          </div>
        ) : (
          <>
            <p className="text-support text-cv-text-muted">
              {openQuestionCount(set) === 0
                ? "כל השאלות נענו או דולגו."
                : `${openQuestionCount(set)} מתוך ${set.questions.length} שאלות ממתינות לתשובה.`}
            </p>
            <ol className="flex flex-col gap-3">
              {set.questions.map((question) => (
                <li key={question.id}>
                  <GapQuestionCard
                    applicationId={applicationId}
                    language={set.language ?? null}
                    question={question}
                    useTarget={useTarget}
                  />
                </li>
              ))}
            </ol>
          </>
        )}
      </QueryState>
    </section>
  );
};
