interface DraftSectionNavProps {
  sections: { claims: number; id: string; name: string }[];
}

/* Where the document's parts are, when there are enough of them to lose your place in.

   A tailored CV runs to several sections and sixty-odd lines, and the editor column is
   one long scroll: reaching "Experience" from the top meant scrolling past everything
   above it, and coming back from the last section meant scrolling past it again.
   These are plain in-page anchors to the section headings - no scroll listener, no
   active-state tracking, nothing that has to be kept in step with the page.

   Below the large breakpoint the same anchors are the phone's section tabs: one segmented
   strip pinned under the masthead, so the way to "Education" is in reach from the middle
   of "Experience" rather than back at the top. They stay anchors over one scroll, not
   tabs that hide the other sections: a hidden section would hide the claim the attention
   panel jumps to, and an edit still in it. The strip scrolls sideways when a CV has more
   sections than fit. */
export const DraftSectionNav = ({ sections }: DraftSectionNavProps) => (
  <nav
    aria-label="מעבר לסעיפי הטיוטה"
    className="flex flex-wrap gap-1.5 max-lg:sticky max-lg:top-16 max-lg:z-(--cv-z-sticky) max-lg:flex-nowrap max-lg:gap-1 max-lg:overflow-x-auto max-lg:rounded-surface max-lg:bg-cv-surface-muted max-lg:p-1 max-lg:shadow-inner"
  >
    {sections.map((section) => (
      <a
        aria-label={`${section.name} ${section.claims}`}
        className="inline-flex min-h-8 items-center gap-1.5 rounded-pill bg-cv-surface-muted px-3 text-support font-semibold text-cv-text transition-colors hover:bg-cv-accent-soft hover:text-cv-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-accent max-lg:min-h-11 max-lg:flex-1 max-lg:shrink-0 max-lg:justify-center max-lg:whitespace-nowrap max-lg:rounded-control max-lg:bg-transparent max-lg:focus-visible:-outline-offset-2"
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
