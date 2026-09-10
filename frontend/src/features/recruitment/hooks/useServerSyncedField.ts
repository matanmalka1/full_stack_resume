import { useEffect, useRef, useState } from "react";

interface ServerSyncedFieldOptions {
  changeToken?: string;
  isDirty: boolean;
  localValue: string;
  onSync: (value: string) => void;
  serverValue: string;
}

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
      if (isDirty || localValue !== serverValue) sync.current(serverValue);
      // This hook intentionally reconciles local form state with a new server version.
      // oxlint-disable-next-line react/set-state-in-effect
      setServerChangedWhileDirty(false);
      return;
    }

    if (serverChanged) {
      // Preserve a dirty local value while surfacing that the server changed underneath it.
      // oxlint-disable-next-line react/set-state-in-effect
      setServerChangedWhileDirty(true);
    }
  }, [isDirty, localValue, serverValue, serverVersion]);

  return serverChangedWhileDirty && isDirty && localValue !== serverValue;
};
