import type { OmissionReason, SelectionOutcome } from "@/api/contracts";
import type { DecisionSource } from "./selectionManifest";

/* What the SelectionPlan decided about a fact, in words. Exhaustive over the generated
   unions: an outcome or omission reason added to the backend fails this build rather
   than reaching a screen as an untranslated value.

   These belong to the plan rather than to any one screen: preparation lists the plan's
   own candidates with them, and the draft editor names the same decisions beside the
   facts it offers to include. */

export const selectionOutcomeLabels: Record<SelectionOutcome, string> = {
  pinned: "נקבעה במפורש",
  selected: "נבחרה",
  rescued: "הוחזרה לכיסוי דרישה",
  omitted: "לא נכללה",
};

export const omissionReasonLabels: Record<OmissionReason, string> = {
  below_section_budget: "לא נכנסה למכסת הסעיף",
  not_relevant_to_emphasis: "אינה רלוונטית לדגש הנוכחי",
  evicted_by_required_tag_rescue: "פינתה מקום לעובדה שנדרשה לכיסוי",
  not_in_profile_pool: "אינה במאגר של הפרופיל הזה",
  excluded_by_user: "הוחרגה על ידך",
};

/* Who placed a fact where it is, as the fact selection names it. Pinned and excluded
   facts are an overlay on the engine's ranking; the server stores a manual mark and an AI
   proposal in the same two lists, so the words say "explicitly" rather than guessing who. */
export const decisionSourceLabels: Record<DecisionSource, string> = {
  engine: "לפי דירוג המנוע",
  pinned: "נכללה במפורש",
  excluded: "הוחרגה במפורש",
  locked: "רכיב מבני קבוע",
};
