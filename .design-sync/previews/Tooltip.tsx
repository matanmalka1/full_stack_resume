import { IconButton, Tooltip } from "cv-application-frontend";
import { Copy, Info } from "lucide-react";

export const Default = () => (
  <div className="flex flex-wrap gap-6 p-8">
    <Tooltip label="העתק לזיכרון">
      <IconButton aria-label="העתק" variant="ghost">
        <Copy className="size-icon-md" />
      </IconButton>
    </Tooltip>
    <Tooltip label="מידע נוסף" placement="bottom">
      <IconButton aria-label="מידע" variant="ghost">
        <Info className="size-icon-md" />
      </IconButton>
    </Tooltip>
  </div>
);

export const Placements = () => (
  <div className="flex flex-wrap items-center gap-6 p-10">
    <Tooltip label="מעל" placement="top">
      <IconButton aria-label="מעל" variant="secondary">
        <Info className="size-icon-md" />
      </IconButton>
    </Tooltip>
    <Tooltip label="מתחת" placement="bottom">
      <IconButton aria-label="מתחת" variant="secondary">
        <Info className="size-icon-md" />
      </IconButton>
    </Tooltip>
  </div>
);
