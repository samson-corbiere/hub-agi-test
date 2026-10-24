#!/usr/bin/env bash
# Tests for the Stop hook (verify.sh). Run: .claude/hooks/test_verify.sh
# Each case builds a throwaway repo where `uv` always fails: if the hook runs the
# backend checks, it must exit 2; if it wrongly skips them, it exits 0.
HOOK="$(cd "$(dirname "$0")" && pwd)/verify.sh"
S=$(mktemp -d); trap 'rm -rf "$S"' EXIT
mkdir -p $S/fakebin; printf '#!/bin/sh\necho "fake uv: failing"; exit 1\n' > $S/fakebin/uv; chmod +x $S/fakebin/uv
pass=0; fail=0
setup() {
  R=$(mktemp -d "$S/hookrepo.XXXX"); cd "$R"
  git init -q -b main; git config user.email t@t; git config user.name t
  mkdir -p backend app; echo '[project]' > backend/pyproject.toml; echo a > app/a.txt
  git add -A; git commit -qm init
  git init -q --bare "$R.remote"; git remote add origin "$R.remote"; git push -q origin main
}
expect() { # name expected_exit
  out=$(echo "{\"session_id\":\"case-$1\",\"stop_hook_active\":false}" | PATH="$S/fakebin:$PATH" CLAUDE_PROJECT_DIR="$R" TMPDIR="$R" "$HOOK" 2>&1); code=$?
  if [ "$code" = "$2" ]; then echo "PASS $1"; pass=$((pass+1)); else echo "FAIL $1 (exit $code, want $2)"; fail=$((fail+1)); fi
}
setup; expect clean-tree 0
setup; echo x > backend/new.py; expect untracked-backend-file 2
setup; git mv app/a.txt backend/a.py; expect staged-rename-into-backend 2
setup; mkdir -p "backend/with space"; echo x > "backend/with space/f.py"; expect path-with-space 2
setup; echo x > backend/c.py; git add -A; git commit -qm c; expect committed-on-main-not-pushed 2
setup; git checkout -qb feature; echo x > backend/d.py; git add -A; git commit -qm d; git branch -qD main 2>/dev/null; expect worktree-branch-without-local-main 2
setup; echo x > app/only.txt; expect app-only-change-skips-backend 0
echo "passed=$pass failed=$fail"
[ "$fail" = 0 ]
