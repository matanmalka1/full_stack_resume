import { useState } from "react";
import { ViewSwitch } from "cv-application-frontend";
import { LayoutList, Table2 } from "lucide-react";

type ViewMode = "list" | "table";

export const WithIcons = () => {
  const [view, setView] = useState<ViewMode>("list");
  return (
    <div className="p-4">
      <ViewSwitch
        label="מצב תצוגה"
        value={view}
        onChange={setView}
        options={[
          { value: "list", label: "רשימה", icon: LayoutList },
          { value: "table", label: "טבלה", icon: Table2 },
        ]}
      />
    </div>
  );
};

export const WithLabels = () => {
  const [view, setView] = useState<ViewMode>("list");
  return (
    <div className="p-4">
      <ViewSwitch
        label="מצב תצוגה"
        value={view}
        onChange={setView}
        showLabels
        options={[
          { value: "list", label: "רשימה", icon: LayoutList },
          { value: "table", label: "טבלה", icon: Table2 },
        ]}
      />
    </div>
  );
};

export const TextOnly = () => {
  const [active, setActive] = useState<"editor" | "preview">("editor");
  return (
    <div className="p-4">
      <ViewSwitch
        label="מצב עריכה"
        value={active}
        onChange={setActive}
        options={[
          { value: "editor", label: "עורך" },
          { value: "preview", label: "תצוגה מקדימה" },
        ]}
      />
    </div>
  );
};
