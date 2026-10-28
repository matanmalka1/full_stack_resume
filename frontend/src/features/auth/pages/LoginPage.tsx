import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, FileText } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { login, meQueryKey, meQueryOptions } from "@/api/auth";
import type { LoginRequest } from "@/api/contracts";
import { useAppForm } from "@/hooks/useAppForm";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { safeNextPath } from "../session";

/* A sheet of a CV drawn in a few bars, beside a blank one tilted behind it: the product
   in one picture, with no real data to go stale. */
const LoginArt = () => (
  <div
    aria-hidden="true"
    className="hidden h-full flex-col items-center justify-center gap-7 overflow-hidden rounded-sheet bg-cv-accent p-14 text-cv-on-accent lg:flex"
  >
    <div className="flex items-end gap-4.5">
      <div className="flex h-62 w-45 -rotate-4 flex-col gap-2 rounded-surface bg-cv-surface px-4 py-4.5 shadow-floating">
        <span className="h-2.5 w-3/5 rounded-control bg-cv-accent" />
        <span className="h-1 w-2/5 rounded-control bg-cv-border-strong" />
        <span className="h-2" />
        <span className="h-1 w-full rounded-control bg-cv-border" />
        <span className="h-1 w-11/12 rounded-control bg-cv-border" />
        <span className="h-1 w-full rounded-control bg-cv-border" />
        <span className="h-1.5" />
        <span className="h-1.5 w-1/3 rounded-control bg-cv-text-muted" />
        <span className="h-1 w-full rounded-control bg-cv-border" />
        <span className="h-1 w-5/6 rounded-control bg-cv-border" />
      </div>
      <div className="h-52 w-37 rotate-5 rounded-surface border border-cv-on-accent/25 bg-cv-on-accent/15" />
    </div>
    <p className="max-w-105 text-heading-md leading-relaxed font-bold">
      קורות חיים מותאמים לכל משרה, מתוך העובדות שאישרת.
    </p>
  </div>
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
    /* A wide screen splits in two: the form on the reader's side, and on the far side a
       dark panel that says what the tool is for. The panel is decoration with one sentence
       in it, so it is hidden from assistive tech and never drawn on a phone. */
    <main className="page-gutter flex min-h-screen items-center justify-center py-10 text-cv-text lg:grid lg:grid-cols-2 lg:p-4">
      {/* On a phone the screen is an installed app's front door: the app mark the masthead
          leads with, a centred heading, and the form on a rounded card. A wide screen
          drops the card: the form stands on the canvas under the mark and its wordmark. */}
      <Card className="w-full max-w-md bg-cv-surface p-6 shadow-surface max-lg:rounded-surface max-lg:shadow-floating sm:p-8 lg:max-w-100 lg:justify-self-center lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
        <div className="flex flex-col items-center lg:mb-7 lg:flex-row lg:gap-3">
          <span
            aria-hidden="true"
            className="mx-auto mb-4 flex size-16 items-center justify-center rounded-surface bg-cv-accent text-cv-on-accent shadow-floating lg:mx-0 lg:mb-0 lg:size-12 lg:shadow-none"
          >
            <FileText className="size-7 lg:size-icon-lg" />
          </span>
          <span className="text-body font-extrabold max-lg:hidden">סביבת קורות החיים</span>
        </div>
        <h1 className="mb-1 flex items-center gap-2 text-heading-md font-bold max-lg:justify-center lg:mb-2 lg:text-heading-lg lg:font-extrabold">
          התחברות
        </h1>
        <p className="mb-6 text-support text-cv-text-muted max-lg:text-center">קורות חיים — כניסה לחשבון.</p>
        <form className="flex flex-col gap-4" noValidate onSubmit={handleSubmit((fields) => signIn.mutate(fields))}>
          <Field label="אימייל">
            {(control) => <Input {...control} autoComplete="username" dir="ltr" type="email" {...register("email")} />}
          </Field>
          <Field label="סיסמה">
            {(control) => (
              <div className="relative">
                <Input
                  {...control}
                  autoComplete="current-password"
                  className="!pe-12"
                  type={passwordShown ? "text" : "password"}
                  {...register("password")}
                />
                <button
                  aria-controls={control.id}
                  aria-label="הצגת התווים שהוקלדו"
                  aria-pressed={passwordShown}
                  className="absolute inset-y-0 end-0 my-auto flex size-11 items-center justify-center rounded-control text-cv-text-muted hover:text-cv-text"
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
            className="lg:mt-1.5 lg:min-h-13 lg:rounded-surface lg:text-body lg:shadow-floating"
            pending={signIn.isPending}
            pendingLabel="מתחבר…"
            size="default"
            type="submit"
          >
            התחברות
          </Button>
        </form>
      </Card>
      <LoginArt />
    </main>
  );
};
