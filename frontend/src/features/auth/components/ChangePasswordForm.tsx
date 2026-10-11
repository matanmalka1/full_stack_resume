import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

import { changePassword } from "@/api/auth";
import type { ChangePasswordRequest } from "@/api/contracts";
import { useAppForm } from "@/hooks/useAppForm";
import { ActionBar } from "@/ui/ActionBar";
import { Button } from "@/ui/Button";
import { ErrorCallout } from "@/ui/ErrorCallout";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { SuccessNotice } from "@/ui/SuccessNotice";

/* Changing the password ends every other session; this one continues on a new cookie. */
export const ChangePasswordForm = () => {
  const [changed, setChanged] = useState(false);
  const { handleSubmit, register, reset } = useAppForm<ChangePasswordRequest>({
    defaultValues: { current_password: "", new_password: "" },
  });
  const change = useMutation({
    mutationFn: changePassword,
    onMutate: () => setChanged(false),
    onSuccess: () => {
      reset();
      setChanged(true);
    },
  });

  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={handleSubmit((fields) => change.mutate(fields))}>
      <Field label="סיסמה נוכחית">
        {(control) => (
          <Input {...control} autoComplete="current-password" type="password" {...register("current_password")} />
        )}
      </Field>
      <Field hint="12 עד 256 תווים." label="סיסמה חדשה">
        {(control) => <Input {...control} autoComplete="new-password" type="password" {...register("new_password")} />}
      </Field>
      {change.error === null ? null : <ErrorCallout error={change.error} title="הסיסמה לא שונתה" />}
      {changed ? (
        <SuccessNotice onDismiss={() => setChanged(false)} title="הסיסמה שונתה">
          <p>כל ההתחברויות האחרות הסתיימו.</p>
        </SuccessNotice>
      ) : null}
      <ActionBar
        primary={
          <Button pending={change.isPending} pendingLabel="משנה…" type="submit">
            שינוי סיסמה
          </Button>
        }
      />
    </form>
  );
};
