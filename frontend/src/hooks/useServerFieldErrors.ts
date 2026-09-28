import { useEffect, useMemo } from "react";
import type { FieldPath, FieldValues, UseFormSetError } from "react-hook-form";

import { problemFieldErrors } from "@/ui/errorMessages";

/** A server refusal of specific fields, shown under those fields rather than in a list.

    `fields` maps the API's field name to the form's own, and must be stable (a module
    constant). Each placed refusal becomes a `server` error on its field - the next edit
    that passes the field's own rules clears it - and focus moves to the first one. The
    returned API names go to `ErrorCallout inlineFields`, so the summary does not repeat
    them; a refused field the form does not own stays listed there. */
export const useServerFieldErrors = <T extends FieldValues>(
  error: unknown,
  setError: UseFormSetError<T>,
  fields: Readonly<Partial<Record<string, FieldPath<T>>>>,
): ReadonlySet<string> => {
  const placed = useMemo(
    () => [...problemFieldErrors(error)].filter(([field]) => fields[field] !== undefined),
    [error, fields],
  );

  useEffect(() => {
    placed.forEach(([field, message], index) => {
      const formField = fields[field];
      if (formField !== undefined) setError(formField, { type: "server", message }, { shouldFocus: index === 0 });
    });
  }, [fields, placed, setError]);

  return useMemo(() => new Set(placed.map(([field]) => field)), [placed]);
};
