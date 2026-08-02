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

if grep -n "—" "$FILE"; then
  echo "FAIL: em dash found above (use ':' or restructure)"
  FAIL=1
fi

if [ "$FAIL" -eq 0 ]; then
  echo "OK: $FILE passed buzzword and em-dash checks"
  exit 0
else
  exit 1
fi
