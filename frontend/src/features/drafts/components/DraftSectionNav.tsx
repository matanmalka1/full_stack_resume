interface DraftSectionNavProps {
  sections: { claims: number; id: string; name: string }[];
}

/* Where the document's parts are, when there are enough of them to lose your place in.

   A tailored CV runs to several sections and sixty-odd lines, and the editor column is
   one long scroll: reaching "Experience" from the top meant scrolling past everything
   above it, and coming back from the last section meant scrolling past it again.
   These are plain in-page anchors to the section headings - no scroll listener, no
   active-state tracking, nothing that has to be kept in step with the page. */
export const DraftSectionNav = ({ sections }: DraftSectionNavProps) => (
  <nav aria-label="מעבר לסעיפי הטיוטה" className="flex flex-wrap gap-1.5">
    {sections.map((section) => (
      <a
        aria-label={`${section.name} ${section.claims}`}
        className="inline-flex min-h-8 items-center gap-1.5 rounded-pill bg-cv-surface-muted px-3 text-support font-semibold text-cv-text transition-colors hover:bg-cv-accent-soft hover:text-cv-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-accent"
        dir="auto"
        href={`#${section.id}`}
        key={section.id}
      >
        {section.name}
        <span className="font-normal text-cv-text-muted">{section.claims}</span>
      </a>
    ))}
  </nav>
);
