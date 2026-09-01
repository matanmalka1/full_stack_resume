import type { ReactNode } from "react";

/* One labelled block, shared by every part of the analysis panel that reports a single
   finding under its own heading - the rationale, the requirement lists, the gaps. */
export const AnalysisSection = ({ children, title }: { children: ReactNode; title: string }) => (
  <div>
    <h3 className="mb-2 text-support font-semibold text-cv-text">{title}</h3>
    {children}
  </div>
);
