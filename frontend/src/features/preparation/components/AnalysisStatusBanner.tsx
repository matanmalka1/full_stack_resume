import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import type { Classification } from "@/api/analyses";
import { routePaths } from "@/app/routePaths";
import { buttonClasses } from "@/ui/Button";
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
  const explanation =
    classification.fit === null
      ? "הניתוח נשמר ללא דירוג התאמה. פרטי האבחון המלאים מראים מה כן נקרא מהמשרה."
      : fitDescriptions[classification.fit];

  return {
    body: explanation,
    title: fitLine,
    tone: classification.fit === null ? "neutral" : fitTones[classification.fit],
  };
};

export const AnalysisStatusBanner = ({
  classification,
  providerMissing = false,
  supersededAnalysis,
}: {
  classification: Classification | null;
  /* No AI provider can analyze. Said here, beside "not analyzed yet", with the way to fix
     it - rather than in a separate line under the step rail, where it was easy to miss. */
  providerMissing?: boolean;
  supersededAnalysis: boolean;
}) => {
  const { body, title, tone } = bannerContent(classification, supersededAnalysis);
  const needsProvider = providerMissing && classification === null && !supersededAnalysis;

  return (
    <Callout
      /* The fix as a control on its own line, not a link at the tail of the explanation
         where it read as more of the same sentence. */
      action={
        needsProvider ? (
          <Link className={buttonClasses("secondary")} to={routePaths.settings}>
            פתיחת ההגדרות
          </Link>
        ) : undefined
      }
      emphasis="banner"
      title={title}
      tone={tone}
    >
      <p>{body}</p>
      {needsProvider ? <p className="mt-1">כדי לנתח את המשרה יש להגדיר ולהפעיל ספק AI בהגדרות.</p> : null}
    </Callout>
  );
};
