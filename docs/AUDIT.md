# Phase 0 audit — 2026-11-25

The headline's underlying backend failure is reproducible: `project('')` calls
`Path('').resolve()`, which resolves to the launch working directory. With
`python main.py` run from this checkout, `/api/files` consequently exposes the
application sources. Selecting the checkout explicitly has the same effect.
No automatic last-workspace loading was found in the frontend. Creating a folder
alone does not explain a twelve-file graph: empty-path resolution or an explicit
source-folder selection is required. The exact original click sequence is not
available; this distinction is important.

Ranked findings (line references refer to the pre-change checkout):

1. Critical: `main.py:24-27` accepts blank paths as cwd; each API chooses an
   arbitrary root independently. No opened-workspace session exists.
2. Critical: `main.py:18,54-155` has no token/Host/Origin checks. Local web pages
   can attempt file mutations against the server.
3. High: `main.py:110-119` applies AI directly, with no confirmation or undo.
4. High: `ai_engine.py:63-69` returns raw provider errors, potentially exposing
   keys in URLs or echoed provider data. Response reads are unbounded.
5. High: `workspace_graph.py:64-104` reads arbitrary-size text during detection;
   `.gitignore` is not respected. `main.py:57-65` rereads all files for diagnostics.
6. High: `workspace.js:12-35` stacks all root files in one column; Fit is clamped
   to 35%, so very tall repositories cannot fit.
7. Medium: `workspace_graph.py:110-117` cached detection never invalidates on
   external edits. `main.py:92-94` mkdir does not refresh graph state.
8. Medium: `main.py:128-139` tkinter fallback runs in a request worker thread.
   `main.py:123,164-175` fixes the port and does not coordinate shutdown.
9. Medium: `workspace.js` contains duplicate AI action handlers, mutable globals,
   and `Enable AI` marks a key ready without a provider validation request.
10. Medium: `test_browser.py:18-27` assumes installed Edge, manipulates collapsed
    AI controls without opening them, and uses fixed sleeps; prior output did
    not establish that this entire suite actually finished.
11. Medium: requirements have no compatible upper bounds, no package/CI/build
    configuration, no license decision, and no coverage measurement.

Regression: `tests/test_workspace_scope.py` must fail before the blank-path fix.
Existing protections worth retaining: atomic v2 metadata replacement, path
resolution checks, revision rejection, move rollback, and AI line guards.
