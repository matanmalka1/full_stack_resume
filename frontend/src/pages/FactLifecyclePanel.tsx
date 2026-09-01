import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import type { CreateFactRequest, Fact, FactStatus } from "../api/contracts";
import {
  attachFact,
  createPendingFact,
  factDetailQueryKey,
  factDetailQueryOptions,
  factsQueryPrefix,
  factsQueryOptions,
  transitionFact,
} from "../api/facts";
import { ErrorCallout } from "../app/ErrorCallout";
import { Button } from "../ui/Button";
import { Callout } from "../ui/Callout";
import { Checkbox } from "../ui/Checkbox";
import { Field } from "../ui/Field";
import { Select } from "../ui/Select";
import { TextArea, TextInput } from "../ui/TextInput";

type FactSource = CreateFactRequest["source"];
type FactStyle = CreateFactRequest["resume_style"];

const sourceLabels: Record<FactSource, string> = {
  "common.md": "עובדות משותפות",
  "sales.md": "ניסיון במכירות",
  "development.md": "ניסיון בפיתוח",
  "situational_skills.md": "כישורים מצביים",
};

const styleLabels: Record<FactStyle, string> = {
  bullet: "שורת ניסיון",
  item: "פריט",
  paragraph: "פסקה",
  heading: "כותרת",
  date: "תאריך",
  contact: "פרט קשר",
};

const statusLabels: Record<FactStatus, string> = {
  pending: "ממתינה",
  confirmed: "אושרה",
  canonical: "מקור אמת",
};

const factLabel = (fact: Fact): string => fact.renderings.he ?? fact.renderings.en ?? fact.meaning;

export const FactLifecyclePanel = ({
  profile,
  sections,
}: {
  profile: string | null;
  sections: string[];
}) => {
  const queryClient = useQueryClient();
  const factsQuery = useQuery(factsQueryOptions());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  useEffect(() => {
    if (selectedId === null && (factsQuery.data?.items.length ?? 0) > 0) {
      setSelectedId(factsQuery.data?.items[0]?.fact.fact_id ?? null);
    }
  }, [factsQuery.data, selectedId]);
  const detailQuery = useQuery({
    ...factDetailQueryOptions(selectedId ?? ""),
    enabled: selectedId !== null,
  });
  const [explicitlyConfirmed, setExplicitlyConfirmed] = useState(false);
  const [section, setSection] = useState(sections[0] ?? "");
  const [pin, setPin] = useState(false);
  const [source, setSource] = useState<FactSource>(
    profile === "development" ? "development.md" : "sales.md",
  );
  const [meaning, setMeaning] = useState("");
  const [english, setEnglish] = useState("");
  const [hebrew, setHebrew] = useState("");
  const [tags, setTags] = useState("");
  const [provenance, setProvenance] = useState("");
  const [style, setStyle] = useState<FactStyle>("bullet");

  const refresh = (factId?: string) => {
    void queryClient.invalidateQueries({ queryKey: factsQueryPrefix });
    if (factId !== undefined) {
      void queryClient.invalidateQueries({ queryKey: factDetailQueryKey(factId) });
    }
  };
  const create = useMutation({
    mutationFn: () =>
      createPendingFact({
        source,
        meaning: meaning.trim(),
        renderings: {
          en: english.trim(),
          ...(hebrew.trim() === "" ? {} : { he: hebrew.trim() }),
        },
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        provenance: provenance.trim(),
        resume_style: style,
        reason: "created from the contextual draft fact panel",
      }),
    onSuccess: (result) => {
      setSelectedId(result.fact.fact_id);
      setMeaning("");
      setEnglish("");
      setHebrew("");
      setTags("");
      setProvenance("");
      refresh(result.fact.fact_id);
    },
  });
  const transition = useMutation({
    mutationFn: (command: "confirm" | "promote") => {
      if (selectedId === null) throw new Error("No fact selected");
      return transitionFact(selectedId, command, {
        confirm: true,
        reason: command === "confirm" ? "explicit Web confirmation" : "explicit Web promotion",
      });
    },
    onSuccess: (result) => {
      setExplicitlyConfirmed(false);
      refresh(result.fact.fact_id);
    },
  });
  const attachment = useMutation({
    mutationFn: () => {
      if (selectedId === null || profile === null || section === "") {
        throw new Error("Attachment requires a fact, Profile, and section");
      }
      return attachFact(selectedId, { profile, section, pin });
    },
    onSuccess: (result) => refresh(result.fact.fact_id),
  });
  const error = factsQuery.error ?? detailQuery.error ?? create.error ?? transition.error ?? attachment.error;
  const tagsPresent = tags.split(",").some((tag) => tag.trim() !== "");
  const canCreate =
    meaning.trim() !== "" && english.trim() !== "" && provenance.trim() !== "" && tagsPresent;
  const selected = detailQuery.data?.fact;

  return (
    <section aria-labelledby="fact-lifecycle-heading" className="rounded-surface border border-cv-border bg-cv-surface-muted p-4 sm:p-5">
      <h2 className="text-heading-sm font-bold text-cv-text" id="fact-lifecycle-heading">
        מחזור חיי העובדות
      </h2>
      <p className="mt-2 text-support text-cv-text-muted">
        העובדות מוצגות בהקשר של הטיוטה. יצירה וקידום כאן משנים את מקור הידע הקבוע.
      </p>
      {error === null ? null : (
        <ErrorCallout
          className="mt-4"
          error={error}
          fallbackDetail="מקור הידע לא השתנה ואפשר לנסות שוב."
          fallbackTitle="לא ניתן לעדכן את העובדה"
        />
      )}

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Field label="עובדה להצגה">
          {(control) => (
            <Select
              {...control}
              onChange={(event) => {
                setSelectedId(event.target.value || null);
                setExplicitlyConfirmed(false);
              }}
              value={selectedId ?? ""}
            >
              {(factsQuery.data?.items.length ?? 0) === 0 ? (
                <option value="">אין עדיין עובדות</option>
              ) : null}
              {factsQuery.data?.items.map(({ fact }) => (
                <option key={fact.fact_id} value={fact.fact_id}>
                  {factLabel(fact)} · {statusLabels[fact.status]}
                </option>
              ))}
            </Select>
          )}
        </Field>
        {selected === undefined ? null : (
          <div className="rounded-control border border-cv-border bg-cv-surface p-4">
            <p className="font-semibold text-cv-text" dir="auto">{factLabel(selected)}</p>
            <p className="mt-1 text-support text-cv-text-muted">{statusLabels[selected.status]}</p>
            <p className="mt-2 text-support text-cv-text-muted" dir="auto">{selected.meaning}</p>
          </div>
        )}
      </div>

      {detailQuery.data === undefined ? null : (
        <div className="mt-4 flex flex-col gap-3">
          <h3 className="font-semibold text-cv-text">היסטוריית העובדה</h3>
          <ol className="flex flex-col gap-2">
            {detailQuery.data.events.map((event) => (
              <li className="border-s-2 border-cv-border ps-3 text-support text-cv-text-muted" key={event.id}>
                {event.from_status == null
                  ? "נוצרה כממתינה"
                  : `${statusLabels[event.from_status as FactStatus] ?? event.from_status} ← ${statusLabels[event.to_status as FactStatus] ?? event.to_status}`}
                {event.reason === "" ? "" : ` · ${event.reason}`}
              </li>
            ))}
          </ol>
          {selected?.status === "pending" || selected?.status === "confirmed" ? (
            <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
              <Checkbox checked={explicitlyConfirmed} onChange={(event) => setExplicitlyConfirmed(event.currentTarget.checked)}>
                בדקתי את תוכן העובדה והמקור ואני מאשר את שינוי המעמד
              </Checkbox>
              <Button
                disabled={!explicitlyConfirmed}
                onClick={() => transition.mutate(selected.status === "pending" ? "confirm" : "promote")}
                pending={transition.isPending}
              >
                {selected.status === "pending" ? "אישור העובדה" : "קידום למקור אמת"}
              </Button>
            </div>
          ) : null}
          {selected?.status !== "canonical" ? null : profile === null || sections.length === 0 ? (
            <Callout title="אין יעד צירוף בהקשר הנוכחי" tone="neutral">
              נדרש פרופיל פעיל וסעיף בטיוטה כדי לצרף את העובדה.
            </Callout>
          ) : (
            <div className="flex flex-col gap-3 rounded-control border border-cv-border bg-cv-surface p-4">
              <Field label="סעיף בפרופיל הפעיל">
                {(control) => (
                  <Select {...control} onChange={(event) => setSection(event.target.value)} value={section}>
                    {sections.map((name) => <option key={name} value={name}>{name}</option>)}
                  </Select>
                )}
              </Field>
              <Checkbox checked={pin} onChange={(event) => setPin(event.currentTarget.checked)}>
                קיבוע העובדה בתוכנית הבחירה הבאה
              </Checkbox>
              <Button onClick={() => attachment.mutate()} pending={attachment.isPending}>
                צירוף העובדה לסעיף
              </Button>
              {attachment.isSuccess ? (
                <Callout role="status" title="העובדה צורפה" tone="success">
                  העובדה זמינה כעת למבחר של הסעיף בפרופיל הפעיל.
                </Callout>
              ) : null}
            </div>
          )}
        </div>
      )}

      <details className="mt-5 rounded-control border border-cv-border bg-cv-surface p-4">
        <summary className="cursor-pointer font-semibold text-cv-text">יצירת עובדה ממתינה חדשה</summary>
        <form
          className="mt-4 grid gap-3 lg:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <Field label="מקור הידע">
            {(control) => (
              <Select {...control} onChange={(event) => setSource(event.target.value as FactSource)} value={source}>
                {Object.entries(sourceLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field label="סוג הצגה">
            {(control) => (
              <Select {...control} onChange={(event) => setStyle(event.target.value as FactStyle)} value={style}>
                {Object.entries(styleLabels).map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </Select>
            )}
          </Field>
          <Field className="lg:col-span-2" label="משמעות">
            {(control) => <TextArea {...control} dir="auto" onChange={(event) => setMeaning(event.target.value)} required value={meaning} />}
          </Field>
          <Field label="ניסוח באנגלית">
            {(control) => <TextArea {...control} dir="ltr" onChange={(event) => setEnglish(event.target.value)} required value={english} />}
          </Field>
          <Field label="ניסוח בעברית (רשות)">
            {(control) => <TextArea {...control} onChange={(event) => setHebrew(event.target.value)} value={hebrew} />}
          </Field>
          <Field hint="יש להפריד תגיות בפסיקים." label="תגיות">
            {(control) => <TextInput {...control} onChange={(event) => setTags(event.target.value)} required value={tags} />}
          </Field>
          <Field label="מקור ואימות העובדה">
            {(control) => <TextArea {...control} dir="auto" onChange={(event) => setProvenance(event.target.value)} required value={provenance} />}
          </Field>
          <Button className="lg:col-span-2" disabled={!canCreate} pending={create.isPending} pendingLabel="יוצר…" type="submit">
            יצירת עובדה ממתינה
          </Button>
        </form>
      </details>
    </section>
  );
};
