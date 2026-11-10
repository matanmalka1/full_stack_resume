import { createContext, useContext } from "react";

/* The trailing corner of the phone's top bar, as the app header mounts it. A page whose
   title the bar already shows (`PageShell`'s `titleInPhoneBar`) draws its commands there.
   Null outside the app layout and until the header has mounted. */
export const PhoneBarSlotContext = createContext<HTMLElement | null>(null);

export const usePhoneBarSlot = (): HTMLElement | null => useContext(PhoneBarSlotContext);
