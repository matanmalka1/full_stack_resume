#!/usr/bin/env python3
"""
Render a tailored CV draft (.md) into .html using config/resume_base.html.

Usage:
    python3 build_html.py outputs/<company>/cv-drafts/cv_<company>_<role>.md
    python3 build_html.py --check <same path>     # validate only, write nothing

Writes:
    outputs/<company>/cv-html/cv_<company>_<role>.html

The script parses the draft, validates it against the output contract in
config/cv_generation_rules.md, and only then renders. Any contract violation is a
hard failure with a line reference: nothing is written. This is deliberate. The
.md is the single source of truth for the PDF, so a draft that cannot be rendered
mechanically is a draft that is wrong, not a draft that needs manual HTML edits.

Python standard library only.
"""

import html
import re
import sys
from pathlib import Path

BASE_TITLES = [
    "Backend-Oriented Full-Stack Developer",
    "Full-Stack Developer",
]

# Each term maps to an entry in the Skills table of base/cv_base.md.
TAGLINE_TERMS = {
    "Python/FastAPI", "FastAPI", "Python", "Node.js",
    "React", "Next.js", "TypeScript", "JavaScript",
    "PostgreSQL", "SQL", "MongoDB", "SQLAlchemy",
    "REST APIs", "Docker", "AWS", "CI/CD",
    "AI Integrations", "GenAI", "LLM Integration", "Prompt Engineering",
}

MAX_TAGLINE_TERMS = 3

DOT = "\u00b7"


def validate_tagline(tagline):
    """Return None if the tagline is valid, otherwise a reason string."""
    parts = [p.strip() for p in tagline.split(DOT)]
    base = parts[0]
    terms = parts[1:]

    if base not in BASE_TITLES:
        return (f"base title must be one of {BASE_TITLES}, got {base!r}")

    if len(terms) > MAX_TAGLINE_TERMS:
        return (f"{len(terms)} technology terms, the maximum is "
                f"{MAX_TAGLINE_TERMS}")

    unknown = [t for t in terms if t not in TAGLINE_TERMS]
    if unknown:
        return (f"technology term(s) not in the approved list: "
                f"{', '.join(repr(u) for u in unknown)}")

    return None

BUZZWORDS = ["passionate", "ninja", "rockstar", "dynamic", "results-driven"]

REQUIRED_SECTIONS = ["Profile", "Work Experience", "Education", "Skills", "Languages"]

EM = "\u2014"  # em dash
EN = "\u2013"  # en dash

errors = []


def fail(msg, line_no=None):
    errors.append(f"  line {line_no}: {msg}" if line_no else f"  {msg}")


# ----------------------------------------------------------------- validation

def check_prose(text, line_no, where):
    """Prose = Profile paragraph and bullet text. Contract: no em dash at all;
    en dash only between digits."""
    if EM in text:
        fail(f"em dash in prose ({where}): use a colon or restructure", line_no)
    for m in re.finditer(EN, text):
        before = text[max(0, m.start() - 1):m.start()]
        after = text[m.end():m.end() + 1]
        if not (before.strip().isdigit() and after.strip().isdigit()):
            fail(f"en dash in prose outside a numeric range ({where})", line_no)
    if "**" in text or "__" in text:
        fail(f"inline bold in {where}: bold is allowed only on date lines", line_no)
    low = text.lower()
    for w in BUZZWORDS:
        if re.search(rf"\b{re.escape(w)}\b", low):
            fail(f"buzzword '{w}' in {where}", line_no)


def strip_front_matter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return lines[i + 1:], i + 1
        fail("front-matter opened with '---' but never closed")
    else:
        fail("missing YAML front-matter (created / modified)")
    return lines, 0


def md_links_to_html(text):
    """[Label](url) -> <a href="url" target="_blank">Label</a>"""
    return re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank">{html.escape(m.group(1))}</a>',
        text,
    )


# -------------------------------------------------------------------- parsing

def parse(path):
    raw = path.read_text(encoding="utf-8").split("\n")
    body, offset = strip_front_matter(raw)

    doc = {"name": "", "tagline": "", "contacts": [], "profile": "",
           "work": [], "education": [], "skills": [], "languages": []}

    i = 0

    def ln(idx):
        return offset + idx + 1

    # header: # Name / tagline / two contact lines
    while i < len(body) and not body[i].strip():
        i += 1
    if i >= len(body) or not body[i].startswith("# "):
        fail("expected '# Matan Malka' as the first content line", ln(i))
        return doc, []
    doc["name"] = body[i][2:].strip()
    i += 1

    while i < len(body) and not body[i].strip():
        i += 1
    if i < len(body):
        doc["tagline"] = body[i].strip()
        if doc["tagline"].startswith("[") or "@" in doc["tagline"]:
            fail("tagline line is missing: the line after '# Matan Malka' is the "
                 "contact block. Insert an allowed tagline above it.", ln(i))
        else:
            reason = validate_tagline(doc["tagline"])
            if reason:
                fail(f"tagline invalid: {reason}", ln(i))
        i += 1

    while i < len(body) and not body[i].strip():
        i += 1
    for _ in range(2):
        if i < len(body) and body[i].strip() and not body[i].startswith("-"):
            doc["contacts"].append(body[i].strip())
            i += 1
    if len(doc["contacts"]) != 2:
        fail("contact block must be exactly two lines", ln(i))

    # sections
    section = None
    entry = None
    seen = []

    while i < len(body):
        line = body[i]
        stripped = line.strip()

        if stripped.startswith("## "):
            section = stripped[3:].strip()
            seen.append(section)
            entry = None
            i += 1
            continue

        if stripped == "---" or not stripped:
            i += 1
            continue

        if section == "Profile":
            check_prose(stripped, ln(i), "Profile")
            doc["profile"] += (" " if doc["profile"] else "") + stripped

        elif section in ("Work Experience", "Education"):
            key = "work" if section == "Work Experience" else "education"
            if stripped.startswith("### "):
                title_line = stripped[4:].strip()
                if f" {EM} " not in title_line:
                    fail(f"'### ' line must use ' {EM} ' between title and company",
                         ln(i))
                    parts = re.split(r"\s+[\u2014\u2013,-]\s+", title_line, maxsplit=1)
                else:
                    parts = title_line.split(f" {EM} ", 1)
                entry = {"title": parts[0].strip(),
                         "org": parts[1].strip() if len(parts) > 1 else "",
                         "date": "", "bullets": []}
                doc[key].append(entry)
            elif stripped.startswith("**") and stripped.endswith("**"):
                if entry is None:
                    fail("date line before any '### ' title line", ln(i))
                else:
                    entry["date"] = stripped.strip("*").strip()
            elif stripped.startswith("- "):
                if entry is None:
                    fail("bullet before any '### ' title line", ln(i))
                else:
                    text = stripped[2:].strip()
                    check_prose(text, ln(i), f"{section} bullet")
                    entry["bullets"].append(text)

        elif section == "Skills":
            if not stripped.startswith("|"):
                i += 1
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) != 2:
                fail("Skills table row must have exactly two columns", ln(i))
            elif set(cells[0]) <= set("-: ") or cells[0].lower() == "category":
                pass  # header or separator row
            else:
                doc["skills"].append((cells[0], cells[1]))

        elif section == "Languages":
            if stripped.startswith("- "):
                text = stripped[2:].strip()
                if f" {EM} " not in text:
                    fail(f"Languages line must be '- <Language> {EM} <Level>'", ln(i))
                    parts = re.split(r"\s+[\u2014\u2013:-]\s+", text, maxsplit=1)
                else:
                    parts = text.split(f" {EM} ", 1)
                doc["languages"].append(
                    (parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""))

        i += 1

    if seen != REQUIRED_SECTIONS:
        fail(f"section order must be exactly {REQUIRED_SECTIONS}, got {seen}")

    return doc, seen


# ------------------------------------------------------------------ rendering

def render_contacts(lines):
    out = []
    parts = [p.strip() for p in lines[0].split("·")]
    for p in parts:
        if re.fullmatch(r"\+?[\d\-\s()]+", p):
            tel = re.sub(r"[^\d+]", "", p)
            out.append(f'<a href="tel:{tel}">{html.escape(p)}</a>')
        elif "@" in p:
            out.append(f'<a href="mailto:{html.escape(p)}">{html.escape(p)}</a>')
        else:
            out.append(html.escape(p))
    out.append(md_links_to_html(lines[1]).replace(" · ", " · "))
    return "\n".join(f"      {x}<br>" for x in out[:-1]) + f"\n      {out[-1]}"


def render_entries(entries, kind):
    blocks = []
    for e in entries:
        bullets = "\n".join(
            f"            <li>{html.escape(b)}</li>" for b in e["bullets"])
        if kind == "job":
            blocks.append(
                f'        <div class="job">\n'
                f'          <div class="job-header">\n'
                f'            <span class="job-title">{html.escape(e["title"])}</span>\n'
                f'            <span class="job-date">{html.escape(e["date"])}</span>\n'
                f'          </div>\n'
                f'          <div class="job-company">{html.escape(e["org"])}</div>\n'
                f'          <ul>\n{bullets}\n          </ul>\n'
                f'        </div>')
        else:
            title = f'{e["title"]} {EM} {e["org"]}' if e["org"] else e["title"]
            blocks.append(
                f'        <div class="edu">\n'
                f'          <div class="edu-title">{html.escape(title)}</div>\n'
                f'          <div class="edu-sub">{html.escape(e["date"])}</div>\n'
                f'          <ul>\n{bullets}\n          </ul>\n'
                f'        </div>')
    return "\n".join(blocks)


def render(doc, template):
    out = template
    out = out.replace("{{NAME}}", html.escape(doc["name"]))
    out = out.replace("{{TAGLINE}}", html.escape(doc["tagline"]))
    out = out.replace("{{CONTACTS}}", render_contacts(doc["contacts"]))
    out = out.replace("{{PROFILE}}", html.escape(doc["profile"]))
    out = out.replace("{{WORK}}", render_entries(doc["work"], "job"))
    out = out.replace("{{EDUCATION}}", render_entries(doc["education"], "edu"))
    out = out.replace("{{SKILLS}}", "\n".join(
        f'          <li><span class="skill-cat">{html.escape(c)}</span>'
        f'<span>{html.escape(t)}</span></li>' for c, t in doc["skills"]))
    out = out.replace("{{LANGUAGES}}", "\n".join(
        f'          <div class="lang-item">{html.escape(lang)} '
        f'<span class="lang-level">- {html.escape(level)}</span></div>'
        for lang, level in doc["languages"]))
    return out


# ----------------------------------------------------------------------- main

def main():
    args = sys.argv[1:]
    check_only = False
    if args and args[0] == "--check":
        check_only = True
        args = args[1:]

    if len(args) != 1:
        print(__doc__.strip())
        return 2

    md_path = Path(args[0])
    if not md_path.is_file():
        print(f"File not found: {md_path}")
        return 1
    if md_path.suffix != ".md":
        print(f"Expected a .md draft, got: {md_path}")
        return 1

    repo = Path(__file__).resolve().parent
    template_path = repo / "config" / "resume_base.html"
    if not template_path.is_file():
        print(f"Template not found: {template_path}")
        return 1

    doc, _ = parse(md_path)

    if errors:
        print(f"FAIL: {md_path} violates the output contract\n")
        print("\n".join(errors))
        print("\nSee config/cv_generation_rules.md. Nothing was written.")
        return 1

    if check_only:
        print(f"OK: {md_path} conforms to the output contract")
        return 0

    out_dir = md_path.parent.parent / "cv-html"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (md_path.stem + ".html")

    if out_path.exists():
        archive = repo / "outputs" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        backup = archive / f"{out_path.stem} (superseded).html"
        n = 2
        while backup.exists():
            backup = archive / f"{out_path.stem} (superseded {n}).html"
            n += 1
        out_path.replace(backup)
        print(f"Archived previous HTML: {backup}")

    out_path.write_text(render(doc, template_path.read_text(encoding="utf-8")),
                        encoding="utf-8")
    print(f"OK: {md_path}")
    print(f"HTML written: {out_path}")
    print(f"Next: bash print_pdf.sh \"{out_path}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())