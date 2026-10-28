import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { logout } from "@/api/auth";
import { routePaths } from "@/navigation/routePaths";
import { buttonClasses } from "@/ui/Button";
import { Tooltip } from "@/ui/Tooltip";
import { clearSignedInBrowserState } from "../session";

/* Ends this session and leaves nothing of the reader in the browser. A sign-out the
   server could not record still clears the browser: the reader asked to leave. */
/* `wideButton` draws it, from the large breakpoint, as a bordered button of its own width -
   the settings page's account card sets it beside "שינוי סיסמה" there - where the sidebar's
   full-width ghost row is the default. A phone draws the ghost row either way. */
export const SignOutButton = ({ compact = false, wideButton = false }: { compact?: boolean; wideButton?: boolean }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const signOut = useMutation({
    mutationFn: logout,
    onSettled: () => {
      clearSignedInBrowserState(queryClient);
      void navigate(routePaths.login(), { replace: true });
    },
  });
  const button = (
    <button
      aria-label="התנתקות"
      className={buttonClasses(
        "ghost",
        compact
          ? undefined
          : wideButton
            ? "lg:border lg:border-cv-border lg:bg-cv-surface lg:text-cv-text lg:hover:border-cv-border-strong lg:hover:bg-cv-surface-muted"
            : "lg:w-full",
        compact ? "icon" : "default",
      )}
      disabled={signOut.isPending}
      onClick={() => signOut.mutate()}
      type="button"
    >
      <LogOut aria-hidden="true" className="size-icon-md" />
      {compact ? null : <span>התנתקות</span>}
    </button>
  );

  return compact ? (
    <Tooltip label="התנתקות" placement="rail">
      {button}
    </Tooltip>
  ) : (
    button
  );
};
