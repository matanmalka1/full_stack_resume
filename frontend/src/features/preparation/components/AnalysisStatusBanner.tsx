import type { ReactNode } from "react";

import type { Classification } from "@/api/analyses";
import { Callout } from "@/ui/Callout";
import type { Tone } from "@/ui/tone";
import { confidenceText, fitDescriptions, fitLabels, fitTones } from "../model/analysisLabels";

/* The analysis verdict is stated before the detailed diagnostics. Fit is information,
   not an acknowledgement request, so the banner never changes tone based on whether the
   user has accepted it. */
interface BannerContent {
  body: string;
  title: ReactNode;
  tone: Tone;
}

const bannerContent = (classification: Classification | null, supersededAnalysis: boolean): BannerContent => {
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

  /* Fit is shown and decided on by nobody: a low Fit or a hard gap tells the user how well
     they match this posting, and they may still draft and apply. There is no confidence
     line beside it - the analysis contract reports no classification confidence, and a
     second percentage here would invite reading one as an explanation of the other. */
  const fitLevelPart = classification.fit === null ? "הניתוח הושלם" : fitLabels[classification.fit];
  const fitLine =
    classification.fitScore === null
      ? fitLevelPart
      : `התאמה למשרה: ${confidenceText(classification.fitScore)} · ${fitLevelPart}`;
  /* The level is not the score read off a scale: mandatory requirements the approved
     facts do not fully cover cap it, however high the percentage. Beside "83% · low" the
     reader needs that said, or the two read as a contradiction. Stated as how the level
     is decided, not as the cause of this one - a low score alone can set it too. */
  const hardGapCount = classification.gaps.filter((gap) => gap.severity === "hard").length;
  const capNote =
    (classification.fit === "low" || classification.fit === "medium") && hardGapCount > 0
      ? ` רמת ההתאמה נקבעת גם לפי דרישות החובה, ולא רק לפי הציון: ${
          hardGapCount === 1 ? "דרישת חובה אחת לא מכוסה במלואה" : `${hardGapCount} דרישות חובה לא מכוסות במלואן`
        }.`
      : "";
  const explanation =
    classification.fit === null
      ? "הניתוח נשמר ללא דירוג התאמה. פרטי האבחון המלאים מראים מה כן נקרא מהמשרה."
      : `${fitDescriptions[classification.fit]}${capNote}`;

  return {
    body: explanation,
    title: fitLine,
    tone: classification.fit === null ? "neutral" : fitTones[classification.fit],
  };
};

export const AnalysisStatusBanner = ({
  classification,
  supersededAnalysis,
}: {
  classification: Classification | null;
  supersededAnalysis: boolean;
}) => {
  const { body, title, tone } = bannerContent(classification, supersededAnalysis);

  /* A missing AI provider is not repeated here. The step's bar says it beside the inert
     analysis button and leads with the way to Settings; a second copy of both in this
     banner left two identical buttons on one screen. */
  return (
    <Callout emphasis="banner" title={title} tone={tone}>
      <p>{body}</p>
    </Callout>
  );
};
