import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import type { ApplicationListItem } from "../../api/contracts";
import { Button } from "../../ui/Button";
import { RecruitmentUpdateDialog } from "./RecruitmentUpdateDialog";

type RecruitmentManagerTarget = Pick<ApplicationListItem, "company" | "id" | "target_role">;

export const RecruitmentManagerButton = ({
  application,
}: {
  application: RecruitmentManagerTarget;
}) => {
  const [open, setOpen] = useState(false);

  return (
    <>
      <Button onClick={() => setOpen(true)} variant="secondary">
        <SlidersHorizontal aria-hidden="true" className="size-4" />
        עדכון סטטוס ומשימות
      </Button>
      <RecruitmentUpdateDialog application={open ? application : null} onClose={() => setOpen(false)} />
    </>
  );
};
