import { useCallback, useEffect, useRef, useState } from "react";

import type { ApplicationIntakeFields } from "../model/applicationIntake";

const INTAKE_DRAFT_STORAGE_KEY = "cv-engine:application-intake-draft";
const INTAKE_DRAFT_VERSION = 1;
const AUTOSAVE_DEBOUNCE_MS = 500;

interface StoredIntakeDraft {
  fields: ApplicationIntakeFields;
  savedAt: string;
  version: typeof INTAKE_DRAFT_VERSION;
}

export type IntakeDraftStatus = "idle" | "restored" | "saving" | "saved" | "failed";

const isIntakeFields = (value: unknown): value is ApplicationIntakeFields => {
  if (typeof value !== "object" || value === null) return false;

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.company === "string" &&
    typeof candidate.target_role === "string" &&
    typeof candidate.source_url === "string" &&
    typeof candidate.job_text === "string"
  );
};

const hasContent = (fields: ApplicationIntakeFields): boolean =>
  fields.company !== "" || fields.target_role !== "" || fields.source_url !== "" || fields.job_text !== "";

const fingerprint = (fields: ApplicationIntakeFields): string =>
  JSON.stringify([fields.company, fields.target_role, fields.source_url, fields.job_text]);

/* The intake has no server record until creation succeeds, so browser-local persistence
   is the only crash/refresh recovery available. Unknown or older payloads are ignored;
   they are never allowed to become form values merely because they parse as JSON. */
export const readApplicationIntakeDraft = (): ApplicationIntakeFields | null => {
  try {
    const raw = window.localStorage.getItem(INTAKE_DRAFT_STORAGE_KEY);
    if (raw === null) return null;

    const candidate = JSON.parse(raw) as Partial<StoredIntakeDraft>;
    return candidate.version === INTAKE_DRAFT_VERSION && isIntakeFields(candidate.fields) ? candidate.fields : null;
  } catch {
    return null;
  }
};

const persist = (fields: ApplicationIntakeFields): boolean => {
  try {
    if (!hasContent(fields)) {
      window.localStorage.removeItem(INTAKE_DRAFT_STORAGE_KEY);
      return true;
    }

    const draft: StoredIntakeDraft = {
      fields,
      savedAt: new Date().toISOString(),
      version: INTAKE_DRAFT_VERSION,
    };
    window.localStorage.setItem(INTAKE_DRAFT_STORAGE_KEY, JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
};

/* Debounced during typing, synchronous at the page boundary. The latter closes the gap
   where SPA navigation unmounts the page before the timer fires. Storage is best effort:
   quota/private-mode failures are surfaced but never prevent editing or submission. */
export const useApplicationIntakeDraft = (fields: ApplicationIntakeFields, restored: boolean) => {
  const latestFields = useRef(fields);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const previousFingerprint = useRef(fingerprint(fields));
  const clearedAfterCreation = useRef(false);
  const [status, setStatus] = useState<IntakeDraftStatus>(restored ? "restored" : "idle");
  latestFields.current = fields;

  const clearDraft = useCallback(() => {
    clearedAfterCreation.current = true;
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
    try {
      window.localStorage.removeItem(INTAKE_DRAFT_STORAGE_KEY);
    } catch {
      /* Creation already succeeded; failure to remove a recovery copy must not block navigation. */
    }
    setStatus("idle");
  }, []);

  useEffect(() => {
    const nextFingerprint = fingerprint(fields);
    if (previousFingerprint.current === nextFingerprint) return;
    previousFingerprint.current = nextFingerprint;

    clearedAfterCreation.current = false;
    if (timer.current !== null) clearTimeout(timer.current);

    if (!hasContent(fields)) {
      setStatus(persist(fields) ? "idle" : "failed");
      return;
    }

    setStatus("saving");
    timer.current = setTimeout(() => {
      timer.current = null;
      setStatus(persist(latestFields.current) ? "saved" : "failed");
    }, AUTOSAVE_DEBOUNCE_MS);

    return () => {
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = null;
    };
  }, [fields.company, fields.job_text, fields.source_url, fields.target_role]);

  useEffect(() => {
    const flush = () => {
      if (!clearedAfterCreation.current) persist(latestFields.current);
    };
    const onVisibilityChanged = () => {
      if (document.visibilityState === "hidden" && !clearedAfterCreation.current) {
        setStatus(persist(latestFields.current) ? (hasContent(latestFields.current) ? "saved" : "idle") : "failed");
      }
    };
    const onBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!clearedAfterCreation.current && hasContent(latestFields.current) && !persist(latestFields.current)) {
        event.preventDefault();
      }
    };
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", onBeforeUnload);
    document.addEventListener("visibilitychange", onVisibilityChanged);
    return () => {
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("beforeunload", onBeforeUnload);
      document.removeEventListener("visibilitychange", onVisibilityChanged);
      flush();
    };
  }, []);

  return { clearDraft, status };
};
