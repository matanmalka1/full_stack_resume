import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { PageShell } from "@/ui/PageShell";
import { boardPath } from "@/navigation/boardReturn";

/* A URL that matches no route. It offers the way back rather than only reporting the
   miss, because the reader who lands here typed or followed an address and has nothing
   else on the screen to act on.

   On a phone the miss is the whole screen: the code drawn large and muted, then the
   heading, the explanation and the way back, centred between the masthead and the
   bottom bar, the button across the width where a thumb finds it. A wide screen gets the
   wrapper as a plain block and the page exactly as before. */
export const NotFoundPage = () => (
  <div className="max-lg:flex max-lg:min-h-[70dvh] max-lg:items-center max-lg:text-center max-lg:[&>section]:w-full">
    <PageShell
      phoneMasthead="centered"
      description="ייתכן שהכתובת השתנתה או שהרשומה נסגרה. אפשר לחזור ללוח המועמדויות ולהמשיך משם."
      eyebrow={
        <span className="max-lg:mb-4 max-lg:block max-lg:text-[5.5rem] max-lg:leading-none max-lg:font-extrabold max-lg:text-cv-text-muted">
          404
        </span>
      }
      measure="form"
      title="העמוד לא נמצא"
    >
      <div>
        <Link
          className={buttonClasses(
            "primary",
            "max-lg:min-h-13 max-lg:w-full max-lg:rounded-surface max-lg:text-body max-lg:shadow-floating",
          )}
          to={boardPath()}
        >
          חזרה ללוח המועמדויות
        </Link>
      </div>
    </PageShell>
  </div>
);
