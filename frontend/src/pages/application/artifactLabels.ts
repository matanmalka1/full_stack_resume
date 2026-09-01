/* Hebrew for the artifact registry's open string fields.

   Open on purpose: `artifact_type`, `lifecycle_status`, and the refusal code are
   `string` at the boundary, and a type or a status this build does not recognize is a
   real possibility rather than an impossible one. So each lookup falls back to the value
   as it arrived - an untranslated `provider_response` says more than `undefined`, and a
   new refusal code reaches the reader as a code rather than as silence. */

const artifactTypeLabels: Record<string, string> = {
  resume_pdf: "קובץ PDF של קורות החיים",
  resume_html: "קובץ HTML של קורות החיים",
  resume_markdown: "קורות החיים ב־Markdown",
  visual_evidence: "צילום מסך של התצוגה",
  claim_manifest: "מניפסט הטענות",
  working_draft_snapshot: "עותק היסטורי של טיוטה",
  job_snapshot: "תצלום המשרה",
  provider_response: "תשובת ספק ה־AI",
};

/* The artifacts a person is handed or looks at, as opposed to the ones the engine keeps
   as evidence of how it got there. Both are shown; this decides which are shown first
   and which sit behind a deliberate press. */
const deliverableTypes = new Set(["resume_pdf", "resume_html", "resume_markdown", "visual_evidence"]);

const lifecycleLabels: Record<string, string> = {
  rendered: "נוצר",
  approved: "מאושר",
  submitted: "הוגש",
  archived: "בארכיון",
};

/* The three refusals `open_artifact` classifies. Each names the check that failed,
   because "מישהו העביר את הקובץ" and "מישהו שינה אותו" are ממצאים שונים. */
const unavailableReasonLabels: Record<string, string> = {
  ARTIFACT_PAYLOAD_MISSING: "הקובץ הרשום אינו נמצא באחסון.",
  ARTIFACT_HASH_MISMATCH: "תוכן הקובץ אינו תואם את חתימת ה־hash שנרשמה לו.",
  ARTIFACT_CONTAINMENT_REFUSED: "הנתיב הרשום אינו מוביל לקובץ שנמצא בתוך שורש הארטיפקטים.",
};

export const artifactTypeLabel = (artifactType: string): string => artifactTypeLabels[artifactType] ?? artifactType;

export const isDeliverableArtifact = (artifactType: string): boolean => deliverableTypes.has(artifactType);

export const lifecycleLabel = (lifecycleStatus: string): string => lifecycleLabels[lifecycleStatus] ?? lifecycleStatus;

export const unavailableReasonLabel = (code: string): string => unavailableReasonLabels[code] ?? code;
