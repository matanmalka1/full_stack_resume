import { useEffect, useState } from "react";

import { cx } from "@/ui/cx";

interface DraftSectionNavProps {
  sections: { claims: number; id: string; name: string }[];
}

/* How far below the viewport's top a heading counts as scrolled into: past the sticky
   masthead, with a line of air under it. */
const READING_LINE_PX = 160;

/* The section whose heading was last scrolled past the reading line - the one the reader
   is in - or the first while none has been. Read from the headings' own positions on
   scroll rather than from an IntersectionObserver over the sections: a short section
   leaves an observed band without the next one entering it, and the mark would go dark
   between them. */
const useCurrentSection = (ids: string[]): string | undefined => {
  const key = ids.join(" ");
  const [current, setCurrent] = useState<string | undefined>(ids[0]);
  useEffect(() => {
    const sectionIds = key.split(" ");
    const update = () => {
      let found = sectionIds[0];
      for (const id of sectionIds) {
        const top = window.document.getElementById(id)?.getBoundingClientRect().top;
        if (top !== undefined && top <= READING_LINE_PX) found = id;
      }
      setCurrent(found);
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    return () => window.removeEventListener("scroll", update);
  }, [key]);
  return current;
};

/* Where the document's parts are, when there are enough of them to lose your place in.

   A tailored CV runs to several sections and sixty-odd lines, and the editor column is
   one long scroll: reaching "Experience" from the top meant scrolling past everything
   above it, and coming back from the last section meant scrolling past it again.
   These are plain in-page anchors to the section headings over that one scroll.

   From the large breakpoint they are a vertical list in the editor's start column, as the
   desktop design draws it, with the section being read filled and marked `aria-current`.
   Below it the same anchors are the phone's section tabs: one segmented strip pinned under
   the masthead, so the way to "Education" is in reach from the middle of "Experience"
   rather than back at the top. They stay anchors over one scroll, not tabs that hide the
   other sections: a hidden section would hide the claim the attention panel jumps to, and
   an edit still in it. The strip scrolls sideways when a CV has more sections than fit.
   The current fill is drawn from `lg` only, so the phone strip reads as it always has. */
export const DraftSectionNav = ({ sections }: DraftSectionNavProps) => {
  const current = useCurrentSection(sections.map((section) => section.id));
  return (
    <nav
      aria-label="מעבר לסעיפי הטיוטה"
      className="flex flex-wrap gap-1.5 max-lg:sticky max-lg:top-16 max-lg:z-(--cv-z-sticky) max-lg:flex-nowrap max-lg:gap-1 max-lg:overflow-x-auto max-lg:rounded-surface max-lg:bg-cv-surface-muted max-lg:p-1 max-lg:shadow-inner lg:flex-col lg:flex-nowrap lg:gap-0.5 lg:rounded-surface lg:border lg:border-cv-hairline lg:bg-cv-surface lg:p-2 lg:shadow-card"
    >
      {sections.map((section) => {
        const active = section.id === current;
        return (
          <a
            aria-current={active ? "location" : undefined}
            aria-label={`${section.name} ${section.claims}`}
            className={cx(
              "inline-flex min-h-8 items-center gap-1.5 rounded-pill bg-cv-surface-muted px-3 text-support font-semibold text-cv-text transition-colors hover:bg-cv-accent-soft hover:text-cv-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cv-accent max-lg:min-h-11 max-lg:flex-1 max-lg:shrink-0 max-lg:justify-center max-lg:whitespace-nowrap max-lg:rounded-control max-lg:bg-transparent max-lg:focus-visible:-outline-offset-2",
              /* A row of the list rather than a pill: full width, the count at its far
                 end, and only the current section filled. */
              "lg:min-h-10 lg:justify-between lg:rounded-control",
              active ? "lg:font-bold" : "lg:bg-transparent lg:font-medium lg:text-cv-text-muted",
            )}
            dir="auto"
            href={`#${section.id}`}
            key={section.id}
          >
            {section.name}
            <span className="font-normal text-cv-text-muted">{section.claims}</span>
          </a>
        );
      })}
    </nav>
  );
};
