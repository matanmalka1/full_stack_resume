/* A list of short backend-authored strings - keywords, requirements. Each picks its own
   direction: the analysis may be of an English posting while the shell is Hebrew, and a
   Hebrew-forced English requirement reads backwards. */
export const TermList = ({ items }: { items: string[] }) => (
  <ul className="flex flex-wrap gap-2">
    {items.map((item) => (
      /* Output, not a control. The bordered pill is the shape the list filters use for
         things you can select, so these carry a flat tinted ground instead: same family,
         visibly not clickable. */
      <li
        className="rounded-control bg-cv-surface-muted px-2.5 py-1 text-support text-cv-text-muted"
        dir="auto"
        key={item}
      >
        {item}
      </li>
    ))}
  </ul>
);
