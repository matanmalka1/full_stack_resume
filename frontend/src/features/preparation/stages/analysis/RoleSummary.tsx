/* The posting's own summary. Extracted keywords are not listed: the requirements below
   carry what the posting asks for, and a chip row beside them offered nothing to act on. */
export const RoleSummary = ({ summary }: { summary: string | null }) =>
  summary === null ? null : (
    <section aria-labelledby="role-summary-heading" className="flex flex-col gap-3">
      <h3 className="text-body font-semibold text-cv-text" id="role-summary-heading">
        מה המשרה מחפשת
      </h3>
      <p className="text-body leading-7 text-cv-text" dir="auto">
        {summary}
      </p>
    </section>
  );
