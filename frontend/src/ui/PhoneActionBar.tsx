import type { ReactNode } from "react";

/* The bar a phone's flow screen closes on: the screen's own bottom edge, a hairline above
   it, one or two commands across its width at the large button's height. Fixed rather
   than sticky, so a short screen still ends on it; the spacer before it keeps the last
   card clear of it.

   For a screen that renders it only below the large breakpoint - on a wide screen the
   same commands sit in the screen's own header or card, where the design draws them.
   Children are the commands themselves; the first takes its own width and the last fills
   the rest, unless a child says otherwise. */
export const PhoneActionBar = ({ children }: { children: ReactNode }) => (
  <>
    <div aria-hidden="true" className="h-24" />
    <div className="fixed inset-x-0 bottom-0 z-(--cv-z-sticky) flex gap-2 border-t border-cv-hairline bg-cv-surface/95 px-4 pt-3 pb-[calc(env(safe-area-inset-bottom,0px)+1rem)] backdrop-blur-xl *:min-h-13 *:rounded-control-lg *:text-body *:last:flex-1">
      {children}
    </div>
  </>
);
