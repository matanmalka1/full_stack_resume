import type { FactDetail } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { QueryState } from "@/ui/QueryState";
import { useFactAttachmentTargets } from "../api/queries";
import { replacementFactForm } from "../model/factForm";
import { FactAttachmentControl } from "./FactAttachmentControl";
import { CreatePendingFactForm } from "./CreatePendingFactForm";
import { FactEventHistory } from "./FactEventHistory";
import { FactProvenance, FactTags, FactWording } from "./FactIdentity";
import { FactPromotionControl } from "./FactPromotionControl";
import { FactStatusBadge } from "./FactStatusBadge";

interface FactManagementDetailProps {
  detail: FactDetail;
  mutationsBlocked?: boolean;
  onCreated: (factId: string) => void;
}

export const FactManagementDetail = ({ detail, mutationsBlocked = false, onCreated }: FactManagementDetailProps) => {
  const { fact } = detail;
  const targets = useFactAttachmentTargets(fact.fact_id);

  return (
    <div className="flex flex-col gap-4" key={fact.fact_id}>
      <div>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <FactWording className="min-w-0 flex-1" fact={fact} />
          <FactStatusBadge className="px-2.5 py-0.5" status={fact.status} />
        </div>
        <p className="mt-3 text-support text-cv-text-muted" dir="auto">
          {fact.meaning}
        </p>
        <FactProvenance className="mt-3" fact={fact} />
        <FactTags className="mt-3" tags={fact.tags} />
      </div>

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
  );
};
