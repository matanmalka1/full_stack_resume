import { AnalysisSection } from "./AnalysisSection";

/* Backend-authored and not translated: the deterministic classifier builds this sentence
   itself, so a Hebrew rendering here would be this client paraphrasing a string it does
   not own - and would drift the moment the rule behind it changes. It is labelled as the
   engine's own wording instead, and picks its own direction so an English sentence is not
   reordered into a Hebrew shell. */
export const RationaleSection = ({ rationale }: { rationale: string | null }) => {
  if (rationale === null) {
    return null;
  }

  return (
    <AnalysisSection title="הנימוק">
      <blockquote className="border-s-2 border-cv-border ps-4">
        <p className="text-body leading-7 text-cv-text" dir="auto">
          {rationale}
        </p>
        <p className="mt-2 text-support text-cv-text-muted">נוסח אוטומטית על ידי מנוע הסיווג, בשפת המקור.</p>
      </blockquote>
    </AnalysisSection>
  );
};
