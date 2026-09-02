import { Building2, ChevronLeft, FileText, Link2, type LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";

import type { DuplicateMatch, DuplicateMatchReason } from "../../api/contracts";
import { appRoutes } from "../../app/appRoutes";
import { Button } from "../../ui/Button";
import { Callout } from "../../ui/Callout";

interface ReasonPresentation {
  icon: LucideIcon;
  label: string;
  /* How much the reason narrows the question. The same URL is all but the same posting;
     a shared company and title is the weakest of the three, since one employer can post
     the same role twice. Ordering the list by it puts the match most likely to be the
     one the user already has at the top, instead of leaving three equal-looking rows. */
  strength: number;
}

/* Keyed by the generated union, so a detection reason added to the backend fails the
   frontend build instead of reaching the screen as an untranslated code. */
const matchReasons: Record<DuplicateMatchReason, ReasonPresentation> = {
  source_url: { icon: Link2, label: "אותה כתובת מקור", strength: 3 },
  normalized_text: { icon: FileText, label: "טקסט משרה זהה", strength: 2 },
  company_title: { icon: Building2, label: "אותה חברה ואותו תפקיד", strength: 1 },
};

const strongestReason = (match: DuplicateMatch): DuplicateMatchReason | undefined =>
  [...match.matched_on].sort((left, right) => matchReasons[right].strength - matchReasons[left].strength)[0];

const matchStrength = (match: DuplicateMatch): number => {
  const reason = strongestReason(match);

  return reason === undefined ? 0 : matchReasons[reason].strength;
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
  /* Sorted for reading, not scored: every match the server returned is still shown, in
     the order that puts the most specific evidence first. */
  const ranked = [...matches].sort((left, right) => matchStrength(right) - matchStrength(left));

  return (
    <Callout
      action={
        <div className="flex flex-wrap items-center gap-3">
          <Button onClick={onCreateAnyway} pending={pending} pendingLabel="יוצר מועמדות…" variant="secondary">
            יצירת מועמדות נוספת
          </Button>
          <span className="text-cv-text-muted">הטקסט שהוזן יישמר כמועמדות חדשה לצד הקיימות.</span>
        </div>
      }
      role="alert"
      title={matches.length === 1 ? "נמצאה מועמדות דומה" : `נמצאו ${matches.length} מועמדויות דומות`}
      tone="warning"
    >
      <p>זו אזהרה בלבד ואינה חוסמת. אפשר לפתוח מועמדות קיימת, או להמשיך ולפתוח מועמדות נוספת.</p>

      {ranked.length === 0 ? (
        <p className="mt-3">השרת ביקש אישור מפורש אך לא החזיר פירוט של המועמדויות הדומות.</p>
      ) : (
        <ul className="mt-3 divide-y divide-cv-warning/20 border-y border-cv-warning/20">
          {ranked.map((match) => {
            const reason = strongestReason(match);
            const ReasonIcon = reason === undefined ? undefined : matchReasons[reason].icon;
            /* The whole row is the link, so the label carries what a repeated button
               caption used to: which record opening this row leads to. */
            const openLabel = `פתיחת המועמדות הקיימת: ${match.company} — ${match.target_role}`;

            return (
              <li key={match.application_id}>
                {/* Rows sit directly on the callout, separated by rules rather than each
                    being its own bordered surface. A card inside a card reads as two
                    nested containers when the list is one thing. */}
                <Link
                  aria-label={openLabel}
                  className="group flex items-center gap-3 py-3 transition-colors duration-200 hover:text-cv-accent"
                  to={appRoutes.application(match.application_id)}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium text-cv-text group-hover:text-cv-accent" dir="auto">
                      {match.company}
                    </span>
                    <span className="block truncate text-cv-text-muted" dir="auto">
                      {match.target_role}
                    </span>
                    <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-cv-warning">
                      {ReasonIcon === undefined ? null : <ReasonIcon aria-hidden="true" className="size-4 shrink-0" />}
                      {match.matched_on.map((matchedReason) => matchReasons[matchedReason].label).join(" · ")}
                    </span>
                  </span>
                  <ChevronLeft
                    aria-hidden="true"
                    className="size-5 shrink-0 text-cv-text-muted transition-transform duration-200 group-hover:-translate-x-0.5 group-hover:text-cv-accent"
                  />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Callout>
  );
};
