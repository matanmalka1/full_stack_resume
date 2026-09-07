import { JOB_TEXT_MAX_BYTES } from "@/api/applications";
import type { ApplicationIntake } from "@/api/contracts";

export interface ApplicationIntakeFields {
  company: string;
  target_role: string;
  source_url: string;
  job_text: string;
}

export const emptyApplicationIntake: ApplicationIntakeFields = {
  company: "",
  target_role: "",
  source_url: "",
  job_text: "",
};

/* The posting text is evidence and must be submitted exactly as entered. Labels and
   provenance are user-facing metadata, so surrounding whitespace is not meaningful. */
export const intakeFromFields = (fields: ApplicationIntakeFields): ApplicationIntake => {
  const sourceUrl = fields.source_url.trim();

  return {
    company: fields.company.trim(),
    target_role: fields.target_role.trim(),
    job_text: fields.job_text,
    source_url: sourceUrl === "" ? null : sourceUrl,
  };
};

export const jobTextByteLength = (jobText: string): number => new TextEncoder().encode(jobText).length;

export const isJobTextWithinBudget = (jobText: string): boolean => jobTextByteLength(jobText) <= JOB_TEXT_MAX_BYTES;
