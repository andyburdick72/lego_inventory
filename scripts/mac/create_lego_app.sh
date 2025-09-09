#!/bin/zsh
set -euo pipefail

# --- resolve project root (works whether run from repo or anywhere) ---
# Prefer git, fall back to inferring from script path (…/scripts/mac -> repo root)
if ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
  :
else
  # zsh-specific: ${0:A} = absolute path to this script
  SCRIPT_DIR="${0:A:h}"
  ROOT="${SCRIPT_DIR:h:h}"
fi

# --- settings ---
APP_NAME="Start LEGO Server.app"
APP_DIR="$HOME/Applications/$APP_NAME"
PROJECT_DIR="$ROOT"                        # repo root
PNG_ICON="$ROOT/lego.png"
ICNS_ICON="$ROOT/lego.icns"                # generated if missing
EXEC_NAME="start-lego"

echo "Project root: $PROJECT_DIR"
echo "Output app  : $APP_DIR"

# --- make .icns from lego.png if needed ---
if [ ! -f "$ICNS_ICON" ]; then
  if [ ! -f "$PNG_ICON" ]; then
    echo "ERROR: PNG icon not found at $PNG_ICON" >&2
    exit 1
  fi
  WORK="/tmp/lego.iconset"
  rm -rf "$WORK"; mkdir -p "$WORK"

  sips -z 16 16     "$PNG_ICON" --out "$WORK/icon_16x16.png"        >/dev/null
  sips -z 32 32     "$PNG_ICON" --out "$WORK/icon_16x16@2x.png"     >/dev/null
  sips -z 32 32     "$PNG_ICON" --out "$WORK/icon_32x32.png"        >/dev/null
  sips -z 64 64     "$PNG_ICON" --out "$WORK/icon_32x32@2x.png"     >/dev/null
  sips -z 128 128   "$PNG_ICON" --out "$WORK/icon_128x128.png"      >/dev/null
  sips -z 256 256   "$PNG_ICON" --out "$WORK/icon_128x128@2x.png"   >/dev/null
  sips -z 256 256   "$PNG_ICON" --out "$WORK/icon_256x256.png"      >/dev/null
  sips -z 512 512   "$PNG_ICON" --out "$WORK/icon_256x256@2x.png"   >/dev/null
  sips -z 512 512   "$PNG_ICON" --out "$WORK/icon_512x512.png"      >/dev/null

  # Try 1024 for 512@2x if source is big enough; else copy original
  if sips -g pixelWidth -g pixelHeight "$PNG_ICON" | grep -qE 'pixel(Width|Height): (1[0-9]{3}|[2-9][0-9]{3})'; then
    sips -z 1024 1024 "$PNG_ICON" --out "$WORK/icon_512x512@2x.png" >/dev/null || cp "$PNG_ICON" "$WORK/icon_512x512@2x.png"
  else
    cp "$PNG_ICON" "$WORK/icon_512x512@2x.png"
  fi

  iconutil -c icns "$WORK" -o "$ICNS_ICON"
  rm -rf "$WORK"
fi

# --- app bundle skeleton ---
mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"

# --- Info.plist ---
cat > "$APP_DIR/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>               <string>Start LEGO Server</string>
  <key>CFBundleDisplayName</key>        <string>Start LEGO Server</string>
  <key>CFBundleIdentifier</key>         <string>com.andyscripts.start-lego-server</string>
  <key>CFBundleVersion</key>            <string>1.0</string>
  <key>CFBundleShortVersionString</key> <string>1.0</string>
  <key>CFBundlePackageType</key>        <string>APPL</string>
  <key>CFBundleExecutable</key>         <string>start-lego</string>
  <key>CFBundleIconFile</key>           <string>lego</string>
  <key>LSMinimumSystemVersion</key>     <string>10.15</string>
</dict>
</plist>
PLIST

# --- icon into bundle ---
cp "$ICNS_ICON" "$APP_DIR/Contents/Resources/lego.icns"

# --- launcher (opens Terminal and runs your server) ---
cat > "$APP_DIR/Contents/MacOS/$EXEC_NAME" <<'LAUNCHER'
#!/bin/zsh
set -euo pipefail
PROJECT_DIR="$(/usr/bin/osascript -e 'tell application "Finder" to POSIX path of (container of (path to me) as alias)')"
# ^ "path to me" -> .../Start LEGO Server.app/Contents/MacOS/
# container twice -> .../Start LEGO Server.app/Contents/
# We want repo root, so store it during build:
PROJECT_DIR_PLACEHOLDER
osascript <<EOF
tell application "Terminal"
  activate
  do script "cd \"$PROJECT_DIR\"; source .venv/bin/activate; python3 src/app/server.py"
end tell
EOF
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/$EXEC_NAME"

# Replace placeholder with actual repo root so app works anywhere
/usr/bin/sed -i '' -e "s|PROJECT_DIR_PLACEHOLDER|PROJECT_DIR=\"$PROJECT_DIR\"|g" "$APP_DIR/Contents/MacOS/$EXEC_NAME"

echo "Created: $APP_DIR"
echo "Tip: drag it to /Applications and your Dock. If the icon doesn't update: killall Dock"