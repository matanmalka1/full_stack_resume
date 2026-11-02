import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, FileText } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { login, meQueryKey, meQueryOptions } from "@/api/auth";
import type { LoginRequest } from "@/api/contracts";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { safeNextPath } from "../session";

/* The design's fields are a little taller than a form's, and on a wide screen they stand
   white on the canvas rather than tinted inside a card. */
const fieldClasses = "!min-h-12.5 lg:!bg-cv-surface";

/* The wide screen's other half: two pages of a CV over the product's one sentence.
   Decorative - the sentence is the product's promise, not something to act on - so the
   whole panel is hidden from assistive tech. */
const LoginIllustration = () => (
  <section
    aria-hidden="true"
    className="m-4 flex flex-1 flex-col justify-center gap-7 overflow-hidden rounded-sheet bg-cv-accent p-14 text-cv-on-accent max-lg:hidden"
  >
    <div className="flex items-end gap-4.5">
      <div className="flex h-62.5 w-45 -rotate-4 flex-col gap-2 rounded-control bg-cv-surface px-4 py-4.5 shadow-fab">
        <span className="h-2.5 w-3/5 rounded-sm bg-cv-accent" />
        <span className="h-1.25 w-2/5 rounded-sm bg-cv-border-strong" />
        <span className="h-2" />
        <span className="h-1 w-full rounded-sm bg-cv-border" />
        <span className="h-1 w-[90%] rounded-sm bg-cv-border" />
        <span className="h-1 w-[95%] rounded-sm bg-cv-border" />
        <span className="h-1.5" />
        <span className="h-1.5 w-[35%] rounded-sm bg-cv-brass" />
        <span className="h-1 w-full rounded-sm bg-cv-border" />
        <span className="h-1 w-[85%] rounded-sm bg-cv-border" />
      </div>
      <div className="h-52.5 w-37.5 rotate-5 rounded-control border border-cv-on-accent/25 bg-cv-on-accent/15" />
    </div>
    <p className="max-w-105 text-heading-md leading-snug font-bold">
      קורות חיים מותאמים לכל משרה, מתוך העובדות שאישרת.
    </p>
  </section>
);

/* The one screen outside the shell. A failed sign-in says the same thing whatever was
   wrong - the server does not say which, and neither does this. */
export const LoginPage = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  /* A password typed on a phone's keyboard is easy to mistype and impossible to check
     while masked, so it can be shown. It starts masked, and showing it is a choice made
     each visit. The toggle's name leaves the field's own word out, so "סיסמה" still
     names one control; `aria-controls` ties it to the field it reveals. */
  const [passwordShown, setPasswordShown] = useState(false);
  const { handleSubmit, register } = useAppForm<LoginRequest>({ defaultValues: { email: "", password: "" } });
  const next = safeNextPath(searchParams.get("next"));
  /* Already signed in - a bookmarked or back-button visit - there is nothing to sign in to. */
  const me = useQuery(meQueryOptions);
  const signIn = useMutation({
    mutationFn: login,
    onSuccess: (signedIn) => {
      queryClient.setQueryData(meQueryKey, signedIn);
      void navigate(next, { replace: true });
    },
  });

  if (me.data) return <Navigate replace to={next} />;

  return (
    <main className="flex min-h-screen text-cv-text">
      {/* On a phone the screen is an installed app's front door: the app mark, the
          product's name over a centred heading, and the form on a rounded card. A wide
          screen sets the mark beside the name and the form straight on the canvas, with
          the illustration as the other half. */}
      <section className="flex flex-1 flex-col items-center justify-center p-6 lg:p-12">
        <div className="flex w-full max-w-100 flex-col gap-8 lg:gap-7">
          <div className="flex flex-col items-center gap-3.5 text-center lg:items-start lg:text-start">
            <div className="flex flex-col items-center gap-3.5 lg:flex-row lg:gap-3">
              <span
                aria-hidden="true"
                className="flex size-16 items-center justify-center rounded-fab bg-cv-accent text-cv-on-accent shadow-fab lg:size-12 lg:rounded-control-lg lg:shadow-none"
              >
                <FileText className="size-7.5 lg:size-6" />
              </span>
              <p className="text-label font-bold text-cv-text-muted lg:text-heading-sm lg:font-extrabold lg:text-cv-text">
                סביבת קורות החיים
              </p>
            </div>
            <h1 className="-mt-2.5 text-title font-extrabold tracking-tight lg:mt-3 lg:text-[2.125rem] lg:leading-tight">
              כניסה לחשבון
            </h1>
          </div>
          <form
            className="flex flex-col gap-3.5 rounded-dialog border border-cv-hairline bg-cv-surface p-4.5 shadow-surface lg:gap-4 lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none"
            noValidate
            onSubmit={handleSubmit((fields) => signIn.mutate(fields))}
          >
            <Field label="אימייל">
              {(control) => (
                <Input
                  {...control}
                  autoComplete="username"
                  className={fieldClasses}
                  dir="ltr"
                  type="email"
                  {...register("email")}
                />
              )}
            </Field>
            <Field label="סיסמה">
              {(control) => (
                <div className="relative">
                  <Input
                    {...control}
                    autoComplete="current-password"
                    className={`${fieldClasses} !pe-13`}
                    type={passwordShown ? "text" : "password"}
                    {...register("password")}
                  />
                  <button
                    aria-controls={control.id}
                    aria-label="הצגת התווים שהוקלדו"
                    aria-pressed={passwordShown}
                    className="absolute inset-y-0 end-0.75 my-auto flex size-11 items-center justify-center rounded-control-sm text-cv-text-muted hover:text-cv-text"
                    onClick={() => setPasswordShown((shown) => !shown)}
                    type="button"
                  >
                    {passwordShown ? (
                      <EyeOff aria-hidden="true" className="size-icon-lg" />
                    ) : (
                      <Eye aria-hidden="true" className="size-icon-lg" />
                    )}
                  </button>
                </div>
              )}
            </Field>
            {signIn.error === null ? null : <ErrorCallout error={signIn.error} title="ההתחברות נכשלה" />}
            <Button
              className="mt-1.5 shadow-action"
              pending={signIn.isPending}
              pendingLabel="נכנס…"
              size="large"
              type="submit"
            >
              כניסה
            </Button>
          </form>
        </div>
      </section>
      <LoginIllustration />
    </main>
  );
};
