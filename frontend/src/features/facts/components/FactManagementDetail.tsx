import { useState, type ReactNode } from "react";
import { ChevronRight, Info } from "lucide-react";
import { Link } from "react-router-dom";

import type { FactDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { cx } from "@/ui/cx";
import { QueryState } from "@/ui/QueryState";
import { cardClasses } from "@/ui/surface";
import { useFactAttachmentTargets } from "../api/queries";
import { replacementFactForm } from "../model/factForm";
import { factContextLine, factLabel, factSourceLabel, factStyleLabel } from "../model/factLabels";
import { FactAttachmentControl } from "./FactAttachmentControl";
import { FactConfirmationControl } from "./FactConfirmationControl";
import { FactCreationDialog } from "./FactCreationDialog";
import { FactDeletionControl } from "./FactDeletionControl";
import { FactEventHistory } from "./FactEventHistory";
import { FactStatusBadge } from "./FactStatusBadge";

interface FactManagementDetailProps {
  detail: FactDetail;
  mutationsBlocked?: boolean;
  onCreated: (factId: string) => void;
  onDeleted: () => void;
  poolHref: string;
  selectedEventId?: string | null;
}

/* A phone's pinned command is the large size, sharing the bar's width. */
const pinnedCommand = "max-lg:min-h-11 max-lg:flex-1 max-lg:rounded-pill";

/* A block of the fact's own text: a small heading and the wording at reading size. */
const WordingCard = ({
  children,
  className,
  dir,
  id,
  label,
}: {
  children: ReactNode;
  className?: string;
  dir: "ltr" | "auto";
  id: string;
  label: string;
}) => (
  <section aria-labelledby={id} className={cardClasses(cx("flex flex-col gap-2 p-3.5 lg:p-4.5", className))}>
    <h2 className="text-support font-bold text-cv-text-muted" id={id}>
      {label}
    </h2>
    <p className={cx("text-body leading-relaxed text-cv-text lg:text-base", dir === "ltr" && "text-left")} dir={dir}>
      {children}
    </p>
  </section>
);

/* One record's page, as the design draws it: the way back and the ⋮ menu on top, the
   status and kind as two pills over the wording's heading, then the wording itself in
   cards. A wide screen sets the record-keeping - what the fact means, where it was filed,
   its tags and its history - in a column beside it; a phone runs everything in one
   column and pins the fact's one command above the tab bar. */
export const FactManagementDetail = ({
  detail,
  mutationsBlocked = false,
  onCreated,
  onDeleted,
  poolHref,
  selectedEventId,
}: FactManagementDetailProps) => {
  const { fact } = detail;
  const targets = useFactAttachmentTargets(fact.fact_id);
  const [correcting, setCorrecting] = useState(false);
  const correctable = fact.status === "canonical" && !mutationsBlocked;
  const promotable = fact.status === "pending" && !mutationsBlocked;
  const context = factContextLine(fact);
  const hebrew = fact.renderings.he;
  const english = fact.renderings.en;

  return (
    <section
      aria-labelledby="route-heading"
      className={cx("page-frame w-full [--page-measure:65rem]", (correctable || promotable) && "max-lg:pb-24")}
      key={fact.fact_id}
    >
      <div className="-mt-2 flex items-center justify-between gap-3 max-lg:-mx-2 lg:mt-0">
        <Link
          aria-label="חזרה למאגר העובדות"
          className="inline-flex size-11 items-center justify-center rounded-control text-cv-text hover:bg-cv-surface-muted lg:hidden"
          to={poolHref}
        >
          <ChevronRight aria-hidden="true" className="size-icon-lg" />
        </Link>
        <nav aria-label="מיקום" className="flex gap-1.5 text-support text-cv-text-muted max-lg:hidden">
          <Link className="underline underline-offset-2 hover:text-cv-text" to={poolHref}>
            מאגר העובדות
          </Link>
          <span aria-hidden="true">/</span>
          <span aria-current="page">פרטי עובדה</span>
        </nav>
        {mutationsBlocked ? null : <FactDeletionControl fact={fact} onDeleted={onDeleted} />}
      </div>

      <div className="mt-1 flex flex-col gap-4 lg:mt-4 lg:flex-row lg:items-start lg:gap-7">
        <div className="flex min-w-0 flex-1 flex-col gap-4">
          <div className="flex flex-col gap-2.5 lg:gap-4">
            <span className="flex flex-wrap gap-1.5">
              <FactStatusBadge status={fact.status} />
              <span className="rounded-pill bg-cv-surface-muted px-2.5 py-1 text-caption font-bold text-cv-text">
                {factStyleLabel(fact.resume_style)}
              </span>
            </span>
            {/* The route's heading, marked as `PageHeading` marks one, so the shell focuses
                it after a navigation. */}
            <h1
              className="text-heading-md leading-snug font-extrabold tracking-tight text-cv-text lg:text-display"
              data-route-heading
              dir="auto"
              id="route-heading"
              tabIndex={-1}
            >
              {factLabel(fact)}
            </h1>
            {context === "" ? null : (
              <p className="text-label text-cv-text-muted lg:text-body" dir="auto">
                {context}
              </p>
            )}
          </div>

          {/* The Hebrew wording is the heading itself, so a phone - one card of wording in
              the design - does not repeat it under the heading. */}
          {hebrew === undefined ? null : (
            <WordingCard className="max-lg:hidden" dir="auto" id="fact-hebrew-heading" label="ניסוח בעברית">
              {hebrew}
            </WordingCard>
          )}
          {english === undefined ? null : (
            <WordingCard dir="ltr" id="fact-english-heading" label="ניסוח באנגלית">
              {english}
            </WordingCard>
          )}

          {/* The fact's one command. A phone pins it above the tab bar, where a thumb finds
              it; a wide screen keeps it under the wording it acts on. */}
          {correctable || promotable ? (
            <div
              className={cx(
                "flex gap-2.5",
                "max-lg:fixed max-lg:inset-x-0 max-lg:bottom-(--cv-bottom-nav-height) max-lg:z-(--cv-z-sticky) max-lg:border-t max-lg:border-cv-hairline max-lg:bg-cv-surface/95 max-lg:px-4 max-lg:py-3",
              )}
            >
              {promotable ? (
                <FactConfirmationControl className={cx(pinnedCommand, "lg:shadow-action")} fact={fact} />
              ) : null}
              {/* A canonical fact is never edited in place: correcting one creates a new
                  pending fact that replaces it, and the original stays as it is. */}
              {correctable ? (
                <Button
                  className={pinnedCommand}
                  onClick={() => setCorrecting(true)}
                  size="default"
                  variant="secondary"
                >
                  יצירת תיקון לעובדה
                </Button>
              ) : null}
            </div>
          ) : null}

          {fact.status === "canonical" && !mutationsBlocked ? (
            <QueryState
              error={targets.error}
              errorTitle="לא ניתן לטעון את יעדי הצירוף"
              loading={targets.isPending}
              loadingLabel="טוען פרופילים וסעיפים…"
            >
              {targets.data === undefined ? null : <FactAttachmentControl fact={fact} targets={targets.data} />}
            </QueryState>
          ) : null}
        </div>

        <aside aria-label="פרטי העובדה" className="flex flex-col gap-3.5 lg:w-70 lg:shrink-0">
          {promotable ? (
            <p className="flex items-start gap-2.5 rounded-control-lg bg-cv-surface-muted px-3.5 py-3 text-support leading-normal text-cv-text lg:px-4 lg:py-3.5 lg:text-label">
              <Info aria-hidden="true" className="mt-0.5 size-icon-md shrink-0" />
              שיוך לפרופיל יתאפשר לאחר הקידום למקור אמת
            </p>
          ) : null}

          <dl className={cardClasses("divide-y divide-cv-canvas overflow-hidden")}>
            <div className="px-4 py-3">
              <dt className="text-caption text-cv-text-muted">מקור הידע</dt>
              <dd className="mt-0.5 text-label font-bold text-cv-text">{factSourceLabel(fact.source)}</dd>
            </div>
            <div className="px-4 py-3">
              <dt className="text-caption text-cv-text-muted">משמעות</dt>
              <dd className="mt-0.5 text-label text-cv-text" dir="auto">
                {fact.meaning}
              </dd>
            </div>
            {fact.tags.length === 0 ? null : (
              <div className="px-4 py-3">
                <dt className="text-caption text-cv-text-muted">תגיות</dt>
                <dd className="mt-1.5 flex flex-wrap gap-1.5">
                  {fact.tags.map((tag) => (
                    <span
                      className="rounded-pill bg-cv-canvas px-2.25 py-0.75 text-caption text-cv-text"
                      dir="auto"
                      key={tag}
                    >
                      {tag}
                    </span>
                  ))}
                </dd>
              </div>
            )}
          </dl>

          <section
            aria-labelledby="fact-history-heading"
            className="flex flex-col gap-2 lg:gap-3 lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:p-4 lg:shadow-surface"
          >
            <h2 className="px-1 text-support font-bold text-cv-text-muted lg:px-0" id="fact-history-heading">
              היסטוריית העובדה
            </h2>
            <div className={cardClasses("p-3.5 lg:contents")}>
              {detail.events.length === 0 ? (
                <Callout title="לא נמצאה היסטוריית lifecycle" tone="blocker">
                  יש להפעיל בדיקת התאמה לפני שינוי נוסף.
                </Callout>
              ) : (
                <FactEventHistory events={detail.events} selectedEventId={selectedEventId} />
              )}
            </div>
          </section>
        </aside>
      </div>

      {correctable ? (
        <FactCreationDialog
          formId="fact-correction-form"
          headingId="fact-correction-heading"
          initialValues={replacementFactForm(fact)}
          intro={
            <Callout title="העובדה המקורית לא תשתנה" tone="warning">
              התיקון ייווצר כעובדה ממתינה חדשה עם קשר החלפה לעובדה הזו. השדות נטענו מהעובדה הקיימת - יש לשנות רק את מה
              שצריך לתקן.
            </Callout>
          }
          onClose={() => setCorrecting(false)}
          onCreated={onCreated}
          open={correcting}
          reason="canonical correction created from the candidate facts page"
          replaces={fact.fact_id}
          submitLabel="יצירת עובדת תיקון ממתינה"
          title="יצירת תיקון לעובדה"
        />
      ) : null}
    </section>
  );
};
