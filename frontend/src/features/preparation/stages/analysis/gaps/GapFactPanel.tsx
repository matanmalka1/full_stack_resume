import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import type { Fact, GapQuestionSet, ProfileName } from "@/api/contracts";
import { factAttachmentTargetsQueryOptions } from "@/api/facts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Checkbox } from "@/ui/Checkbox";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Select } from "@/ui/Select";
import { StatusBadge } from "@/ui/StatusBadge";
import { useConfirmAndUseGapFact, useConfirmGapFact } from "../../../api/gapQuestions";
import { gapFactRendering } from "../../../model/gapQuestions";
import { GapFactEditDialog } from "./GapFactEditDialog";

/* Where a confirmed fact can be put to use at once: the document built on the analysis
   these questions are about, under its Profile. Absent, only confirmation is offered. */
export interface GapFactUseTarget {
  analysisId: string;
  profile: ProfileName;
}

const statusWords: Record<Fact["status"], string> = {
  pending: "ממתינה לאישור",
  canonical: "אושרה",
  deleted: "נמחקה",
};

/* The fact drafted from one answer: its wording, and the reader's three ways on from it -
   correct it, confirm it, or confirm it and use it in the document. Nothing here is
   counted until it is confirmed, and coverage moves only when the analysis runs again;
   the copy says both, the way the manual "add a fact" path says it. */
export const GapFactPanel = ({
  applicationId,
  fact,
  language,
  useTarget,
}: {
  applicationId: string;
  fact: Fact;
  language: GapQuestionSet["language"];
  useTarget: GapFactUseTarget | null;
}) => {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [attested, setAttested] = useState(false);
  const confirm = useConfirmGapFact(applicationId, fact.fact_id);
  const confirmAndUse = useConfirmAndUseGapFact(applicationId, fact.fact_id);
  const pending = fact.status === "pending";

  return (
    <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface-muted p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-support font-semibold text-cv-text">העובדה שנוסחה מהתשובה</p>
        <StatusBadge tone={fact.status === "canonical" ? "success" : "neutral"}>{statusWords[fact.status]}</StatusBadge>
      </div>
      <p className="text-body leading-7 text-cv-text" dir="auto">
        {gapFactRendering(fact, language)}
      </p>

      {pending ? (
        <>
          <p className="text-support leading-6 text-cv-text-muted">
            העובדה נשמרה כממתינה. כדי שתיחשב לדרישה יש לאשר אותה ולהריץ את הניתוח מחדש.
          </p>
          <div>
            <Button className="max-lg:min-h-11" onClick={() => setEditing(true)} variant="secondary">
              עריכה
            </Button>
          </div>
          <Checkbox checked={attested} onChange={(event) => setAttested(event.currentTarget.checked)}>
            בדקתי את ניסוח העובדה והוא נכון ומבוסס על התשובה שלי
          </Checkbox>
          <div className="flex flex-wrap gap-2 max-lg:flex-col">
            <Button
              className="max-lg:min-h-11"
              disabled={!attested || confirmAndUse.isPending}
              onClick={() => confirm.mutate()}
              pending={confirm.isPending}
              variant={useTarget === null ? "primary" : "secondary"}
            >
              אישור העובדה
            </Button>
          </div>
          {useTarget === null ? null : (
            <ConfirmAndUse
              attested={attested}
              blocked={confirm.isPending}
              factId={fact.fact_id}
              onUse={(section) =>
                confirmAndUse.mutate({ job_analysis_id: useTarget.analysisId, profile: useTarget.profile, section })
              }
              pending={confirmAndUse.isPending}
              profile={useTarget.profile}
            />
          )}
          {confirm.error === null && confirmAndUse.error === null ? null : (
            <ErrorCallout
              error={confirm.error ?? confirmAndUse.error}
              fallbackDetail="העובדה לא השתנתה. אפשר לנסות שוב."
              title="העובדה לא אושרה"
            />
          )}
          {editing ? (
            <GapFactEditDialog
              applicationId={applicationId}
              fact={fact}
              headingId={`${id}-edit`}
              onClose={() => setEditing(false)}
              open={editing}
            />
          ) : null}
        </>
      ) : fact.status === "canonical" ? (
        // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
        <Callout role="status" title="העובדה אושרה" tone="success">
          {confirmAndUse.isSuccess
            ? "העובדה צורפה לפרופיל, והטיוטה הבאה תוכל להשתמש בה. כדי שהכיסוי של הדרישה יתעדכן יש להריץ את הניתוח מחדש."
            : "כדי שהכיסוי של הדרישה יתעדכן יש להריץ את הניתוח מחדש."}
        </Callout>
      ) : null}
    </div>
  );
};

/* Confirm and attach in one command, into a section of the document's Profile. The
   sections come from the attachment targets the fact store reports for this fact. */
const ConfirmAndUse = ({
  attested,
  blocked,
  factId,
  onUse,
  pending,
  profile,
}: {
  attested: boolean;
  blocked: boolean;
  factId: string;
  onUse: (section: string) => void;
  pending: boolean;
  profile: ProfileName;
}) => {
  const targets = useQuery(factAttachmentTargetsQueryOptions(factId));
  const sections = targets.data?.profiles.find((target) => target.profile === profile)?.sections ?? [];
  const [chosen, setChosen] = useState<string | null>(null);
  const section = chosen ?? sections[0]?.section ?? null;

  if (sections.length === 0 || section === null) return null;

  return (
    <div className="cv-fields-compact flex flex-col gap-2 border-t border-cv-border pt-3">
      <Field label="סעיף בקורות החיים">
        {(control) => (
          <Select {...control} onChange={(event) => setChosen(event.target.value)} value={section}>
            {sections.map((item) => (
              <option key={item.section} value={item.section}>
                {item.label}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <div>
        <Button
          className="max-lg:min-h-11 max-lg:w-full"
          disabled={!attested || blocked}
          onClick={() => onUse(section)}
          pending={pending}
        >
          אישור ושימוש בטיוטה
        </Button>
      </div>
    </div>
  );
};
