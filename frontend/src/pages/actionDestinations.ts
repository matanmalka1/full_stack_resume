/* Which backend action names this frontend has actually built a screen for.

   It is a route table keyed by the backend's own action vocabulary, not a second
   workflow state machine: it decides nothing about availability, which stays the §9
   projection's answer through `available_actions`. It exists so that "this action now
   has a screen" is one fact in one place - the context screen links to it and the review
   reason stops promising it is coming - rather than two that drift apart.

   An action absent from the table has no screen yet, which is the honest default. */
const destinations: Record<string, (applicationId: string) => string> = {
  apply_analysis_decisions: (applicationId) =>
    `/applications/${encodeURIComponent(applicationId)}/review`,
};

export const actionDestination = (action: string, applicationId: string): string | null =>
  destinations[action]?.(applicationId) ?? null;
