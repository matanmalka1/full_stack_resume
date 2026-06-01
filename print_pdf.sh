#!/bin/bash
# Export HTML resume to PDF using Chrome headless
# Usage: bash print_pdf.sh jobs/company-name/tailored_resume.html

set -e

HTML_FILE="${1:-tailored_resume.html}"

if [ ! -f "$HTML_FILE" ]; then
  echo "File not found: $HTML_FILE"
  exit 1
fi

ABS_PATH="$(cd "$(dirname "$HTML_FILE")" && pwd)/$(basename "$HTML_FILE")"
PDF_PATH="${ABS_PATH%.html}.pdf"

CHROME=$(command -v "Google Chrome" 2>/dev/null \
  || command -v google-chrome 2>/dev/null \
  || command -v chromium 2>/dev/null \
  || echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

if [ ! -f "$CHROME" ] && ! command -v "$CHROME" &>/dev/null; then
  echo "Chrome not found. Install Chrome or run: brew install --cask google-chrome"
  exit 1
fi

"$CHROME" \
  --headless \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="$PDF_PATH" \
  --print-to-pdf-no-header \
  "file://$ABS_PATH" 2>/dev/null

echo "PDF saved: $PDF_PATH"
