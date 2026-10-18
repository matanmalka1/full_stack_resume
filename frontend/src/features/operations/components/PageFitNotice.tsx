import type { PageFitReport } from "@/api/contracts";
import { Callout } from "@/ui/Callout";
import { pagesLabel } from "../model/operationLabels";

type TrimmedClaim = NonNullable<PageFitReport["trimmed"]>[number];

/* Where the line sat. A heading that only repeats its section's name says nothing twice. */
const lineContext = ({ heading, section }: TrimmedClaim) =>
  heading == null || heading === section ? section : `${section} · ${heading}`;

const TrimmedLines = ({ lines }: { lines: TrimmedClaim[] }) => (
  <ul aria-label="שורות שהוסרו" className="mt-2 flex flex-col gap-2">
    {lines.map((line) => (
      <li className="flex flex-col gap-0.5" key={line.claim_id}>
        <span className="text-support text-cv-text-muted" dir="auto">
          {lineContext(line)}
        </span>
        <span className="text-cv-text" dir="auto">
          {line.text}
        </span>
      </li>
    ))}
  </ul>
);

/* What fitting a new draft to its page limit did, when the reader has to know: no line
   leaves a draft unseen, a draft still too long is said before approval refuses it, and
   a length nobody could check is not passed off as one that fits. */
export const PageFitNotice = ({ report }: { report: PageFitReport }) => {
  const limit = pagesLabel(report.maximum);
  const trimmed = report.trimmed ?? [];

  switch (report.status) {
    case "trimmed":
      return (
        <Callout title={`קורות החיים קוצרו כדי להיכנס ל־${limit}`} tone="warning">
          <p>
            {trimmed.length === 1 ? "השורה הבאה הוסרה מהטיוטה." : `${trimmed.length} השורות הבאות הוסרו מהטיוטה.`} שורה
            שתוחזר בעריכת הטיוטה תצטרך קישור לעובדה ובדיקה, כמו כל שורה חדשה.
          </p>
          <TrimmedLines lines={trimmed} />
        </Callout>
      );
    case "over":
      return (
        <Callout title={`קורות החיים עדיין ארוכים מ־${limit}`} tone="warning">
          <p>
            גם אחרי הקיצור המרבי שמותר, הטיוטה חורגת ממגבלת העמודים. ההפקה תיכשל עד שהיא תקוצר - יש להסיר או לקצר שורות
            בעריכת הטיוטה.
          </p>
          {trimmed.length === 0 ? null : (
            <>
              <p className="mt-2">השורות הבאות כבר הוסרו:</p>
              <TrimmedLines lines={trimmed} />
            </>
          )}
        </Callout>
      );
    case "unavailable":
      return (
        <Callout title="לא ניתן היה לבדוק את אורך קורות החיים" tone="info">
          <p>
            הטיוטה נשמרה כפי שנכתבה. אם היא ארוכה מ־{limit}, ההפקה תיכשל ותציין זאת, ואז אפשר לקצר אותה בעריכת הטיוטה.
          </p>
        </Callout>
      );
    case "fits":
      return null;
  }
};
