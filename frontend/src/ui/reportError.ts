import { problemDetailsFrom } from "./errorMessages";

/** Where technical failure detail goes instead of the page.

    What the reader sees is the Hebrew catalogue in `errorMessages`; what a developer
    needs - the problem code, HTTP status, the server's own detail and context, or a
    local exception's message and stack - is written here. An API refusal the reader can
    act on is a warning; anything else is an error. */
export const reportError = (scope: string, error: unknown): void => {
  const problem = problemDetailsFrom(error);
  if (problem !== null) {
    const expected = problem.status > 0 && problem.status < 500;
    // Diagnostics for a failure whose user-facing copy hides the server's prose.
    // oxlint-disable-next-line no-console
    (expected ? console.warn : console.error)(scope, {
      code: problem.code,
      status: problem.status,
      detail: problem.detail,
      ...(problem.context === undefined ? {} : { context: problem.context }),
      ...(problem.instance === undefined ? {} : { instance: problem.instance }),
    });
    return;
  }

  const context =
    error instanceof Error
      ? { name: error.name, message: error.message, ...(import.meta.env.DEV ? { stack: error.stack } : {}) }
      : { value: error };
  // oxlint-disable-next-line no-console
  console.error(scope, context);
};
