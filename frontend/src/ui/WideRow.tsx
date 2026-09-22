import { createContext, useContext, type ReactNode } from "react";
import { createPortal } from "react-dom";

/* The same portal shape `CommitBar` uses: a wizard step owns one physical position for
   the wide row - `PageShell`'s `afterBody` slot - even though the component deciding
   what belongs there lives several layers below, inside `PreparationView`, where the
   classification driving it is already computed. Portalling avoids a second reading of
   that projection just to place the same content in a different slot. */
export const WideRowTargetContext = createContext<HTMLElement | null | undefined>(undefined);

/* Renders `children` into the wizard shell's `afterBody` slot when a step has opted in
   and the shell has mounted its target. Falls back to rendering in place - unset
   context, or a step that never asked for the slot - so a standalone caller (component
   tests included) still gets its content. */
export const WideRow = ({ children }: { children: ReactNode }) => {
  const target = useContext(WideRowTargetContext);
  if (target === undefined) return children;
  if (target === null) return null;
  return createPortal(children, target);
};
