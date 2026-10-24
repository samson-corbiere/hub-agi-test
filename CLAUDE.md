# CaptureKit

Spec: issue #1. Every product decision is settled there; read it before deciding anything about format, API or behaviour.

## Boundaries

- Each ticket belongs to one track: `app/` or `backend/`. Stay inside your track's folder.
- `contract/` and `docs/api-contract.md` are owner-only. Build against them as written; if one looks wrong, stop and ask the owner.
- React Native renders UI only. Video bytes, IMU samples, file state and uploads live in Swift.

## Working rules

- TDD, red first: write the test, run it, see it fail for the right reason, then make it pass.
- Test through the seam, never internals: the HTTP API for `backend/`, the public API of `CaptureCore` (with fake `Transport` and `Clock`) for the app.
- Logic goes in `CaptureCore` (pure Swift). Native glue (AVFoundation, CoreMotion, URLSession, Expo bridge) stays thin enough to need no logic tests.
- A task is done only when the `Stop` hook's checks pass. Report failures as failures.
- Repo artifacts (code, docs, issues, commits) are in English.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on samson-corbiere/hub-agi-test (via `gh`). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one root `GLOSSARY.md` plus `docs/adr/`. See `docs/agents/domain.md`.
