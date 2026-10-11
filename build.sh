#!/usr/bin/env bash
# Build the distributable .alfredworkflow into dist/ and print its path.
# This is the single list of files that ship; install.sh and CI both use it.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
FILES=(info.plist repo_jump.py icon.png)
OUT="dist/GitHub-Repo-Jump.alfredworkflow"
cd "$HERE"
# zip only warns about missing files, so check first.
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "build.sh: missing $f" >&2; exit 1; }
done
mkdir -p dist
rm -f "$OUT"
zip -q "$OUT" "${FILES[@]}"
echo "$HERE/$OUT"
