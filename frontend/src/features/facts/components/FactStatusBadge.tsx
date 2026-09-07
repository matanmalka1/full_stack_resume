import type { FactStatus } from "@/api/contracts";
import { StatusBadge } from "@/ui/StatusBadge";
import { factStatusIcons, factStatusLabels, factStatusTones } from "../model/factLabels";

/* One reading of a fact's status wherever it appears: the same Hebrew label, tone and
   icon on the settings pool, the draft editor and the claim panel. */
export const FactStatusBadge = ({ className, status }: { className?: string; status: FactStatus }) => (
  <StatusBadge className={className} icon={factStatusIcons[status]} tone={factStatusTones[status]}>
    {factStatusLabels[status]}
  </StatusBadge>
);
