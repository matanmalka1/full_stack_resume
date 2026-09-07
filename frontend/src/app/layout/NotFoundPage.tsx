import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { PageShell } from "@/ui/PageShell";
import { routePaths } from "../routePaths";

/* A URL that matches no route. It offers the way back rather than only reporting the
   miss, because the reader who lands here typed or followed an address and has nothing
   else on the screen to act on. */
export const NotFoundPage = () => (
  <PageShell
    description="ייתכן שהכתובת השתנתה או שהרשומה נסגרה. אפשר לחזור ללוח המועמדויות ולהמשיך משם."
    eyebrow="404"
    measure="form"
    title="העמוד לא נמצא"
  >
    <div>
      <Link className={buttonClasses("primary")} to={routePaths.home}>
        חזרה ללוח המועמדויות
      </Link>
    </div>
  </PageShell>
);
