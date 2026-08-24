import { Link } from "react-router-dom";

import type { DuplicateMatch, DuplicateMatchReason } from "../api/contracts";
import { Button, buttonClasses } from "../ui/Button";
import { Callout } from "../ui/Callout";

/* Keyed by the generated union, so a detection reason added to the backend fails the
   frontend build instead of reaching the screen as an untranslated code. */
const matchReasonLabels: Record<DuplicateMatchReason, string> = {
  source_url: "אותה כתובת מקור",
  normalized_text: "טקסט משרה זהה",
  company_title: "אותה חברה ואותו תפקיד",
};

interface DuplicateChoicesProps {
  matches: DuplicateMatch[];
  onCreateAnyway: () => void;
  pending: boolean;
}

/* A.4 frame 1, region 9. Duplicate results are warnings: each one offers the existing
   Application, and creating another is a separate explicit action rather than something
   the primary button does quietly. */
export const DuplicateChoices = ({ matches, onCreateAnyway, pending }: DuplicateChoicesProps) => {
  return (
    <Callout
      action={
        <Button disabled={pending} onClick={onCreateAnyway} variant="secondary">
          יצירה בכל זאת
        </Button>
      }
      role="alert"
      title="נמצאו מועמדויות דומות"
      tone="warning"
    >
      <p>
        זו אזהרה בלבד ואינה חוסמת. אפשר לפתוח מועמדות קיימת, או ליצור מועמדות נוספת עם
        הטקסט שהוזן באמצעות הכפתור שבהמשך.
      </p>

      {matches.length === 0 ? (
        <p className="mt-3">השרת ביקש אישור מפורש אך לא החזיר פירוט של המועמדויות הדומות.</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-3">
          {matches.map((match) => (
            <li
              className="flex flex-wrap items-center justify-between gap-3 rounded-control border border-cv-border bg-cv-surface p-3"
              key={match.application_id}
            >
              <div className="min-w-0">
                <p className="font-medium text-cv-text" dir="auto">
                  {match.company}
                </p>
                <p className="text-cv-text-muted" dir="auto">
                  {match.target_role}
                </p>
                <p className="text-cv-text-muted">
                  {match.matched_on.map((reason) => matchReasonLabels[reason]).join(" · ")}
                </p>
              </div>
              <Link
                className={buttonClasses("secondary")}
                to={`/applications/${encodeURIComponent(match.application_id)}`}
              >
                פתיחת המועמדות הקיימת
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Callout>
  );
};
