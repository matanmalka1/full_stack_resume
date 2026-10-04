import { Link } from "react-router-dom";

import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";

/* The document has no content yet (or no document exists before the first analysis). The
   screen says so once and points at the one place that creates it, rather than drawing an
   editor over nothing or leaving the reader on an empty page. */
export const DraftEmptyState = ({ applicationId }: { applicationId: string }) => (
  <Callout
    action={
      <Link className={buttonClasses("primary")} to={routePaths.application(applicationId)}>
        חזרה לניתוח והתאמה
      </Link>
    }
    title="לקורות החיים של המועמדות הזו אין עדיין טיוטה"
    tone="neutral"
  >
    מסך המועמדות מציג את המצב המדויק ואת הפעולה שיוצרת טיוטה.
  </Callout>
);
