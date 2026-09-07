import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";

import { Button } from "@/ui/Button";
import type { RecruitmentManagerTarget } from "../model/recruitment.types";
import { RecruitmentUpdateDialog } from "./RecruitmentUpdateDialog";

export const RecruitmentManagerButton = ({ application }: { application: RecruitmentManagerTarget }) => {
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
