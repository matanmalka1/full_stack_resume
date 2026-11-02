import { useQuery } from "@tanstack/react-query";
import { Lock, User } from "lucide-react";
import { useId } from "react";

import { meQueryOptions } from "@/api/auth";
import { ChangePasswordForm, SignOutButton } from "@/features/auth";
import { Button } from "@/ui/Button";
import { cx } from "@/ui/cx";
import { Dialog } from "@/ui/Dialog";
import { ListCard, ListRow } from "@/ui/ListCard";
import { cardClasses } from "@/ui/surface";
import { SettingsSection } from "./SettingsSection";

/* Whose Settings these are. The account has an email and no display name, so the email
   is the line the design gives a name. */
const Profile = ({ email, className }: { email: string | undefined; className?: string }) => (
  <div className={cx("flex items-center gap-3.5 p-3.5 lg:p-4", className)}>
    <span
      aria-hidden="true"
      className="flex size-12 shrink-0 items-center justify-center rounded-pill bg-cv-accent text-cv-on-accent lg:size-11"
    >
      <User className="size-icon-lg" />
    </span>
    <p className="min-w-0 flex-1 truncate text-heading-sm font-bold text-cv-text lg:text-body">
      <span dir="ltr">{email}</span>
    </p>
  </div>
);

/* The account's controls in the two shapes the design draws them. A wide screen opens
   Settings on the account: the email, then the password and sign-out commands under it.
   A phone opens on the email alone, as a phone's own settings do, and keeps the two
   commands for a list of their own at the end (`AccountList`). Each shape is hidden at
   the other's width, so a reader meets each command once. */
export const AccountSection = ({ onChangePassword }: { onChangePassword: () => void }) => {
  /* Already read by the session gate this screen renders inside. The query only reads
     that cache (`enabled: false`): the account is a courtesy, not a reason for a request. */
  const me = useQuery({ ...meQueryOptions, enabled: false });
  const email = me.data?.email;

  return (
    <>
      <div className={cardClasses("lg:hidden")}>
        <Profile email={email} />
      </div>
      <SettingsSection className="max-lg:hidden" description="פרטי הכניסה שלך." title="חשבון">
        <div className={cardClasses("overflow-hidden")}>
          <Profile email={email} />
          <div className="flex flex-wrap gap-2 border-t border-cv-hairline px-4 py-3">
            <Button onClick={onChangePassword} size="compact" variant="secondary">
              שינוי סיסמה
            </Button>
            <SignOutButton className="min-h-10 rounded-control-sm border border-cv-border bg-cv-surface px-3.5 text-label font-bold text-cv-text hover:bg-cv-surface-muted [&>svg]:hidden" />
          </div>
        </div>
      </SettingsSection>
    </>
  );
};

/* A phone's account commands, the last group on its Settings. */
export const AccountList = ({ onChangePassword }: { onChangePassword: () => void }) => (
  <SettingsSection className="lg:hidden" divided={false} title="חשבון">
    <ListCard>
      <ListRow icon={Lock} label="שינוי סיסמה" onClick={onChangePassword} />
      <li>
        <SignOutButton className="min-h-13.5 w-full gap-3 px-3.5 text-body font-bold text-cv-text hover:bg-cv-surface-muted [&>svg]:size-4.5" />
      </li>
    </ListCard>
  </SettingsSection>
);

/* Changing the password is a form of its own with its own submit, so it opens over the
   screen rather than among the settings - a sheet on a phone, a dialog on a wide screen. */
export const ChangePasswordDialog = ({ onClose, open }: { onClose: () => void; open: boolean }) => {
  const headingId = useId();

  return (
    <Dialog
      description="שינוי הסיסמה מנתק את כל ההתחברויות האחרות."
      headingId={headingId}
      onClose={onClose}
      open={open}
      title="שינוי סיסמה"
    >
      {/* Mounted only while open, so a reopened dialog starts empty: no typed password
          and no notice from the last change is kept behind a closed dialog. */}
      {open ? <ChangePasswordForm /> : null}
    </Dialog>
  );
};
