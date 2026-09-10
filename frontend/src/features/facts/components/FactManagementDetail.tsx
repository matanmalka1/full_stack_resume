import { useState } from "react";
import { PenLine } from "lucide-react";

import type { FactDetail } from "@/api/contracts";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { QueryState } from "@/ui/QueryState";
import { useFactAttachmentTargets } from "../api/queries";
import { replacementFactForm } from "../model/factForm";
import { FactAttachmentControl } from "./FactAttachmentControl";
import { FactCreationDialog } from "./FactCreationDialog";
import { FactEventHistory } from "./FactEventHistory";
import { FactOverview } from "./FactOverview";
import { FactPromotionControl } from "./FactPromotionControl";

interface FactManagementDetailProps {
  detail: FactDetail;
  mutationsBlocked?: boolean;
  onCreated: (factId: string) => void;
}

export const FactManagementDetail = ({ detail, mutationsBlocked = false, onCreated }: FactManagementDetailProps) => {
  const { fact } = detail;
  const targets = useFactAttachmentTargets(fact.fact_id);
  const [correcting, setCorrecting] = useState(false);
  const correctable = fact.status === "canonical" && !mutationsBlocked;

  return (
    <div className="flex flex-col gap-5" key={fact.fact_id}>
      <FactOverview fact={fact} />

      {mutationsBlocked ? null : <FactPromotionControl fact={fact} />}

      {fact.status === "canonical" && !mutationsBlocked ? (
        <QueryState
          error={targets.error}
          fallbackTitle="יעדי הצירוף לא נטענו"
          loading={targets.isPending}
          loadingLabel="טוען פרופילים וסעיפים…"
        >
          {targets.data === undefined ? null : <FactAttachmentControl fact={fact} targets={targets.data} />}
        </QueryState>
      ) : fact.status !== "canonical" && !mutationsBlocked ? (
        <Callout title="שיוך לפרופיל יתאפשר לאחר הקידום למקור אמת" tone="info" />
      ) : null}

      <div className="flex flex-col gap-3 border-t border-cv-border pt-4">
        {/* A canonical fact is never edited in place, so correcting one is not an edit
            form folded under the fact it would appear to change. It is its own write, and
            it reads as one: a stated action here, the consequence spelled out where the
            writing happens, and the original left on screen behind the dialog exactly as
            it was. The button carries the whole sentence rather than a bare "תיקון" -
            what is created is a new pending fact, not a change to this one. */}
        {correctable ? (
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-control bg-cv-surface-muted px-3.5 py-3">
            <p className="min-w-0 text-support leading-6 text-cv-text-muted">
              נוסח שגוי או לא מדויק? התיקון נוצר כעובדה ממתינה חדשה, והעובדה הקנונית הזו נשארת כפי שהיא.
            </p>
            <Button onClick={() => setCorrecting(true)} size="compact" variant="secondary">
              <PenLine aria-hidden="true" className="size-4 shrink-0" />
              יצירת תיקון לעובדה
            </Button>
          </div>
        ) : null}

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

        <Disclosure summary="היסטוריית העובדה">
          {detail.events.length === 0 ? (
            <Callout title="לא נמצאה היסטוריית lifecycle" tone="blocker">
              יש להפעיל בדיקת התאמה לפני שינוי נוסף.
            </Callout>
          ) : (
            <FactEventHistory events={detail.events} />
          )}
        </Disclosure>
      </div>
    </div>
  );
};
