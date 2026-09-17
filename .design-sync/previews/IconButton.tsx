import { IconButton } from "cv-application-frontend";
import { Copy, Pencil, Trash2, X } from "lucide-react";

export const Variants = () => (
  <div className="flex flex-wrap gap-3 p-4">
    <IconButton aria-label="העתק" variant="ghost">
      <Copy className="size-icon-md" />
    </IconButton>
    <IconButton aria-label="ערוך" variant="secondary">
      <Pencil className="size-icon-md" />
    </IconButton>
    <IconButton aria-label="סגור" variant="ghost">
      <X className="size-icon-md" />
    </IconButton>
    <IconButton aria-label="מחק" variant="destructive">
      <Trash2 className="size-icon-md" />
    </IconButton>
  </div>
);

export const Disabled = () => (
  <div className="flex flex-wrap items-center gap-3 p-4">
    <IconButton aria-label="העתק מבוטל" variant="ghost" disabled>
      <Copy className="size-icon-md" />
    </IconButton>
    <IconButton aria-label="ערוך מבוטל" variant="secondary" disabled>
      <Pencil className="size-icon-md" />
    </IconButton>
  </div>
);
