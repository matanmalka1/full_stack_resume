#!/usr/bin/env python3
"""
Batch-fix the mechanical contract violations in legacy CV drafts.

Usage:
    python3 fix_drafts.py            # dry run, shows a per-file summary
    python3 fix_drafts.py --apply    # rewrite the drafts in place

Fixes only what is deterministic:

  1. inline bold inside bullets            **React**  ->  React
  2. '### ' separator                      -  ·  –  ,  ->  em dash
  3. Languages line separator              :  -  ·  –  ->  em dash
  4. bold tagline                          **...**    ->  ...
  5. missing tagline                       recovered from the sibling cv-html file,
                                           which records the variant chosen at the time

Anything requiring judgement is reported and left alone: a tagline that is not an
allowed variant, a draft in a different format entirely, an em dash inside prose.
Those need a sentence rewritten or a decision, not a substitution.

Commit before running with --apply. Git is the undo.

Python standard library only.
"""

import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent
OUTPUTS = REPO / "outputs"

EM = "\u2014"
EN = "\u2013"

ALLOWED_TAGLINES = [
    "Full-Stack Developer \u00b7 Python/FastAPI \u00b7 React \u00b7 AI Integrations",
    "Full-Stack Developer \u00b7 Python/FastAPI \u00b7 React",
    "Backend-Oriented Full-Stack Developer",
    "Full-Stack Developer \u00b7 AI Integrations",
]

# Ordered: the em dash form is already correct, everything else is rewritten to it.
SEPARATORS = [f" {EM} ", f" {EN} ", " \u00b7 ", " - ", ", "]

TODAY = date.today().isoformat()


def split_on_first_separator(text):
    """Return (left, right) at the earliest separator, or (text, None)."""
    best = None
    for sep in SEPARATORS:
        idx = text.find(sep)
        if idx != -1 and (best is None or idx < best[0]):
            best = (idx, sep)
    if best is None:
        return text, None
    idx, sep = best
    return text[:idx].strip(), text[idx + len(sep):].strip()


def tagline_from_html(md_path):
    """Recover the tagline the draft was actually built with."""
    html_path = md_path.parent.parent / "cv-html" / (md_path.stem + ".html")
    if not html_path.is_file():
        return None
    m = re.search(r'<div class="tagline">(.*?)</div>',
                  html_path.read_text(encoding="utf-8"), re.S)
    if not m:
        return None
    return re.sub(r"<[^>]+>", "", m.group(1)).strip()


def fix(md_path):
    """Return (new_lines, changes, blockers)."""
    lines = md_path.read_text(encoding="utf-8").split("\n")
    changes = []
    blockers = []

    # ---- front matter: bump modified
    for i, line in enumerate(lines[:10]):
        if line.startswith("modified:") and TODAY not in line:
            lines[i] = f"modified: {TODAY}"
            changes.append("modified date bumped")
            break

    # ---- locate the name heading
    name_idx = next((i for i, l in enumerate(lines) if l.startswith("# ")), None)
    if name_idx is None:
        blockers.append("no '# Matan Malka' heading, not an output-format draft")
        return lines, changes, blockers

    nxt = next((i for i in range(name_idx + 1, len(lines)) if lines[i].strip()), None)
    if nxt is None:
        blockers.append("nothing after the name heading")
        return lines, changes, blockers

    candidate = lines[nxt].strip()

    if candidate.startswith("##"):
        blockers.append(f"line {nxt + 1}: draft uses the base-CV layout, not the "
                        f"output skeleton: {candidate!r}")
        return lines, changes, blockers

    if candidate in ALLOWED_TAGLINES:
        pass
    elif candidate.startswith("**") and candidate.endswith("**"):
        stripped = candidate.strip("*").strip()
        if stripped in ALLOWED_TAGLINES:
            lines[nxt] = stripped
            changes.append("tagline unbolded")
        else:
            blockers.append(f"line {nxt + 1}: tagline is not an allowed variant: "
                            f"{stripped!r}")
    else:
        recovered = tagline_from_html(md_path)
        if recovered is None:
            blockers.append("tagline missing and no sibling cv-html file to recover "
                            "it from")
        elif recovered not in ALLOWED_TAGLINES:
            blockers.append(f"tagline missing; the HTML says {recovered!r}, which is "
                            f"not an allowed variant")
        else:
            lines.insert(nxt, "")
            lines.insert(nxt, recovered)
            changes.append(f"tagline inserted from HTML: {recovered}")

    # ---- section-aware line fixes
    section = None
    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.startswith("## "):
            section = stripped[3:].strip()
            continue

        if stripped.startswith("### "):
            title, rest = split_on_first_separator(stripped[4:].strip())
            if rest is None:
                blockers.append(f"line {i + 1}: cannot split the '### ' line")
            else:
                fixed = f"### {title} {EM} {rest}"
                if fixed != stripped:
                    lines[i] = fixed
                    changes.append(f"line {i + 1}: '### ' separator normalized")
            continue

        if section == "Languages" and stripped.startswith("- "):
            body = stripped[2:].strip()
            lang, level = split_on_first_separator(body)
            if level is None and ": " in body:
                lang, level = body.split(": ", 1)
            elif level is None and ":" in body:
                lang, level = body.split(":", 1)
            if level is None:
                blockers.append(f"line {i + 1}: cannot split the Languages line")
            else:
                fixed = f"- {lang.strip()} {EM} {level.strip()}"
                if fixed != stripped:
                    lines[i] = fixed
                    changes.append(f"line {i + 1}: Languages separator normalized")
            continue

        if stripped.startswith("- ") and "**" in stripped:
            lines[i] = line.replace("**", "")
            changes.append(f"line {i + 1}: inline bold removed")
            continue

        if section in ("Profile", "Work Experience", "Education"):
            if not stripped.startswith(("-", "#", "|", "**", "---")) and EM in stripped:
                blockers.append(f"line {i + 1}: em dash inside prose, needs rewording")

    # em dash inside bullets, after bold removal
    section = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip()
        elif (section in ("Work Experience", "Education")
              and stripped.startswith("- ") and EM in stripped):
            blockers.append(f"line {i + 1}: em dash inside a bullet, needs rewording")

    return lines, changes, blockers


def main():
    apply_changes = "--apply" in sys.argv[1:]

    drafts = [p for p in sorted(OUTPUTS.glob("*/cv-drafts/cv_*.md"))
              if not p.name.endswith(".notes.md")]
    if not drafts:
        print("No drafts found under outputs/*/cv-drafts/")
        return 1

    fixed_count = 0
    blocked = []

    for md in drafts:
        new_lines, changes, blockers = fix(md)
        rel = md.relative_to(REPO)

        if not changes and not blockers:
            continue

        print(f"\n{rel}")
        for c in changes:
            print(f"  fix      {c}")
        for b in blockers:
            print(f"  BLOCKED  {b}")

        if blockers:
            blocked.append(rel)

        if changes and apply_changes:
            md.write_text("\n".join(new_lines), encoding="utf-8")
            fixed_count += 1

    print("\n" + "=" * 60)
    if apply_changes:
        print(f"Rewrote {fixed_count} draft(s).")
    else:
        print("Dry run. Nothing was changed. Re-run with --apply to execute.")

    if blocked:
        print(f"\n{len(blocked)} draft(s) still need a human decision:")
        for rel in blocked:
            print(f"  {rel}")

    print("\nThen re-run the survey:")
    print("  for f in outputs/*/cv-drafts/cv_*.md; do")
    print("    case \"$f\" in *.notes.md) continue;; esac")
    print("    python3 build_html.py --check \"$f\" >/dev/null 2>&1 || echo \"FAIL $f\"")
    print("  done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
