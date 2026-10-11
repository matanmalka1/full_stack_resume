/* The auth feature's public surface: the gate every signed-in screen renders inside, the
   shell's sign-out control, the settings screen's password form, and what the app runs
   when the server reports the session gone. The sign-in screen is reached through the
   router. */
export { ChangePasswordForm } from "./components/ChangePasswordForm";
export { SessionGate } from "./components/SessionGate";
export { SignOutButton } from "./components/SignOutButton";
export { safeNextPath } from "./session";
