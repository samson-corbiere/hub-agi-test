#!/usr/bin/env bash
# Stop hook: before Claude ends a turn, verify the parts of the repo that changed.
#   backend/ or contract/  -> ruff (lint + format) + pytest
#   app/                   -> TypeScript check + `swift test` (CaptureCore) + iOS simulator build
#   .claude/hooks/         -> this hook's own tests
# Steps whose project doesn't exist yet are skipped.
# On failure, exit 2: the output goes back to Claude and the turn can't end until it's fixed.
# After 3 consecutive blocks in one session, the turn is allowed to end with a loud warning,
# so Claude can ask the user for help instead of looping forever.
set -uo pipefail

input=$(cat)
session_id=$(jq -r '.session_id // "unknown"' <<<"$input")
# false = Claude is ending a fresh turn (not one this hook already sent back), so the
# block counter starts over.
stop_hook_active=$(jq -r '.stop_hook_active // false' <<<"$input")
root="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$root" || exit 0

# --- What changed: uncommitted work (staged, unstaged, untracked), plus commits not yet on
# origin/main (or local main when there is no remote). Renames count as both paths;
# quotePath=false keeps paths with spaces or accents unquoted so the patterns match.
g() { git -c core.quotePath=false "$@"; }
base=$(g merge-base HEAD origin/main 2>/dev/null || g merge-base HEAD main 2>/dev/null || true)
changed=$(
  g diff --name-only --no-renames HEAD 2>/dev/null
  g ls-files --others --exclude-standard
  if [ -n "$base" ]; then g diff --name-only --no-renames "$base" HEAD; fi
)

touched() { grep -qE "$1" <<<"$changed"; }

failures=""
run() {
  local label="$1"; shift
  local out
  if ! out=$("$@" 2>&1); then
    failures+=$'\n'"### $label failed"$'\n'"$(tail -n 80 <<<"$out")"$'\n'
  fi
}

# --- The hook itself ---
if touched '^\.claude/hooks/'; then
  run "Stop hook tests" .claude/hooks/test_verify.sh
fi

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
[ "$stop_hook_active" = "true" ] || rm -f "$counter"
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
