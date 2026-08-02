#!/bin/bash
# Export an HTML resume to PDF using Chrome headless.
#
# Usage: bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html
#
# Output: outputs/<company>/cv-pdf/<role>/Matan Malka - Full Stack Developer.pdf
#
# The filename is fixed because that is what a recruiter sees. The role folder
# keeps two live roles at the same company from silently overwriting each other.
# Any existing PDF at the target path is archived, never overwritten in place.

set -euo pipefail

HTML_FILE="${1:-}"

if [ -z "$HTML_FILE" ] || [ ! -f "$HTML_FILE" ]; then
  echo "File not found: ${HTML_FILE:-<no argument>}"
  echo "Usage: bash print_pdf.sh outputs/<company>/cv-html/cv_<company>_<role>.html"
  exit 1
fi

case "$HTML_FILE" in
  *.html) ;;
  *)
    echo "Expected a .html file, got: $HTML_FILE"
    echo "Never export a PDF from a .md draft. Run build_html.py first."
    exit 1
    ;;
esac

ABS_PATH="$(cd "$(dirname "$HTML_FILE")" && pwd)/$(basename "$HTML_FILE")"
HTML_DIR="$(dirname "$ABS_PATH")"
COMPANY_DIR="$(dirname "$HTML_DIR")"
OUTPUTS_DIR="$(dirname "$COMPANY_DIR")"
COMPANY="$(basename "$COMPANY_DIR")"
BASE="$(basename "$ABS_PATH" .html)"

# cv_<company>_<role> -> <role>
PREFIX="cv_${COMPANY}_"
case "$BASE" in
  "$PREFIX"*)
    ROLE="${BASE#"$PREFIX"}"
    ;;
  *)
    echo "Filename does not match cv_<company>_<role>.html"
    echo "  file:    $BASE.html"
    echo "  company: $COMPANY (from the folder name)"
    echo "Rename the draft so the HTML, the company folder, and status.csv agree."
    exit 1
    ;;
esac

PDF_DIR="$COMPANY_DIR/cv-pdf/$ROLE"
mkdir -p "$PDF_DIR"
PDF_PATH="$PDF_DIR/Matan Malka - Full Stack Developer.pdf"

if [ -f "$PDF_PATH" ]; then
  ARCHIVE="$OUTPUTS_DIR/archive"
  mkdir -p "$ARCHIVE"
  STAMP="$(date +%Y-%m-%d)"
  BACKUP="$ARCHIVE/Matan Malka - Full Stack Developer ($COMPANY $ROLE, superseded, $STAMP).pdf"
  N=2
  while [ -f "$BACKUP" ]; do
    BACKUP="$ARCHIVE/Matan Malka - Full Stack Developer ($COMPANY $ROLE, superseded $N, $STAMP).pdf"
    N=$((N + 1))
  done
  mv "$PDF_PATH" "$BACKUP"
  echo "Archived previous PDF: $BACKUP"
fi

CHROME=""
for candidate in \
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  "$(command -v google-chrome 2>/dev/null || true)" \
  "$(command -v chromium 2>/dev/null || true)" \
  "$(command -v chromium-browser 2>/dev/null || true)"
do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    CHROME="$candidate"
    break
  fi
done

if [ -z "$CHROME" ]; then
  echo "Chrome not found. Install it with: brew install --cask google-chrome"
  exit 1
fi

"$CHROME" \
  --headless \
  --disable-gpu \
  --no-sandbox \
  --print-to-pdf="$PDF_PATH" \
  --print-to-pdf-no-header \
  "file://$ABS_PATH" 2>/dev/null

if [ ! -f "$PDF_PATH" ]; then
  echo "Chrome ran but produced no PDF: $PDF_PATH"
  exit 1
fi

echo "PDF saved: $PDF_PATH"
echo "status.csv cv_file: outputs/$COMPANY/cv-pdf/$ROLE/Matan Malka - Full Stack Developer.pdf"