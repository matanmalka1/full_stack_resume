import { useEffect, useRef, useState } from "react";

interface ServerSyncedFieldOptions {
  changeToken?: string;
  isDirty: boolean;
  localValue: string;
  onSync: (value: string) => void;
  serverValue: string;
}

/* A server-backed form field has two owners at different times: the projection supplies
   its clean value, and the user owns it from the first edit until their value is accepted.
   Polling may update the projection in between. Keep dirty text intact and remember that
   the server moved so the host can make that divergence visible instead of silently
   choosing either side. */
export const useServerSyncedField = ({
  changeToken,
  isDirty,
  localValue,
  onSync,
  serverValue,
}: ServerSyncedFieldOptions): boolean => {
  const serverVersion = changeToken ?? serverValue;
  const previousServerVersion = useRef(serverVersion);
  const sync = useRef(onSync);
  const [serverChangedWhileDirty, setServerChangedWhileDirty] = useState(false);

  useEffect(() => {
    sync.current = onSync;
  }, [onSync]);

  useEffect(() => {
    const serverChanged = previousServerVersion.current !== serverVersion;
    previousServerVersion.current = serverVersion;

    if (!isDirty || localValue === serverValue) {
      if (isDirty || localValue !== serverValue) {
        sync.current(serverValue);
      }
      setServerChangedWhileDirty(false);
      return;
    }

    if (serverChanged) {
      setServerChangedWhileDirty(true);
    }
  }, [isDirty, localValue, serverValue, serverVersion]);

  return serverChangedWhileDirty && isDirty && localValue !== serverValue;
};
