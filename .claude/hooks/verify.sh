#!/usr/bin/env bash
# Stop hook: before Claude ends a turn, verify the parts of the repo that changed.
#   backend/ or contract/  -> ruff (lint + format) + pytest
#   app/                   -> TypeScript check + `swift test` (CaptureCore) + iOS simulator build
# Steps whose project doesn't exist yet are skipped.
# On failure, exit 2: the output goes back to Claude and the turn can't end until it's fixed.
# After 3 consecutive blocks in one session, the turn is allowed to end with a loud warning,
# so Claude can ask the user for help instead of looping forever.
set -uo pipefail

input=$(cat)
session_id=$(jq -r '.session_id // "unknown"' <<<"$input")
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$root" || exit 0

# --- What changed: uncommitted work, plus commits on this branch since it left main ---
changed=$(git status --porcelain --untracked-files=all | cut -c4-)
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ -n "$branch" ] && [ "$branch" != "main" ] && git rev-parse --verify -q main >/dev/null; then
  base=$(git merge-base HEAD main)
  changed+=$'\n'$(git diff --name-only "$base" HEAD)
fi

touched() { grep -qE "$1" <<<"$changed"; }

failures=""
run() {
  local label="$1"; shift
  local out
  if ! out=$("$@" 2>&1); then
    failures+=$'\n'"### $label failed"$'\n'"$(tail -n 80 <<<"$out")"$'\n'
  fi
}

# --- Backend + contract ---
if touched '^(backend|contract)/' && [ -f backend/pyproject.toml ]; then
  run "Backend lint" bash -c 'cd backend && uv run ruff check . ../contract && uv run ruff format --check . ../contract'
  run "Backend tests" bash -c 'cd backend && uv run pytest'
fi

# --- App ---
core=app/modules/capture/ios/CaptureCore
if touched '^app/'; then
  if [ -f app/package.json ] && [ -f app/tsconfig.json ]; then
    run "TypeScript" bash -c 'cd app && npx --no-install tsc --noEmit'
  fi
  if [ -f "$core/Package.swift" ]; then
    run "CaptureCore tests" bash -c "cd $core && swift test"
  fi
  if [ -f app/package.json ]; then
    run "iOS build" bash -c '
      cd app
      [ -d ios ] || CI=1 npx expo prebuild --platform ios >/dev/null || exit 1
      ws=$(ls -d ios/*.xcworkspace 2>/dev/null | head -n1)
      [ -n "$ws" ] || { echo "no Xcode workspace in app/ios"; exit 1; }
      scheme=$(basename "$ws" .xcworkspace)
      xcodebuild -workspace "$ws" -scheme "$scheme" -configuration Debug \
        -sdk iphonesimulator -destination "generic/platform=iOS Simulator" \
        CODE_SIGNING_ALLOWED=NO -quiet build'
  fi
fi

counter="${TMPDIR:-/tmp}/capturekit-stop-hook-${session_id}"
if [ -z "$failures" ]; then
  rm -f "$counter"
  exit 0
fi

count=$(( $(cat "$counter" 2>/dev/null || echo 0) + 1 ))
echo "$count" >"$counter"
if [ "$count" -gt 3 ]; then
  rm -f "$counter"
  msg="Verification still failing after 3 attempts. Do NOT report the task as done; tell the user what fails."
  jq -n --arg m "$msg" '{systemMessage: $m}'
  exit 0
fi

printf 'Verification failed (attempt %s/3). Fix these before ending the turn; never report a task as done while they fail:\n%s' "$count" "$failures" >&2
exit 2
