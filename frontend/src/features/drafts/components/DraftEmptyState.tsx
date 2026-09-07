import { Link } from "react-router-dom";

import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";

/* No active WorkingDraft, and none being rendered from an approval either. The screen
   says so once and points at the one place that creates one, rather than reading a draft
   that does not exist or leaving the reader on an empty page. */
export const DraftEmptyState = ({ applicationId }: { applicationId: string }) => (
  <Callout
    action={
      <Link className={buttonClasses("primary")} to={routePaths.preparation(applicationId)}>
        חזרה להכנת קורות החיים
      </Link>
    }
    title="אין כרגע טיוטה פעילה למועמדות הזו"
    tone="neutral"
  >
    מסך המועמדות מציג את המצב המדויק ואת הפעולה שיוצרת טיוטה.
  </Callout>
);
