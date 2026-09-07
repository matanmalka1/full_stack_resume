interface DraftSectionNavProps {
  sections: { claims: number; id: string; name: string }[];
}

/* Where the document's parts are, when there are enough of them to lose your place in.

   A tailored CV runs to several sections and sixty-odd lines, and the editor column is
   one long scroll: reaching "Experience" from the top meant scrolling past everything
   above it, and coming back from a fact panel at the foot meant scrolling past it again.
   These are plain in-page anchors to the section headings - no scroll listener, no
   active-state tracking, nothing that has to be kept in step with the page. */
export const DraftSectionNav = ({ sections }: DraftSectionNavProps) => (
  <nav aria-label="מעבר לסעיפי הטיוטה" className="flex flex-wrap gap-2">
    {sections.map((section) => (
      <a
        aria-label={`${section.name} ${section.claims}`}
        className="inline-flex min-h-9 items-center gap-1.5 rounded-pill border border-cv-border bg-cv-surface px-3 text-support font-semibold text-cv-text-muted transition-colors hover:bg-cv-surface-muted hover:text-cv-text focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-accent"
        dir="auto"
        href={`#${section.id}`}
        key={section.id}
      >
        {section.name}
        <span className="text-cv-text-muted">{section.claims}</span>
      </a>
    ))}
  </nav>
);
