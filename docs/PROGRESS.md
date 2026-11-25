# Hardening status

Phase 0: audit and headline regression completed. Before fix: regression returned
200 rather than 400. No evidence of automatic last-workspace loading was found.

Phase 1: foundation implemented: explicit empty state, creation, blank/source/home/
root rejection, active root, bounded cached text, binary/non-UTF-8 errors, root
gitignore rules. Still required: nested gitignore semantics, ignored-item toggle,
scan-truncation UI, sensitive system-directory prompts, complete collision tests.

Phase 2: foundation implemented: launch token, Host/Origin filtering, active root,
AI previews/approval/in-memory undo, sanitized errors, response cap, free port and
shutdown. Still required: retries/backoff, all request limits, persistent undo,
expiry-bound proposals and broader concurrency testing. Current test host alias
`testserver` is accepted for TestClient; remove it before a production release.

Phases 3–6 are not complete. Package extraction, strict typing, structured logs,
native main-thread fallback, uniform mutation/revision protocol, provider adapter
interfaces, UI virtualization/modules, structural undo/trash, comprehensive
pytest migration, 80% coverage, cross-platform CI, installer validation, license
selection and contributor/security documentation remain open.

Verification: local Python compilation; backend pytest suite; Ruff and baseline
mypy on changed backend modules; real local Edge empty-workspace regression.
These checks do not establish CI success, clean-machine installer behavior, full
browser regression success, or 80% backend coverage.

Manual checks: run `python main.py`; Open should show the native folder picker.
On unavailable picker, enter a dedicated project path. Create new workspace with
a parent and name. For a live AI request, choose provider/model, enter a key and
Enable AI; select a file edge and Run Wiring. Inspect the diff, cancel once to
verify no write, then apply a new preview. Verify auth/quota errors expose no key.
`POST /api/ai/undo` with the session header and folder/name reverses the last AI
write if no edits intervened. An undo UI is still required.
