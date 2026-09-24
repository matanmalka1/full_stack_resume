import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

/* One fixed place, at the top of a step, for the status of the work behind it - the same
   portal shape `WideRow` and `CommitBar` use. A screen renders its Operation status
   wherever its own code happens to hold the watch, and without a shared slot the row
   landed under the heading on one step, under the version card on the next, and below the
   PDF preview on the last. */
export const StatusSlotTargetContext = createContext<HTMLElement | null | undefined>(undefined);

/* Portals into the shell's slot when one is provided and mounted; renders in place when
   no shell asked for it (component tests included). */
export const StatusSlot = ({ children }: { children: ReactNode }) => {
  const target = useContext(StatusSlotTargetContext);
  if (target === undefined) return children;
  if (target === null) return null;
  return createPortal(children, target);
};
