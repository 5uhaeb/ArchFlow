# Changelog

## 0.3.0-dev — UI reliability

- Stable canonical edge IDs; duplicate origin/port records merge. Original
  duplicate metadata is backed up before migration; schema v2 stays readable.
- Selection and dimming use edge IDs, manual deletion/detected suppression,
  bounded connection undo/redo, context menu, double-click/Enter Details.
- AI validation, explanation and reviewable connection suggestions; explicit
  preview Apply/Discard; command palette, Help, status/log toggle and About.
- Single-click selects rather than opening the editor; use Details → Open in
  editor. Optional browser tests no longer execute during pytest collection.
- Windows CRLF source buffers no longer appear modified immediately after opening.
- File-action undo/redo and other unfinished scope is listed in docs/UI_PROGRESS.md.

## Unreleased — hardening foundation

- Audit and failing regression establish that a blank workspace path resolved
  to cwd; blank/source/home/root paths are now rejected.
- Fresh launch has an empty state; dedicated workspace creation is explicit.
- Bounded cached UTF-8 reads, binary rejection and root `.gitignore` filtering.
- Per-launch API token, Host/Origin checks and opened-root enforcement.
- AI requests produce a diff proposal; writing requires confirmation. In-memory
  undo rejects subsequent user modifications. Proposals and undo expire on exit.
- Provider error details are sanitized; oversized responses are rejected.
- Port selection can fall back to a free port; desktop close stops the server.
- Unsafe worker-thread tkinter fallback removed. In browser mode enter a path
  manually if the native folder picker is unavailable.

This is not yet the complete production-hardening release. See docs/PROGRESS.md.
