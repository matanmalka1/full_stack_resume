import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import type { ApplicationDetail } from "@/api/contracts";
import { cx } from "@/ui/cx";
import { cardClasses } from "@/ui/surface";
import { type PreparationRowState, preparationProgress } from "../model/applicationHub";

const markClasses: Record<PreparationRowState, string> = {
  done: "bg-cv-accent text-cv-on-accent",
  current: "border-2 border-cv-accent",
  upcoming: "border-2 border-cv-border-strong",
};

const stateWords: Record<PreparationRowState, string> = {
  done: "הושלם",
  current: "השלב הנוכחי",
  upcoming: "בהמשך",
};

/* A phone lists the five steps one under another, the open one on a tinted row; a wide
   screen lays them side by side as tiles - done ones filled, the open one outlined, the
   ones ahead drawn dashed. */
const itemClasses: Record<PreparationRowState, string> = {
  done: "text-cv-text-muted lg:bg-cv-canvas",
  current:
    "font-bold text-cv-text max-lg:-mx-2 max-lg:my-0.5 max-lg:min-h-11 max-lg:rounded-control-sm max-lg:bg-cv-canvas max-lg:px-2 lg:border-2 lg:border-cv-accent",
  upcoming: "text-cv-text-muted lg:border lg:border-dashed lg:border-cv-border-soft",
};

/* The hub's account of its CV: five steps, each done, current or ahead, and the way to the
   screen each is worked on wherever that screen has something to show. The whole row (a
   tile, from the large breakpoint) is the link; on a phone the open one also says what the
   press does there - "עריכה" in the editor, "פתיחה" elsewhere. */
export const PreparationProgressCard = ({ detail }: { detail: ApplicationDetail }) => {
  const { position, rows, total } = preparationProgress(detail);

  return (
    <section
      aria-labelledby="preparation-progress-heading"
      className={cardClasses("flex flex-col gap-1 p-3.5 lg:gap-3.5 lg:p-5")}
    >
      <div className="flex items-center justify-between gap-3 pb-1.5 lg:pb-0">
        <h2 className="text-body font-extrabold text-cv-text" id="preparation-progress-heading">
          הכנת קורות החיים
        </h2>
        <span className="rounded-pill bg-cv-surface-muted px-2.5 py-0.5 text-caption font-bold text-cv-text tabular-nums">
          <span className="sr-only">שלב </span>
          <span dir="ltr">{`${position}/${total}`}</span>
        </span>
      </div>
      <ol className="flex flex-col lg:grid lg:grid-cols-5 lg:gap-2">
        {rows.map((row) => {
          const content = (
            <>
              <span
                aria-hidden="true"
                className={cx(
                  "flex size-5.5 shrink-0 items-center justify-center rounded-pill lg:size-5",
                  markClasses[row.state],
                )}
              >
                {row.state === "done" ? (
                  <Check className="size-icon-sm [stroke-width:var(--stroke-icon-strong)]" />
                ) : null}
                {row.state === "current" ? <span className="size-2 rounded-pill bg-cv-accent" /> : null}
              </span>
              <span className={cx("min-w-0 flex-1", row.state === "done" && row.href !== null && "max-lg:underline")}>
                {row.label}
                <span className="sr-only">{`, ${stateWords[row.state]}`}</span>
              </span>
              {row.state === "current" && row.href !== null ? (
                <span className="text-support font-bold text-cv-text underline underline-offset-4 lg:hidden">
                  {row.key === "draft" || row.key === "approve" ? "עריכה" : "פתיחה"}
                </span>
              ) : null}
            </>
          );
          const shape = cx(
            "flex min-h-9 items-center gap-3 text-label lg:min-h-16 lg:flex-col lg:items-start lg:gap-1 lg:rounded-control lg:px-3 lg:py-2.5 lg:text-support",
            itemClasses[row.state],
          );

          return (
            <li aria-current={row.state === "current" ? "step" : undefined} key={row.key}>
              {row.href === null ? (
                <div className={shape}>{content}</div>
              ) : (
                <Link className={cx(shape, "transition-colors hover:text-cv-text")} to={row.href}>
                  {content}
                </Link>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
};
