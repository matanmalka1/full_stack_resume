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

interface ChangePasswordFields extends ChangePasswordRequest {
  repeat_password: string;
}

/* Changing the password ends every other session; this one continues on a new cookie. */
export const ChangePasswordForm = () => {
  const [changed, setChanged] = useState(false);
  /* The new password is typed twice: a typo here would lock the reader out of every
     session at once. The repeat stays in the form; only the request's fields are sent. */
  const {
    formState: { errors },
    handleSubmit,
    register,
    reset,
  } = useAppForm<ChangePasswordFields>({
    defaultValues: { current_password: "", new_password: "", repeat_password: "" },
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
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={handleSubmit(({ current_password, new_password }) => change.mutate({ current_password, new_password }))}
    >
      <Field label="סיסמה נוכחית">
        {(control) => (
          <Input {...control} autoComplete="current-password" type="password" {...register("current_password")} />
        )}
      </Field>
      <Field hint="12 עד 256 תווים." label="סיסמה חדשה">
        {(control) => <Input {...control} autoComplete="new-password" type="password" {...register("new_password")} />}
      </Field>
      <Field error={errors.repeat_password?.message} label="סיסמה חדשה שוב">
        {(control) => (
          <Input
            {...control}
            autoComplete="new-password"
            type="password"
            {...register("repeat_password", {
              validate: (value, fields) => value === fields.new_password || "הסיסמאות אינן זהות.",
            })}
          />
        )}
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
