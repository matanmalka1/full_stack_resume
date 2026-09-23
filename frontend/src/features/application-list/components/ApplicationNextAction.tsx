import type { ApplicationListItem } from "@/api/contracts";

/* The recruitment reminder on a stage card: one quiet line, because the card's command
   below it is the step to take and the reminder is only what the reader asked to be
   told. The table and the cards carry it inside their next-action block instead. */
export const ApplicationNextAction = ({ item }: { item: ApplicationListItem }) =>
  item.next_action == null ? null : (
    <p className="line-clamp-2 rounded-control bg-cv-surface-muted px-2 py-1.5 text-support text-cv-text-muted">
      <strong className="text-cv-text">הבא: </strong>
      <span dir="auto">{item.next_action}</span>
    </p>
  );
