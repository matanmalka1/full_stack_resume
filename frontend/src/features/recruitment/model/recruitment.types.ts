import type { ApplicationListItem, TransitionableRecruitmentStatus } from "@/api/contracts";

export type RecruitmentManagerTarget = Pick<ApplicationListItem, "company" | "id" | "target_role">;

export interface RecruitmentUpdateFields {
  nextAction: string;
  nextActionDate: string;
  notes: string;
  reason: string;
  targetStatus: TransitionableRecruitmentStatus | "";
}
