import { AnalysisSection } from "./AnalysisSection";
import { TermList } from "./TermList";

/* Mandatory requirements, preferred requirements, and keywords are three term lists under
   three different titles, not three different shapes - so they share one component rather
   than three near-identical copies of the same section-plus-list markup. */
export const RequirementsSection = ({ items, title }: { items: string[]; title: string }) => {
  if (items.length === 0) {
    return null;
  }

  return (
    <AnalysisSection title={title}>
      <TermList items={items} />
    </AnalysisSection>
  );
};
