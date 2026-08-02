#!/bin/bash
# Lint a tailored CV draft against CLAUDE.md hard rules before PDF export.
# Usage: bash check_cv.sh outputs/<company>/cv-drafts/cv_<company>_<role>.md

set -e

FILE="$1"

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  echo "File not found: $FILE"
  exit 1
fi

FAIL=0

BUZZWORDS="passionate|ninja|rockstar|dynamic|results-driven"
if grep -Eion "$BUZZWORDS" "$FILE"; then
  echo "FAIL: buzzword(s) found above"
  FAIL=1
fi

# The "no em dash" rule applies to prose only (Profile paragraph, bullets).
# Headers (#/##/###), date-range lines, and the Languages section use em/en
# dash natively (matches base/cv_base.md) and are not prose, so they're
# excluded here before checking the rest of the file.
PROSE=$(awk '
  /^## Languages/ {skip=1; next}
  /^---$/ {skip=0}
  skip {next}
  /^#/ {next}
  {print}
' "$FILE")

if echo "$PROSE" | grep -n "—" >/dev/null; then
  echo "$PROSE" | grep -n "—"
  echo "FAIL: em dash found in prose text above (use ':' or restructure)"
  FAIL=1
fi

# En dash in prose is allowed only in digit-to-digit ranges (e.g. "2025 – 2026",
# "3–4 reps"). Any other use in prose fails.
BAD_ENDASH=$(echo "$PROSE" | grep -n "–" | grep -vE '[0-9][[:space:]]*–[[:space:]]*([0-9]|Present)' || true)
if [ -n "$BAD_ENDASH" ]; then
  echo "$BAD_ENDASH"
  echo "FAIL: en dash used in prose outside a date/number range (use ':' or restructure)"
  FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "OK: $FILE passed buzzword and em-dash checks"
  exit 0
else
  exit 1
fi
