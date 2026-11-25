# Local Codex provider

Choose **Local Codex (VS Code)** in AI Settings, then **Enable AI**. ArchFlow invokes the `codex` executable installed by the VS Code Codex extension using your existing ChatGPT login and model `gpt-6.1-terra`. No API key is needed. It creates a separate ephemeral CLI request; it does not send a message into an existing VS Code conversation. Inference still uses the remote Codex service and your account's usage limits.

Executable discovery uses PATH, then the VS Code/Insiders extension directories. Set `ARCHFLOW_CODEX_PATH` to the full `codex.exe` path if necessary. Run ArchFlow as the same Windows user that signed in to Codex. If authentication is missing, sign in to the extension or use `codex login`.

The session-protected local endpoint is `POST /api/codex` with JSON fields `folder`, `source`, `target`, optional `instructions`, and optional `constraint` (defaults to preserving existing code). Include the running app's `X-ArchFlow-Token` session header, as with other API endpoints. It returns a diff and proposal token; applying still requires `POST /api/ai/apply` with that proposal token. The normal `/api/ai` route also accepts provider `CodexLocal`, model `gpt-6.1-terra`, and a blank `api_key`.

Requests run in an isolated temporary working directory, use a read-only sandbox, disable shell and multi-agent tools, ignore user configuration, and time out after 180 seconds. Only one local request runs at a time. Project writes remain controlled by ArchFlow's preview, constraint checks and explicit Apply step. The bridge never reads or copies login credentials. Temporary response files are removed when the request ends.

Reference: [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive).
