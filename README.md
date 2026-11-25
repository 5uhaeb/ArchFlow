# ArchFlow

Local Python desktop workspace wiring utility. Uses FastAPI, pywebview and vanilla HTML/CSS/JavaScript.

## Run

Production hardening is in progress; see [audit](docs/AUDIT.md) and
[verified progress / remaining work](docs/PROGRESS.md). This checkout is not yet
a validated production release. API calls now require a per-launch token, the
workspace must be opened explicitly, and AI writes require preview confirmation.

```sh
python -m pip install -r requirements.txt
python main.py
```

Open a project, create files/folders, connect output to input ports and run wiring. API keys stay in the current browser session. Custom providers accept a base URL including `/v1`. Review generated changes before using them. Preview Diff Only avoids writes. Preserve Existing Code retains every meaningful existing line, ignoring trailing whitespace.

The local server binds to 127.0.0.1:8765. Native window failures fall back to your browser. Workspace graph data is stored in `.archflow_graph.json`.

## Architecture workspace

UI controls have changed: single-click selects; double-click or Enter opens
Details, where Open in editor launches the file editor. Right-click wires for
actions. Delete/Backspace removes a selected manual connection or suppresses a
detected one. Ctrl/Cmd+Z undoes connection edits; Ctrl+Shift+Z redoes them.
AI opens the three-action panel; Enable AI now makes a provider validation
request. Ctrl/Cmd+K opens Commands and ? shows Help. About identifies this build.
See [UI pass scope and limitations](docs/UI_PROGRESS.md).

The canvas follows the architecture-board reference: a centered Workspace node feeds folder columns across a shared gray bus; each column stacks its files along a left hierarchy trunk. Nested folders retain indented subtrees within their column. Rounded nodes and four port dots share extension colors (Python blue, JSON pink, HTML orange, CSS purple, JavaScript gold). New users start in the dark theme; existing theme preferences remain respected. New workspaces fit automatically, while saved viewports are restored.

Folders form a centered, top-down tree. Use the chevron to collapse a folder; its functional connections remain stored. Nodes have four ports: drag any port to another node's port (24 world-unit snapping). A click pins the connection inspector; hover reveals incoming/outgoing relationships without expanding folders. Select a relationship to reveal its node. Delete/Backspace or right-click removes a selected functional wire. Ordinary structural branches cannot be removed.

Functional lines have arrows; solid lines are manual, dashed lines are detected. The collapsible legend provides type overrides: Python blue, JavaScript yellow, HTML orange, CSS purple, API/backend green, database teal, configuration pink, AI cyan, unresolved red, and other slate. Folder structure is gray. The inspector also names connection types and directions. Overrides convert detected edges to manual edges. Newly drawn edges use the selected legend type. Detection infers file-language types; API/backend and AI semantics require a manual override.

Plain wheel/trackpad pans; Shift+wheel pans horizontally; Ctrl/Cmd+wheel zooms at the cursor. Drag empty background to pan. Use Fit, Reset, Center Selected, or the minimap to navigate. All navigation is clamped to the visible tree with padding. At the minimum 35% zoom, very large trees may still require panning.

Select a folder before New File/New Folder to create within it. Enter accepts the inline name, Escape cancels. Drag a node's label (past a small movement threshold) onto a folder to move it on disk. Collapsed destinations expand after hovering briefly. Root accepts drops. Escape cancels dragging. Conflicts and descendant moves are rejected; existing contents are never overwritten. Affected unsaved editor buffers require confirmation and are kept after a move. ArchFlow warns about imports; it never silently rewrites code. Save edits before AI wiring; folders cannot be sent to AI.

## Dependency detection and storage

Python AST imports, JS/TS static imports/exports and literal require calls, HTML src/href references, and CSS imports/url references are scanned. Dynamic expressions, package-manager aliases, custom Python source roots, runtime imports and bundler resolution are not supported. Bare external package names are omitted. Missing explicit local references appear as unresolved relationships in the inspector; they do not create imaginary file nodes. Moves can invalidate references; inspect warnings and fix code yourself. Auto edges refresh on workspace load (including after saves/creation/moves); deleting an auto edge only lasts until the next scan. Manual edges persist independently.

Graph schema v2 stores typed manual/auto edges, port sides, collapsed paths, selection, viewport and a revision. Older source/target-only edges become manual right-to-left connections. Metadata writes use atomic replacement; stale revisions are rejected rather than overwriting newer moves. Ignored/internal directories and symlinks are excluded from scanning. API keys are never graph fields. Metadata-write failures during a move roll the filesystem move back; external programs changing the same files concurrently are outside this transaction.

## Verification

```sh
python -m py_compile main.py ai_engine.py workspace_graph.py
python -m unittest test_workspace -v
```

Backend tests need `httpx` in the test environment. Optional real interaction tests use Python Playwright and an installed Microsoft Edge: `python test_browser.py`. Neither is needed by the app. Tests use temporary mixed-language workspaces and cover actual moves, metadata migration, stale revisions, simulated failures, four-sided wiring, hover inspection, hidden-node reveal, viewport clamps, editor alignment, themes and persistence. The native folder picker and live paid AI requests require manual testing on the target desktop/provider.
