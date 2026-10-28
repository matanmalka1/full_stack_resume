import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, FileText, LogIn } from "lucide-react";
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
    <main className="page-gutter flex min-h-screen items-center justify-center py-10 text-cv-text">
      {/* On a phone the screen is an installed app's front door: the app mark the masthead
          leads with, a centred heading, and the form on a rounded card. */}
      <Card className="w-full max-w-md bg-cv-surface p-6 shadow-surface max-lg:rounded-surface max-lg:shadow-floating sm:p-8">
        <span
          aria-hidden="true"
          className="mx-auto mb-4 flex size-16 items-center justify-center rounded-surface bg-cv-accent text-cv-on-accent shadow-floating lg:hidden"
        >
          <FileText className="size-7" />
        </span>
        <h1 className="mb-1 flex items-center gap-2 text-heading-md font-bold max-lg:justify-center">
          <LogIn aria-hidden="true" className="size-6 text-cv-accent max-lg:hidden" />
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
          <Button pending={signIn.isPending} pendingLabel="מתחבר…" size="default" type="submit">
            התחברות
          </Button>
        </form>
      </Card>
    </main>
  );
};
