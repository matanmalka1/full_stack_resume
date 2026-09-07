import { useQuery } from "@tanstack/react-query";
import { Briefcase, Building2, ChevronDown, Plus, Search } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { applicationDetailQueryOptions, applicationListQueryOptions } from "../api/applications";
import { appRoutes } from "./appRoutes";
import { preparationStateLabels, preparationStateTones } from "../pages/application/applicationLabels";
import { StatusBadge } from "../ui/StatusBadge";
import { cx } from "../ui/cx";

export const ApplicationQuickSwitcher = () => {
  const [open, setOpen] = useState(false);
  const [filter, setFilter] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { applicationId } = useParams<{ applicationId?: string }>();

  const listQuery = useQuery(applicationListQueryOptions({ limit: 50 }));
  const items = listQuery.data?.items ?? [];

  /* Only while the open screen is one Application's own: `new` is intake, not a record
     to look up. */
  const detailQuery = useQuery({
    ...applicationDetailQueryOptions(applicationId ?? ""),
    enabled: applicationId !== undefined && applicationId !== "new",
  });
  const currentDetail = detailQuery.data;

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [open]);

  useEffect(() => {
    setOpen(false);
    setFilter("");
  }, [location.pathname]);

  const filteredItems = items.filter((item) => {
    if (!filter.trim()) {
      return true;
    }
    const q = filter.trim().toLowerCase();
    return item.company.toLowerCase().includes(q) || item.target_role.toLowerCase().includes(q);
  });

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        aria-expanded={open}
        aria-haspopup="listbox"
        className={cx(
          "inline-flex items-center gap-2 rounded-control border px-3 py-1.5 text-support font-semibold transition-colors",
          currentDetail !== undefined
            ? "border-cv-border bg-cv-surface text-cv-text shadow-surface hover:border-cv-border-strong"
            : "border-cv-border/70 bg-cv-surface-muted text-cv-text-muted hover:border-cv-border hover:text-cv-text",
        )}
        onClick={() => setOpen((prev) => !prev)}
        type="button"
      >
        {currentDetail !== undefined ? (
          <>
            <Building2 aria-hidden="true" className="size-4 shrink-0 text-cv-accent" />
            <span className="max-w-[140px] truncate sm:max-w-[200px]" dir="auto">
              {currentDetail.application.company} · {currentDetail.application.target_role}
            </span>
          </>
        ) : (
          <>
            <Briefcase aria-hidden="true" className="size-4 shrink-0 text-cv-text-muted" />
            <span className="hidden sm:inline">מעבר למועמדות…</span>
            <span className="sm:hidden">מועמדויות</span>
          </>
        )}
        <ChevronDown
          aria-hidden="true"
          className={cx("size-3.5 shrink-0 text-cv-text-muted transition-transform duration-150", open && "rotate-180")}
        />
      </button>

      {open ? (
        <div
          className="absolute start-0 top-full z-40 mt-1.5 w-72 sm:w-84 rounded-control border border-cv-border bg-cv-surface p-1.5 shadow-floating"
          role="listbox"
        >
          {items.length > 5 ? (
            <div className="mb-1.5 flex items-center gap-2 border-b border-cv-border px-2 pb-1.5 pt-1">
              <Search aria-hidden="true" className="size-3.5 text-cv-text-muted" />
              <input
                autoFocus
                className="w-full bg-transparent text-support text-cv-text placeholder:text-cv-text-muted focus:ring-0"
                dir="auto"
                onChange={(e) => setFilter(e.target.value)}
                placeholder="סינון מועמדויות…"
                type="text"
                value={filter}
              />
            </div>
          ) : null}

          <div className="max-h-64 overflow-y-auto">
            {filteredItems.length === 0 ? (
              <p className="p-3 text-center text-support text-cv-text-muted">לא נמצאו מועמדויות</p>
            ) : (
              filteredItems.map((item) => {
                const isCurrent = item.id === applicationId;
                return (
                  <button
                    aria-selected={isCurrent}
                    className={cx(
                      "flex w-full items-center justify-between gap-2 rounded-control p-2 text-start transition-colors",
                      isCurrent ? "bg-cv-accent-soft/80 font-bold" : "hover:bg-cv-surface-muted",
                    )}
                    key={item.id}
                    onClick={() => {
                      setOpen(false);
                      navigate(appRoutes.application(item.id));
                    }}
                    role="option"
                    type="button"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-support font-semibold text-cv-text" dir="auto">
                        {item.company}
                      </p>
                      <p className="truncate text-support text-cv-text-muted" dir="auto">
                        {item.target_role}
                      </p>
                    </div>

                    <div className="flex shrink-0 items-center gap-1.5">
                      <StatusBadge
                        className="px-2 py-0.5 text-xs"
                        tone={preparationStateTones[item.preparation_state]}
                      >
                        {preparationStateLabels[item.preparation_state]}
                      </StatusBadge>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          <div className="mt-1 flex items-center justify-between border-t border-cv-border px-2 pt-2 text-support">
            <Link
              className="font-medium text-cv-text-muted hover:text-cv-text hover:underline"
              onClick={() => setOpen(false)}
              to={appRoutes.home}
            >
              לוח המועמדויות
            </Link>
            <Link
              className="inline-flex items-center gap-1 font-semibold text-cv-accent hover:underline"
              onClick={() => setOpen(false)}
              to={appRoutes.newApplication}
            >
              <Plus aria-hidden="true" className="size-3.5" />
              משרה חדשה
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
};
