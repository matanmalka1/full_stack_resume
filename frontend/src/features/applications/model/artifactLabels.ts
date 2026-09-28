/* Hebrew for the artifact registry's open string fields.

   Open on purpose: `artifact_type`, the provider task, and the refusal code are `string`
   at the boundary, and a value this build does not recognize is a real possibility rather
   than an impossible one. So each lookup falls back - a type or a refusal code to the
   value as it arrived, a task to the artifact type's label: an untranslated
   `provider_response` says more than `undefined`, and a new refusal code reaches the
   reader as a code rather than as silence. */

const artifactTypeLabels: Record<string, string> = {
  job_snapshot: "תצלום המשרה",
  provider_response: "תשובת ספק ה־AI",
};

/* The provider task that produced a response, as the registry records it in `task`.
   The engine's six contracted tasks; an unknown one falls back to the artifact type. */
const providerTaskLabels: Record<string, string> = {
  propose_analysis: "ניתוח המשרה",
  propose_selection_plan: "הצעת בחירת עובדות",
  draft_resume: "כתיבת הטיוטה",
  assess_claim_support: "בדיקת ביסוס הטענות",
  regenerate_section: "כתיבה מחדש של סעיף",
  regenerate_claim: "כתיבה מחדש של טענה",
};

/* The three refusals `open_artifact` classifies. Each names the check that failed,
   because "מישהו העביר את הקובץ" and "מישהו שינה אותו" are ממצאים שונים. */
const unavailableReasonLabels: Record<string, string> = {
  ARTIFACT_PAYLOAD_MISSING: "הקובץ הרשום אינו נמצא באחסון.",
  ARTIFACT_HASH_MISMATCH: "תוכן הקובץ אינו תואם את חתימת ה־hash שנרשמה לו.",
  ARTIFACT_CONTAINMENT_REFUSED: "הנתיב הרשום אינו מוביל לקובץ שנמצא בתוך שורש הארטיפקטים.",
};

export const artifactTypeLabel = (artifactType: string): string => artifactTypeLabels[artifactType] ?? artifactType;

export const providerTaskLabel = (task: string): string | undefined => providerTaskLabels[task];

export const unavailableReasonLabel = (code: string): string => unavailableReasonLabels[code] ?? code;
