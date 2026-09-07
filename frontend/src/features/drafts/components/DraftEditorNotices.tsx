import { Link } from "react-router-dom";

import { ErrorCallout } from "@/ui/ErrorCallout";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Callout } from "@/ui/Callout";

interface DraftEditorNoticesProps {
  aiUnavailable: boolean;
  /* Text the server has not accepted yet. Regeneration is frozen on the saved version, so
     the control says why it is shut instead of acting on a version the user has moved
     past. */
  dirty: boolean;
  regenerationError: unknown;
  selectionError: unknown;
}

/* What the editor's own commands have to say, in one place under the outline they act on.

   A refusal belongs next to the rows it refused, not in a banner at the top of a screen
   the reader has already scrolled past. Each notice is silent unless it applies, and none
   of them decides anything: the errors are the server's, and the two conditions are the
   editor's own state. */
export const DraftEditorNotices = ({
  aiUnavailable,
  dirty,
  regenerationError,
  selectionError,
}: DraftEditorNoticesProps) => (
  <>
    {aiUnavailable ? (
      <Callout title="יצירה מחדש באמצעות AI אינה זמינה" tone="neutral">
        יש להגדיר ספק ולהפעיל AI במסך ההגדרות. לא יתבצע מעבר דטרמיניסטי שקט.
        <div className="mt-3">
          <Link className={buttonClasses("secondary")} to={routePaths.settings}>
            מעבר להגדרות
          </Link>
        </div>
      </Callout>
    ) : null}

    {regenerationError === null || regenerationError === undefined ? null : (
      <ErrorCallout
        error={regenerationError}
        fallbackDetail="לא ניתן היה להפעיל יצירה מחדש. הטיוטה נשמרה כפי שהיא."
        fallbackTitle="היצירה מחדש לא הופעלה"
      />
    )}

    {dirty ? (
      <p className="text-support leading-6 text-cv-text-muted">
        יצירה מחדש מוקפאת על הגרסה השמורה של הטיוטה, ולכן היא זמינה רק אחרי שהשמירה הסתיימה.
      </p>
    ) : null}

    {selectionError === null || selectionError === undefined ? null : (
      <ErrorCallout
        error={selectionError}
        fallbackDetail="לא ניתן היה לשנות את בחירת העובדות. הטיוטה נשמרה כפי שהיא."
        fallbackTitle="שינוי הבחירה לא בוצע"
      />
    )}
  </>
);
