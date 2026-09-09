import type { Classification } from "@/api/analyses";
import { Button } from "@/ui/Button";
import { Callout } from "@/ui/Callout";
import type { Tone } from "@/ui/tone";
import { confidenceText, fitDescriptions, fitLabels, fitTones } from "../model/analysisLabels";

/* The state of the analysis, above everything this screen offers.

   It used to be readable only at the foot of the page, under every decision card: the
   reader was asked to choose a track and to accept a risk before being told that the
   requirements had not been read at all and that the confidence behind the classification
   was zero. The verdict is what those decisions are about, so it is stated first.

   It is the one place the verdict is explained. The same sentence stood in the analysis
   masthead, in the decision panel's own preamble, and again on the control that accepts
   it; here it is said once and the full diagnosis is a link away rather than a repeat.

   How many decisions are open is not the banner's to say. That count is carried by the
   decisions sub-tab's badge, where it is a target, and by the commit checklist, where it
   is live progress against named decisions; stated a third time here it was the same
   number in a place that could disagree with them on any refetch. The banner keeps only
   the fact the count implies - that decisions are open - in its tone, not a tally. */
interface BannerContent {
  body: string;
  title: string;
  tone: Tone;
}

const bannerContent = (
  classification: Classification | null,
  decisionCount: number,
  supersededAnalysis: boolean,
): BannerContent => {
  if (supersededAnalysis) {
    return {
      body: "הניתוח האחרון שנשמר נעשה מול תצלום משרה קודם, ולכן אינו מוצג כאן. ניתוח חדש מול התצלום הפעיל הוא מה שיציג את הסיווג העדכני.",
      title: "הניתוח שעל המסך אינו הניתוח הפעיל",
      tone: "warning",
    };
  }

  if (classification === null) {
    return {
      body: "אין ניתוח פעיל למשרה הזו. ניתוח המשרה הוא מה שקובע את הסיווג, את הפערים ואת העובדות שייכנסו לקורות החיים.",
      title: "המשרה טרם נותחה",
      tone: "neutral",
    };
  }

  /* Fit and confidence are recorded independently - a classification may carry one
     without the other - so the headline states whichever exists rather than a sentence
     that would be wrong when only one is present. */
  const fitPart = classification.fit === null ? "הניתוח הושלם" : fitLabels[classification.fit];
  const confidencePart =
    classification.confidence === null ? null : `רמת ביטחון ${confidenceText(classification.confidence)}`;
  const explanation =
    classification.fit === null
      ? "הניתוח נשמר ללא דירוג התאמה. פרטי האבחון המלאים מראים מה כן נקרא מהמשרה."
      : fitDescriptions[classification.fit];

  return {
    body: explanation,
    title: confidencePart === null ? fitPart : `${fitPart} · ${confidencePart}`,
    /* Warning, not blocker, while a decision is open: `needs_review` is the same state
       `preparationStateTones` already reports as "warning" everywhere else on this
       screen - the stepper, the header badge - and a decision here is always answerable
       from the form directly below, never a dead end. Blocker is reserved for what a
       reader cannot act their way out of, which is not this. With nothing open, the tone
       is the verdict's own. */
    tone: decisionCount > 0 ? "warning" : classification.fit === null ? "neutral" : fitTones[classification.fit],
  };
};

export const AnalysisStatusBanner = ({
  classification,
  decisionCount,
  onShowDiagnostics,
  supersededAnalysis,
}: {
  classification: Classification | null;
  decisionCount: number;
  /* Absent when there is no diagnosis to show - an Application with no active analysis
     has no diagnostics tab, and a link to an empty region is worse than none. */
  onShowDiagnostics: (() => void) | null;
  supersededAnalysis: boolean;
}) => {
  const { body, title, tone } = bannerContent(classification, decisionCount, supersededAnalysis);

  return (
    <Callout
      action={
        onShowDiagnostics === null ? undefined : (
          <Button className="min-h-0! px-0! underline underline-offset-2" onClick={onShowDiagnostics} variant="ghost">
            לפרטי האבחון המלאים ←
          </Button>
        )
      }
      emphasis="banner"
      title={title}
      tone={tone}
    >
      {body}
    </Callout>
  );
};
