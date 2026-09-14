import { useState } from "react";
import type { UpdateSettingsRequest } from "@/api/contracts";
import type { SettingsRead } from "@/api/settings";
import { Button } from "@/ui/Button";
import { editableSettings, settingsFieldLabels, settingValueLabel } from "../settings.model";

export const SettingsConflict = ({
  base,
  local,
  latest,
  onResolve,
}: {
  base: UpdateSettingsRequest;
  local: UpdateSettingsRequest;
  latest: SettingsRead;
  onResolve: (latest: SettingsRead, fields: UpdateSettingsRequest) => void;
}) => {
  const [selected, setSelected] = useState<Set<keyof UpdateSettingsRequest>>(new Set());
  const current = editableSettings(latest.settings);
  const fields = (Object.keys(current) as (keyof UpdateSettingsRequest)[]).filter(
    (key) => base[key] !== current[key] || base[key] !== local[key],
  );
  const apply = () => {
    const merged = { ...current };
    for (const key of selected) Object.assign(merged, { [key]: local[key] });
    onResolve(latest, merged);
  };
  return (
    <section aria-label="השוואת הגדרות" className="mt-4 space-y-4">
      <p>בחרו אילו עריכות מקומיות להחיל. כל שדה שלא נבחר יישאר כפי שהוא בשרת. לאחר ההחלה יש לשמור במפורש.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-start text-support">
          <caption>הבסיס, הגרסה העדכנית והעריכות שלך</caption>
          <thead>
            <tr>
              <th scope="col">הגדרה</th>
              <th scope="col">בעת פתיחת הטופס</th>
              <th scope="col">כעת בשרת</th>
              <th scope="col">העריכה שלך</th>
              <th scope="col">החלה</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((key) => (
              <tr key={key}>
                <th scope="row">{settingsFieldLabels[key]}</th>
                <td>{settingValueLabel(base[key])}</td>
                <td>{settingValueLabel(current[key])}</td>
                <td>{settingValueLabel(local[key])}</td>
                <td>
                  {base[key] !== local[key] && (
                    <label>
                      <input
                        type="checkbox"
                        checked={selected.has(key)}
                        onChange={(event) =>
                          setSelected((previous) => {
                            const next = new Set(previous);
                            if (event.target.checked) next.add(key);
                            else next.delete(key);
                            return next;
                          })
                        }
                      />{" "}
                      החלת העריכה: {settingsFieldLabels[key]}
                    </label>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => onResolve(latest, current)}>
          טעינת ערכי השרת והשלכת העריכות שלי
        </Button>
        <Button disabled={latest.etag === null} onClick={apply}>
          החלת הבחירה על הגרסה העדכנית
        </Button>
      </div>
    </section>
  );
};
