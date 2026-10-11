#!/usr/bin/env bash
# Install (or update) this workflow in Alfred's workflows directory,
# and build a distributable .alfredworkflow in dist/.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ALFRED_DIR="$HOME/Library/Application Support/Alfred"
PREFS="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["current"])' "$ALFRED_DIR/prefs.json" 2>/dev/null || true)"
[ -n "$PREFS" ] || PREFS="$ALFRED_DIR/Alfred.alfredpreferences"  # default when no sync folder is set
BUNDLE="$(/usr/libexec/PlistBuddy -c 'Print :bundleid' "$HERE/info.plist")"
WF_DIR="$PREFS/workflows"
mkdir -p "$WF_DIR" "$HERE/dist"

# Reuse the directory of an installed copy with the same bundleid, else create one
TARGET=""
for d in "$WF_DIR"/*/; do
  [ -f "$d/info.plist" ] || continue
  if [ "$(/usr/libexec/PlistBuddy -c 'Print :bundleid' "$d/info.plist" 2>/dev/null)" = "$BUNDLE" ]; then
    TARGET="${d%/}"; break
  fi
done
[ -n "$TARGET" ] || TARGET="$WF_DIR/user.workflow.$(uuidgen)"
FILES=(info.plist repo_jump.py icon.png)
mkdir -p "$TARGET"
# Remove files left over from older versions. prefs.plist holds the user's
# workflow configuration (Cache TTL etc.), so it is kept.
find "$TARGET" -mindepth 1 -maxdepth 1 ! -name prefs.plist -exec rm -rf {} +
for f in "${FILES[@]}"; do cp "$HERE/$f" "$TARGET/"; done
echo "installed -> $TARGET"

( cd "$HERE" && rm -f dist/GitHub-Repo-Jump.alfredworkflow && zip -q dist/GitHub-Repo-Jump.alfredworkflow "${FILES[@]}" )
echo "packaged  -> $HERE/dist/GitHub-Repo-Jump.alfredworkflow"
