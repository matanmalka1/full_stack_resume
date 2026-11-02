import type { FactStatus } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { factStatusIcons, factStatusLabels, factStatusTones } from "../model/factLabels";

/* One reading of a fact's status wherever it appears: the same Hebrew label, tone and
   icon on the pool, the fact's own page, the draft editor and the claim panel. A fact
   waiting for confirmation is the one state that asks for the reader, so it alone draws
   filled, as the design's pending pill does. */
export const FactStatusBadge = ({ className, status }: { className?: string; status: FactStatus }) => (
  <StatusBadge
    className={className}
    icon={factStatusIcons[status]}
    tone={factStatusTones[status]}
    variant={status === "pending" ? "solid" : "soft"}
  >
    {factStatusLabels[status]}
  </StatusBadge>
);
