import type { FactDetail } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { QueryState } from "@/ui/QueryState";
import { useFactAttachmentTargets } from "../api/queries";
import { replacementFactForm } from "../model/factForm";
import { FactAttachmentControl } from "./FactAttachmentControl";
import { CreatePendingFactForm } from "./CreatePendingFactForm";
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
        <Callout title="שיוך לפרופיל יתאפשר לאחר הקידום למקור אמת" tone="neutral" />
      ) : null}

      <div className="flex flex-col gap-3 border-t border-cv-border pt-4">
        {fact.status === "canonical" && !mutationsBlocked ? (
          <Disclosure summary="יצירת תיקון לעובדה">
            <Callout title="העובדה המקורית לא תשתנה" tone="warning">
              התיקון ייווצר כעובדה ממתינה חדשה עם קשר החלפה לעובדה הזו.
            </Callout>
            <CreatePendingFactForm
              initialValues={replacementFactForm(fact)}
              onCreated={onCreated}
              profile={null}
              reason="canonical correction created from the candidate facts page"
              replaces={fact.fact_id}
              submitLabel="יצירת עובדת תיקון ממתינה"
            />
          </Disclosure>
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
