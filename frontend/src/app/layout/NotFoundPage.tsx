import { Link } from "react-router-dom";

import { buttonClasses } from "@/ui/Button";
import { routePaths } from "@/navigation/routePaths";

/* A URL that matches no route, or a record the server no longer has. It offers the way
   back rather than only reporting the miss, because the reader who lands here typed or
   followed an address and has nothing else on the screen to act on.

   The miss is the whole content area at every width: the code drawn large and pale, then
   the heading, the explanation and the way back, centred. On a phone the button runs
   across the width where a thumb finds it. The heading is the route heading the shell
   moves focus to. */
export const NotFoundPage = () => (
  <section
    aria-labelledby="route-heading"
    className="page-frame flex min-h-[70dvh] flex-col lg:min-h-[calc(100dvh-5rem)] items-center justify-center gap-4.5 text-center"
  >
    {/* Drawn as generated content: it is a decoration, deliberately paler than any text
        may be, and the heading under it says the same thing in words. */}
    <span
      aria-hidden="true"
      className="block text-[5.5rem] leading-none font-extrabold tracking-tighter text-cv-border-soft before:content-['404'] lg:text-[8.75rem]"
    />
    <h1
      className="text-[1.625rem] font-extrabold tracking-tight text-cv-text lg:text-[2.125rem]"
      data-route-heading
      id="route-heading"
      tabIndex={-1}
    >
      העמוד לא נמצא
    </h1>
    <p className="max-w-75 text-body leading-relaxed text-cv-text-muted lg:max-w-115 lg:text-[1.0625rem]">
      ייתכן שהכתובת השתנתה או שהרשומה נסגרה. אפשר לחזור לקורות החיים ולהמשיך משם.
    </p>
    <Link
      className={buttonClasses("primary", "mt-2 shadow-action max-lg:w-full lg:min-h-12.5 lg:px-6", "large")}
      to={routePaths.home()}
    >
      חזרה לקורות החיים
    </Link>
  </section>
);
