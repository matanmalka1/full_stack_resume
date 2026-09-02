import { Link } from "react-router-dom";

import type { ApplicationDetail } from "../../api/contracts";
import { useSettings } from "../../api/useSettings";
import { appRoutes } from "../../app/appRoutes";
import { Callout } from "../../ui/Callout";
import { autoDraftIsAnticipated } from "./autoDraft";

/* Said before it happens rather than explained afterwards. With the automation opt-in on,
   a successful analysis is followed by a generate this screen sends on its own: a second
   Operation appears with no press behind it, and the setting that caused it is on another
   screen. The notice states it while the analysis is still running, and names the screen
   the decision lives on so it can be changed rather than merely understood. */
export const AutomaticDraftNotice = ({ detail }: { detail: ApplicationDetail }) => {
  const { settings } = useSettings();

  if (!autoDraftIsAnticipated(settings, detail)) {
    return null;
  }

  return (
    <Callout title="טיוטה תיווצר אוטומטית בסיום הניתוח" tone="neutral">
      אם הניתוח לא יעלה נושא שדורש החלטה, יצירת הטיוטה תתחיל מיד עם סיומו בלי לחיצה נוספת. ההגדרה נמצאת ב
      <Link className="text-cv-accent hover:underline" to={appRoutes.settings}>
        הגדרות
      </Link>
      .
    </Callout>
  );
};
