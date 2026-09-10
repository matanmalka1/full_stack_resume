import type { FactStatus } from "@/api/contracts";
import { Field } from "@/ui/Field";
import { Input } from "@/ui/Input";
import { Select } from "@/ui/Select";
import type { FactFilters } from "../model/factFilters";
import { factSourceLabel, factStatusLabels } from "../model/factLabels";

interface FactPoolFiltersProps {
  filters: FactFilters;
  onChange: (filters: FactFilters) => void;
  sources: string[];
  tags: string[];
}

const statuses: FactStatus[] = ["pending", "confirmed", "canonical"];

export const FactPoolFilters = ({ filters, onChange, sources, tags }: FactPoolFiltersProps) => (
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
    <Field label="חיפוש">
      {(control) => (
        <Input
          {...control}
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
          placeholder="תוכן, מקור או תגית"
          type="search"
          value={filters.query}
        />
      )}
    </Field>
    <Field label="מעמד">
      {(control) => (
        <Select
          {...control}
          onChange={(event) => onChange({ ...filters, status: event.target.value as FactStatus | "all" })}
          value={filters.status}
        >
          <option value="all">כל המעמדות</option>
          {statuses.map((status) => (
            <option key={status} value={status}>
              {factStatusLabels[status]}
            </option>
          ))}
        </Select>
      )}
    </Field>
    <Field label="מאגר מקור">
      {(control) => (
        <Select
          {...control}
          onChange={(event) => onChange({ ...filters, source: event.target.value })}
          value={filters.source}
        >
          <option value="all">כל המאגרים</option>
          {sources.map((source) => (
            <option key={source} value={source}>
              {factSourceLabel(source)}
            </option>
          ))}
        </Select>
      )}
    </Field>
    <Field label="תגית">
      {(control) => (
        <Select
          {...control}
          onChange={(event) => onChange({ ...filters, tag: event.target.value })}
          value={filters.tag}
        >
          <option value="all">כל התגיות</option>
          {tags.map((tag) => (
            <option key={tag} value={tag}>
              {tag}
            </option>
          ))}
        </Select>
      )}
    </Field>
  </div>
);
