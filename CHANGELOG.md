# Changelog

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
