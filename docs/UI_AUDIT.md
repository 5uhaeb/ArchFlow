# UI audit

Baseline: 132ecbe (local); last previously published build: 3e4e0fb.
The baseline had no version/About display. A running process can retain older
assets; this audit does not assume a previously launched window is current.

- Duplicate root cause: workspace_graph.normalize keyed by source, target,
  source/target ports AND origin. Thus detected/manual pairs and port variations
  were distinct. Frontend complete() checked ports; /api/edge checked a different
  pair/origin combination; refresh concatenated lists. New failing tests cover
  the inconsistency using requirements.txt -> app.py.
- Deletion handlers DO exist: workspace.js removeWire, window keydown and
  wire.oncontextmenu. They used mutable array indices. Inspector offered no
  delete controls. Detected edges could reappear after a rescan. Editor focus
  correctly excluded Delete to protect text; right click deleted immediately
  rather than opening a discoverable menu.
- Inspector labels already contained full relative paths plus a type string;
  the assertion that target was literally replaced by 'python' is not reproduced
  in this checkout. Compact mixed labels and no headings made them ambiguous.
- Dimming depends on hovered, independent of selected edge; pinned hover could
  leave selection faded. Hover timer and pinned state were not cleared on delete.
- Single click directly opened the editor, preventing a predictable selection /
  double-click-details distinction. Graph selection had no bounded undo history.

Before fixes: tests/test_edge_identity.py must fail all three regressions.
