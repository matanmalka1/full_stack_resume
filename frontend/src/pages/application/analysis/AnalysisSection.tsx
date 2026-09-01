import type { ReactNode } from "react";

/* One labelled block, shared by every part of the analysis panel that reports a single
   finding under its own heading - the rationale, the requirement lists, the gaps.

   A `<section>`, not a `<div>`: the panel lays its findings out with the same
   `divide-y` rhythm JobDetailsPage uses for its own top-level sections, and that
   selector reaches direct `<section>` children. A finding that renders nothing returns
   null instead of an empty section, so an absent finding costs no divider and no
   padding rather than leaving a blank band. */
export const AnalysisSection = ({ children, title }: { children: ReactNode; title: string }) => (
  <section>
    <h3 className="mb-2 text-support font-semibold text-cv-text">{title}</h3>
    {children}
  </section>
);
