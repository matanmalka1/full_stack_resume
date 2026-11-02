import type { ReactNode } from "react";

export interface Toast {
  body?: ReactNode;
  id: number;
  title: string;
}

/* The one shape of a success message, and the bar for having one at all.

   A command earns a toast only when the reader learns something the screen does not
   already show: a consequence ("the analysis is no longer current"), a record that now
   exists elsewhere, or a result that has no other place on the page. A command whose
   effect is visible where it happened - a row that changed, a button that became
   disabled - says nothing.

   It is shown after the server confirmed, never optimistically. The store lives outside
   React so a mutation's onSuccess can raise one without threading state through the
   screen; `<Toaster>` is the only reader. */
let toasts: readonly Toast[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

const emit = () => {
  for (const listener of listeners) listener();
};

/* Three at most: a fourth success while three are still showing pushes the oldest out. */
const MAX_TOASTS = 3;

export const showToast = (toast: Omit<Toast, "id">) => {
  toasts = [...toasts, { ...toast, id: nextId++ }].slice(-MAX_TOASTS);
  emit();
};

export const dismissToast = (id: number) => {
  toasts = toasts.filter((toast) => toast.id !== id);
  emit();
};

export const subscribeToasts = (listener: () => void) => {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
};

export const getToasts = () => toasts;

export const clearToasts = () => {
  toasts = [];
  emit();
};
