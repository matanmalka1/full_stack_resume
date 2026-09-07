import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { buttonClasses } from "@/ui/Button";
import { actionDestination, actionLabel } from "@/features/preparation";

/* The one thing to do next, in the masthead.

   It is a destination, never a command: the Application screen composes the domains that
   execute, and duplicating their controls here would put two live buttons for one action
   on one page. `recommended_action` is the projection's own answer to "what is this
   waiting on", and `actionDestination` is the frontend's answer to "does a screen for it
   exist yet" - with no screen there is nothing honest to offer, so nothing is drawn and
   the reader is left with the tabs.

   A recommendation that resolves to preparation resolves to this same screen at its
   preparation address, which is why this needs no special case for it: following the
   link changes the path, and the path is what selects the tab. */
export const ApplicationPrimaryAction = ({ detail }: { detail: ApplicationDetail }) => {
  const recommended = detail.recommended_action ?? null;
  const href = recommended === null ? null : actionDestination(recommended, detail.application.id);

  if (recommended === null || href === null) {
    return null;
  }

  return (
    <Link className={buttonClasses("primary")} to={href}>
      {actionLabel(recommended)}
      <ArrowLeft aria-hidden="true" className="size-4 shrink-0" />
    </Link>
  );
};
