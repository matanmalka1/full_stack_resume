import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogIn } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { login, meQueryKey } from "@/api/auth";
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
  const { handleSubmit, register } = useAppForm<LoginRequest>({ defaultValues: { email: "", password: "" } });
  const signIn = useMutation({
    mutationFn: login,
    onSuccess: (me) => {
      queryClient.setQueryData(meQueryKey, me);
      void navigate(safeNextPath(searchParams.get("next")), { replace: true });
    },
  });

  return (
    <main className="page-gutter flex min-h-screen items-center justify-center py-10 text-cv-text">
      <Card className="w-full max-w-md bg-cv-surface p-6 shadow-surface sm:p-8">
        <h1 className="mb-1 flex items-center gap-2 text-heading-md font-bold">
          <LogIn aria-hidden="true" className="size-6 text-cv-accent" />
          התחברות
        </h1>
        <p className="mb-6 text-support text-cv-text-muted">קורות חיים — כניסה לחשבון.</p>
        <form className="flex flex-col gap-4" noValidate onSubmit={handleSubmit((fields) => signIn.mutate(fields))}>
          <Field label="אימייל">
            {(control) => <Input {...control} autoComplete="username" dir="ltr" type="email" {...register("email")} />}
          </Field>
          <Field label="סיסמה">
            {(control) => (
              <Input {...control} autoComplete="current-password" type="password" {...register("password")} />
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
