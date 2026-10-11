#!/usr/bin/env bash
# Set the workflow version in info.plist without rewriting the rest of the file.
# PlistBuddy and plutil re-serialize the whole plist, which turns a one-line
# change into a large diff, so only the top-level <string> after the top-level
# version key is edited. The integer version keys inside objects are untouched.
#
#   ./bump-version.sh 1.2.3
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HERE/info.plist"
NEW="${1:-}"
fail() { echo "bump-version.sh: $*" >&2; exit 1; }

# X.Y.Z without leading zeros, as in Semantic Versioning.
[[ "$NEW" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]] || fail "usage: $0 X.Y.Z (no leading zeros)"
CURRENT="$(plutil -extract version raw "$PLIST")"
[ "$NEW" != "$CURRENT" ] || fail "info.plist is already at $NEW"

TAB="$(printf '\t')"
BACKUP="$(mktemp)"
cp "$PLIST" "$BACKUP"
trap 'rm -f "$BACKUP"' EXIT
restore() { cp "$BACKUP" "$PLIST"; fail "$1; info.plist left unchanged"; }

# BSD sed (macOS): -i takes a separate, empty backup suffix.
sed -i '' "/^${TAB}<key>version<\/key>/{n;s|<string>.*</string>|<string>${NEW}</string>|;}" "$PLIST"

CHANGED="$(diff "$BACKUP" "$PLIST" | grep -c '^>' || true)"
[ "$CHANGED" = 1 ] || restore "expected exactly one changed line, got $CHANGED"
[ "$(plutil -extract version raw "$PLIST")" = "$NEW" ] || restore "version did not read back as $NEW"
plutil -lint -s "$PLIST" || restore "info.plist no longer lints"
echo "info.plist version $CURRENT -> $NEW"
