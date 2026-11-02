import { ChevronDown, ExternalLink, FileText } from "lucide-react";
import { useId, useState } from "react";

import type { ApplicationDetail } from "@/api/contracts";
import { LtrText } from "@/ui/LtrText";
import { cx } from "@/ui/cx";
import { cardClasses } from "@/ui/surface";
import { sourceHostname } from "../model/applicationPresentation";

/* The posting the CV is tailored to, as the hub's last card: reference, read rather than
   worked on. Editing it is the analysis step's (`JobPostingPanel`), where a change is
   weighed against the analysis it invalidates.

   A wide screen shows the text in the card. On a phone it is folded behind its title, a
   row a press away, so the step cards above stay the screen's subject; the text is in the
   document once either way. */
export const JobPostingCard = ({ detail }: { detail: ApplicationDetail }) => {
  const [open, setOpen] = useState(false);
  const bodyId = useId();
  const posting = detail.job_posting;
  const host = sourceHostname(posting.source_url);

  return (
    <section aria-labelledby="hub-job-posting-heading" className={cardClasses("lg:flex lg:flex-col lg:gap-2.5 lg:p-5")}>
      <h2 className="text-body font-extrabold text-cv-text max-lg:sr-only" id="hub-job-posting-heading">
        מודעת המשרה
      </h2>
      <button
        aria-controls={bodyId}
        aria-expanded={open}
        className="flex min-h-13 w-full items-center gap-2.5 px-3.5 text-start text-body font-bold text-cv-text lg:hidden"
        onClick={() => setOpen((current) => !current)}
        type="button"
      >
        <FileText aria-hidden="true" className="size-icon-lg shrink-0" />
        <span className="flex-1">מודעת המשרה</span>
        <ChevronDown
          aria-hidden="true"
          className={cx("size-icon-lg shrink-0 text-cv-text-muted transition-transform", open && "rotate-180")}
        />
      </button>
      <div className={cx("max-lg:px-3.5 max-lg:pb-3.5", open ? "block" : "hidden", "lg:block")} id={bodyId}>
        {posting.job_text.trim() === "" ? (
          <p className="text-label text-cv-text-muted">נוסח המשרה אינו זמין.</p>
        ) : (
          <p className="text-label leading-relaxed whitespace-pre-wrap text-cv-text-muted" dir="auto">
            {posting.job_text}
          </p>
        )}
        {posting.source_url == null || host === null ? null : (
          <a
            className="mt-3 inline-flex max-w-full items-center gap-1.5 text-support font-bold text-cv-text underline underline-offset-4"
            href={posting.source_url}
            rel="noreferrer noopener"
            target="_blank"
          >
            מודעת המקור
            <LtrText>({host})</LtrText>
            <ExternalLink aria-hidden="true" className="size-icon-sm shrink-0" />
          </a>
        )}
      </div>
    </section>
  );
};
