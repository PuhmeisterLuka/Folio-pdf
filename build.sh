#!/usr/bin/env bash
# Packages Folio PDF as a macOS .app bundle with PyInstaller.
#
#   bash build.sh
#
# Output lands in dist/Folio PDF.app

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Folio PDF"
ENTRY="main.py"
ICON="assets/logo.icns"
DIST_DIR="dist"
BUILD_DIR="build"

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo "No virtual environment active."
  echo "  source venv/bin/activate"
  echo "or create one first:"
  echo "  python3 -m venv venv && source venv/bin/activate"
  exit 1
fi

echo "Installing dependencies..."
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller

echo "Cleaning previous build..."
rm -rf "$DIST_DIR" "$BUILD_DIR" "${APP_NAME}.spec"

# PyInstaller misses these on its own
HIDDEN=(
  "customtkinter"
  "tkinterdnd2"
  "pypdf"
  "fitz"
  "PIL"
  "PIL.Image"
  "PIL.ImageTk"
  "docx2pdf"
)
HIDDEN_ARGS=()
for h in "${HIDDEN[@]}"; do
  HIDDEN_ARGS+=("--hidden-import=$h")
done

# find package data through pip show instead of importing, importing tk
# libraries at build time causes dylib headaches
_pkg_location() { python3 -m pip show "$1" 2>/dev/null | grep '^Location:' | sed 's/Location: //'; }

CTK_PATH="$(_pkg_location customtkinter)/customtkinter"
TK_DND_PATH="$(_pkg_location tkinterdnd2)/tkinterdnd2"
DOCX2PDF_PATH="$(_pkg_location docx2pdf)/docx2pdf"

DATA_ARGS=(
  "--add-data=${CTK_PATH}:customtkinter"
)
if [ -d "$TK_DND_PATH" ]; then
  DATA_ARGS+=("--add-data=${TK_DND_PATH}:tkinterdnd2")
else
  echo "warning: tkinterdnd2 not found, drag and drop will not work in the built app"
  echo "         pip install tkinterdnd2"
fi
if [ -f "${DOCX2PDF_PATH}/convert.jxa" ]; then
  DATA_ARGS+=("--add-data=${DOCX2PDF_PATH}/convert.jxa:docx2pdf")
else
  echo "warning: docx2pdf convert.jxa not found, Word to PDF will not work in the built app"
fi
if [ -d "assets" ]; then
  DATA_ARGS+=("--add-data=assets:assets")
fi

ICON_ARGS=()
if [ -f "$ICON" ]; then
  ICON_ARGS+=("--icon=$ICON")
else
  echo "warning: no icon at $ICON, building without one"
fi

echo "Running PyInstaller..."
PYINSTALLER_ARGS=(
  --name "$APP_NAME"
  --windowed
  --onedir
  --noconfirm
  --osx-bundle-identifier "com.foliopdf.app"
  --distpath "$DIST_DIR"
  --workpath "$BUILD_DIR"
  "${HIDDEN_ARGS[@]+"${HIDDEN_ARGS[@]}"}"
  "${DATA_ARGS[@]+"${DATA_ARGS[@]}"}"
  "${ICON_ARGS[@]+"${ICON_ARGS[@]}"}"
  "$ENTRY"
)
python3 -m PyInstaller "${PYINSTALLER_ARGS[@]}"

# macOS refuses to show the automation permission prompt for Word unless the
# usage description is in the plist, and the single instance lock needs its
# own key too
PLIST="$DIST_DIR/$APP_NAME.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c \
  "Add :NSAppleEventsUsageDescription string 'Folio PDF uses Microsoft Word to convert .docx files to PDF.'" \
  "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c \
  "Set :NSAppleEventsUsageDescription 'Folio PDF uses Microsoft Word to convert .docx files to PDF.'" \
  "$PLIST"
/usr/libexec/PlistBuddy -c \
  "Add :LSMultipleInstancesProhibited bool true" \
  "$PLIST" 2>/dev/null || \
/usr/libexec/PlistBuddy -c \
  "Set :LSMultipleInstancesProhibited true" \
  "$PLIST"

echo ""
echo "Build complete: $DIST_DIR/$APP_NAME.app"
echo "Run it with: open \"$DIST_DIR/$APP_NAME.app\""
