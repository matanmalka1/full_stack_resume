import type { DraftClaim } from "@/api/contracts";

/* What may be done to any one line of the draft. The editor has one policy for every
   claim, whichever section it sits in, so the commands travel together rather than as
   five separate props repeated down the tree. */
export interface DraftClaimActions {
  /* A keystroke. It goes to the autosave buffer, never straight to the server. */
  onEdit: (claim: DraftClaim, text: string) => void;
  /* The edit is finished - a blur, or the row being closed - so the buffer may go now
     instead of waiting out the debounce. */
  onCommit: () => void;
  /* A brand-new line, written free-hand into a named section. It lands `pending`, same
     as any other line nothing has authorized yet. */
  onAdd: (section: string, text: string) => void;
  onRegenerate: (claim: DraftClaim) => void;
  onRemove: (claim: DraftClaim) => void;
  /* Regeneration freezes the saved version, so it is withheld while anything is unsaved
     or while a regeneration is already running, and when AI is unavailable. */
  regenerationDisabled: boolean;
}

/* What turning an unsupported line into a confirmed fact needs from the Application,
   passed as a settled contract rather than by handing the whole projection downward. */
export interface ClaimFactContext {
  analysisId: string | null;
  applicationId: string;
  language: string;
  profile: string | null;
}
