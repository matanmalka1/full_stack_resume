import type { ReactNode } from "react";

import type { Reason } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { Disclosure } from "@/ui/Disclosure";
import { reasonTitle } from "../model/preparationLabels";

/* The server's own sentence behind a reason. It is English and written for a log -
   evidence for a bug report, not the explanation - so it is folded rather than shown. */
export const ReasonDetails = ({ message }: { message: string }) => (
  <Disclosure summary="פרטי הסיבה">
    <p dir="auto">{message}</p>
  </Disclosure>
);

/* One projected reason as the reader meets it on every screen that reports it: its
   translated title, the tone it blocks or warns at, and the server's sentence folded
   beneath. What resolves it differs by screen - a link to another step, or a control in
   the editor itself - so the action and any explanation above the fold are the caller's. */
export const ReasonCallout = ({
  action,
  children,
  fallbackTitle,
  reason,
  tone,
}: {
  action?: ReactNode;
  children?: ReactNode;
  fallbackTitle: string;
  reason: Pick<Reason, "code" | "message">;
  tone: "blocker" | "warning";
}) => (
  <Callout action={action} title={reasonTitle(reason.code, fallbackTitle)} tone={tone}>
    {children}
    <ReasonDetails message={reason.message} />
  </Callout>
);
