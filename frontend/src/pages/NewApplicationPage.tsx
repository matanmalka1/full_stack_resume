import { Briefcase, Building2, FileCheck2, FileText, Link2, Sparkles, type LucideIcon } from "lucide-react";
import { type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { JOB_TEXT_MAX_BYTES } from "../api/applications";
import { ErrorCallout } from "../app/ErrorCallout";
import { useWorkflowStage } from "../app/WorkflowLandmark";
import { appRoutes } from "../app/appRoutes";
import { ActionBar } from "../ui/ActionBar";
import { Breadcrumbs } from "../ui/Breadcrumbs";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Field } from "../ui/Field";
import { FormSection } from "../ui/FormSection";
import { LtrText } from "../ui/LtrText";
import { PageShell } from "../ui/PageShell";
import { TextArea, TextInput } from "../ui/TextInput";
import { surfaceClasses } from "../ui/Surface";
import { cx } from "../ui/cx";
import { formatBytes } from "../ui/formatBytes";
import { JobTextFileField } from "./application/JobTextFileField";
import { LABEL_MAX_CHARACTERS, SOURCE_URL_MAX_CHARACTERS } from "./application/applicationInput";
import { paramsFromQuery, queryFromParams } from "./applicationListParams";
import { DuplicateChoices } from "./new-application/DuplicateChoices";
import { useApplicationIntake } from "./new-application/useApplicationIntake";

/* The snapshot limit the server enforces is a byte budget, not a character count, so the
   counter measures the same thing the refusal will. It stays a quiet character count
   until the text is close enough to the ceiling for the budget to be the useful fact. */
const JOB_TEXT_BUDGET_NOTICE_RATIO = 0.8;

/* A placeholder cannot wrap its LTR example in a <bdi> element. Unicode isolates give
   the English example the same boundary without letting it reorder the Hebrew prefix
   or its colon. */
const examplePlaceholder = (example: string) => `לדוגמה: \u2066${example}\u2069`;

const SectionTitle = ({ icon: Icon, children }: { children: string; icon: LucideIcon }) => (
  <span className="inline-flex items-center gap-2">
    <Icon aria-hidden="true" className="size-4 text-cv-accent" />
    {children}
  </span>
);

const IconField = ({ children, icon: Icon }: { children: ReactNode; icon: LucideIcon }) => (
  <span className="relative block">
    <Icon
      aria-hidden="true"
      className="pointer-events-none absolute start-3.5 top-1/2 z-10 size-4 -translate-y-1/2 text-cv-text-muted"
    />
    {children}
  </span>
);

export const NewApplicationPage = () => {
  const navigate = useNavigate();
  /* The board hands its own narrowing over in this screen's address bar, so the way back
     returns to the board the user actually left rather than to an unfiltered one. It is
     read back through the board's own parser, so an arbitrary value in the URL cannot
     become an arbitrary link. */
  const [boardParams] = useSearchParams();
  const boardSearch = paramsFromQuery(queryFromParams(boardParams)).toString();
  const boardPath = boardSearch === "" ? appRoutes.home : `${appRoutes.home}?${boardSearch}`;
  /* Intake creates the job the CV workflow later acts on; it is not a stage of that
     workflow, so this screen reports none rather than claiming step 1. */
  useWorkflowStage("none");
  const { answeredIntake, duplicates, failure, form, runSubmit, staleAnswer, submit } = useApplicationIntake({
    onCreated: (result) => {
      void navigate(appRoutes.application(result.applicationId), {
        state: {
          createdApplication: {
            analysisProblem: result.analysisProblem,
            analysisQueued: result.analysisQueued,
          },
        },
        replace: true,
      });
    },
  });
  const {
    formState: { errors },
    register,
    setValue,
    watch,
  } = form;

  /* The snapshot is written exactly as entered, so its size is worth showing while it is
     still editable. Subscribing to this one field keeps the counter live without making
     the whole form controlled. */
  const jobText = watch("job_text");
  const jobTextLength = jobText.length;
  /* Measured only once the text is long enough to be worth measuring: encoding every
     keystroke of a short paste to report a fraction of a percent is work for nothing. */
  const jobTextBytes =
    jobTextLength * 4 < JOB_TEXT_MAX_BYTES * JOB_TEXT_BUDGET_NOTICE_RATIO
      ? null
      : new TextEncoder().encode(jobText).length;
  const jobTextNearBudget = jobTextBytes !== null && jobTextBytes >= JOB_TEXT_MAX_BYTES * JOB_TEXT_BUDGET_NOTICE_RATIO;
  const jobTextOverBudget = jobTextBytes !== null && jobTextBytes > JOB_TEXT_MAX_BYTES;

  return (
    <PageShell
      description="הזנת פרטי המשרה יוצרת תצלום מקור קבוע ומתחילה ניתוח התאמה מול העובדות הקנוניות."
      measure="form"
      navigation={
        <Breadcrumbs
          items={[
            { label: "מועמדויות", to: boardPath },
            { label: "משרה חדשה" },
          ]}
        />
      }
      title="קליטת משרה חדשה"
    >
      <form
        className={surfaceClasses("flex flex-col gap-6 bg-cv-surface p-5 shadow-surface sm:p-7")}
        noValidate
        onSubmit={runSubmit(undefined)}
      >
        <FormSection divided={false} title={<SectionTitle icon={Briefcase}>פרטי המשרה</SectionTitle>}>
          <div className="grid gap-4 md:grid-cols-2">
            <Field error={errors.company?.message} label="שם החברה">
              {(control) => (
                <IconField icon={Building2}>
                  <TextInput
                    {...control}
                    {...register("company", {
                      validate: (value) => value.trim() !== "" || "יש להזין את שם החברה.",
                    })}
                    autoComplete="organization"
                    className="rtl-placeholder ps-10"
                    dir="auto"
                    maxLength={LABEL_MAX_CHARACTERS}
                    placeholder={examplePlaceholder("Stripe")}
                  />
                </IconField>
              )}
            </Field>

            <Field error={errors.target_role?.message} label="תפקיד היעד">
              {(control) => (
                <IconField icon={Briefcase}>
                  <TextInput
                    {...control}
                    {...register("target_role", {
                      validate: (value) => value.trim() !== "" || "יש להזין את תפקיד היעד.",
                    })}
                    className="rtl-placeholder ps-10"
                    dir="auto"
                    maxLength={LABEL_MAX_CHARACTERS}
                    placeholder={examplePlaceholder("Senior Solutions Architect")}
                  />
                </IconField>
              )}
            </Field>
          </div>

          <Field
            hint="נשמרת כתיעוד מקור בלבד, המערכת אינה פותחת את הכתובת או מייבאת ממנה טקסט."
            label="כתובת המשרה"
            optional
          >
            {(control) => (
              /* A.3: a URL is an LTR island even inside the RTL shell. */
              <IconField icon={Link2}>
                <TextInput
                  {...control}
                  {...register("source_url")}
                  className="ltr-island ps-10"
                  dir="ltr"
                  inputMode="url"
                  maxLength={SOURCE_URL_MAX_CHARACTERS}
                  placeholder="https://company.example/careers/job"
                  type="url"
                />
              </IconField>
            )}
          </Field>
        </FormSection>

        <FormSection
          aside={
            /* Kept in the header at every length: appearing with the first keystroke
               reflowed the title row while the user was typing into it. */
            jobTextLength === 0 ? (
              <span aria-hidden="true" className="invisible">
                0
              </span>
            ) : jobTextNearBudget ? (
              /* Close to the ceiling the byte budget is the fact that matters, so the
                 counter switches to it and says which side of the limit the text is on
                 before the server has to. */
              <span className={cx("font-medium", jobTextOverBudget ? "text-cv-blocker" : "text-cv-warning")}>
                <LtrText>
                  {formatBytes(jobTextBytes ?? 0)} / {formatBytes(JOB_TEXT_MAX_BYTES)}
                </LtrText>{" "}
                {jobTextOverBudget ? "— חורג מגודל התצלום המותר" : "מגודל התצלום המותר"}
              </span>
            ) : (
              <span>
                <LtrText>{jobTextLength.toLocaleString("en-US")}</LtrText> תווים
              </span>
            )
          }
          /* Said once. How the text gets in is the file row's own sentence and the
             text area's placeholder; what this group needs to say is what happens to
             the text afterwards. */
          description="הטקסט יישמר בתצלום המשרה בדיוק כפי שהוזן."
          divided={false}
          title={<SectionTitle icon={FileText}>תיאור המשרה</SectionTitle>}
        >
          <JobTextFileField
            onText={(text) => setValue("job_text", text, { shouldDirty: true, shouldValidate: true })}
          />

          <Field error={errors.job_text?.message} label="טקסט המשרה">
            {(control) => (
              /* Mixed Hebrew/English job text picks its own direction (A.3). */
              <TextArea
                {...control}
                {...register("job_text", {
                  validate: {
                    required: (value) => value.trim() !== "" || "יש להזין את טקסט המשרה.",
                    withinBudget: (value) =>
                      new TextEncoder().encode(value).length <= JOB_TEXT_MAX_BYTES ||
                      "טקסט המשרה חורג מהגודל המותר. יש לקצר אותו לפני יצירת המועמדות.",
                  },
                })}
                /* A long paste scrolls inside the field instead of moving the form's
                   actions below the fold. The user can still resize it when useful. */
                className="rtl-placeholder h-64 max-h-[55vh]"
                dir="auto"
                placeholder="הדבק כאן את תיאור המשרה…"
              />
            )}
          </Field>
        </FormSection>

        {duplicates === null ? null : (
          <DuplicateChoices
            matches={duplicates}
            onCreateAnyway={() => {
              void runSubmit(answeredIntake)();
            }}
            pending={submit.isPending}
          />
        )}

        {staleAnswer ? (
          <Callout role="status" title="הקלט השתנה מאז הבדיקה" tone="neutral">
            בדיקת הכפילויות רצה על טקסט קודם, ולכן התשובה שלה אינה חלה על מה שמופיע עכשיו. יש ללחוץ שוב על יצירת מועמדות
            כדי לבדוק את הקלט הנוכחי.
          </Callout>
        ) : null}

        {failure === null ? null : (
          <ErrorCallout
            error={failure}
            fallbackDetail="הפנייה לשרת נכשלה. מה שהוזן נשמר בטופס וניתן לנסות שוב."
            fallbackTitle="יצירת המועמדות נכשלה"
          />
        )}

        {/* The action does three things and named one of them. What follows the click is
            worth knowing before it, not after the navigation. */}
        <div className="flex items-start gap-2 rounded-control border border-cv-success/25 bg-cv-success-soft p-3 text-support text-cv-text">
          <FileCheck2 aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-cv-success" />
          <p>יצירת המועמדות שומרת את הטקסט בדיוק כפי שהוזן בתצלום משרה קבוע, ואז מתחילה את ניתוח ההתאמה.</p>
        </div>

        {/* Once duplicate choices are current, the callout owns the only creation
            action. Keeping this generic submit beside the explicit override would make
            two visually competing actions appear to create the same record. */}
        {duplicates === null ? (
          <ActionBar
            align="start"
            primary={
              <Button
                disabled={jobTextOverBudget || (submit.isPending && submit.variables?.acknowledged === true)}
                pending={submit.isPending && submit.variables?.acknowledged !== true}
                pendingLabel="בודק כפילויות…"
                type="submit"
              >
                <Sparkles aria-hidden="true" className="size-4" />
                יצירת מועמדות
              </Button>
            }
          />
        ) : null}
      </form>
    </PageShell>
  );
};
