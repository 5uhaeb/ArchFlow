# UI reliability pass: verified scope and remaining work

Phase 0: reproduced duplicate pair/port identity failures before fixing. Existing
Delete handlers were present but undiscoverable; array indices and detected
refresh behavior caused inconsistency. Labels already included paths, contrary
to the report; labels now have explicit direction/type/origin in Details.

Phase 1: canonical normalized source/target/type identities, map-based merging,
stable IDs, manual/detected/both origins, suppression on detection refresh,
duplicate migration with original metadata backup. v2 edges remain a serialized
list for compatibility; identities/maps are used during normalization/rendering.

Phases 2–3: stable canvas selection, selected endpoints override hover dimming,
empty-canvas deselection, right-click action menu, delete/restore, bounded
connection undo/redo, double-click/Enter details with full paths, size/time,
diagnostics and connection actions. Single-click selects; editor opens from
Details. Existing hover inspector remains separate for quick discovery.

Phases 4–5: AI toolbar panel with Wire/update, Explain and Suggest. Explicit
credential test on Enable AI; sanitized provider errors; per-suggestion accept /
dismiss. Diff Apply/Discard is explicit. Commands (Ctrl/Cmd+K), help (?), status
line, log toggle, About version/checkout commit, tooltips and keyboard focus.

Phase 6 remains partial: history covers connections, not file mutations or AI
applications. AI undo remains a backend session operation. Rename/trash/delete
file actions, a shared transaction-based file history, full command coverage,
coach-mark tour, instruction input for wire changes and all-action accessibility
are not implemented. Do not describe this pass as meeting every acceptance item.
Saved status acknowledges successful graph writes; it is not a crash-proof
write-ahead journal. Suppression remains per canonical connection type.

Tests: backend regressions + lint/baseline typing; real local Edge tests for
duplicate gestures, delete/undo/redo, selection, Details/editor, commands,
suppression, mocked AI validation/explanation/suggestions, and 1000-node render.
No live AI key was used. Native dialog and actual provider behavior need manual
verification. The default optional runner uses Playwright Chromium; local checks
may use ARCHFLOW_BROWSER_CHANNEL=msedge.

Manual: open a dedicated folder; wire two ports twice; select the single wire,
Delete, Ctrl+Z, Ctrl+Shift+Z. Double-click or press Enter on a selected node;
review paths and connections, then Open in editor. AI → Set up AI → credentials
→ Enable AI (one provider request). Run a two-file preview; Discard first, then
generate another and Apply. Check constraints and source files afterward.
