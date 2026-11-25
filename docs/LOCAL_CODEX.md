# Local Codex provider

Open **ChatGPT Connection** and click **Connect ChatGPT**. ArchFlow reuses your Codex ChatGPT sign-in or launches Codex's browser login and waits for completion. It invokes the extension's bundled `codex` executable using model `gpt-6.1-terra`. No API-key/provider settings are exposed, and backend AI requests always use this subscription route. It creates a separate ephemeral CLI request; it does not send a message into an existing VS Code conversation. Inference still uses the remote Codex service and your account's usage limits.

Executable discovery uses PATH, then the VS Code/Insiders extension directories. Set `ARCHFLOW_CODEX_PATH` to the full `codex.exe` path if necessary. Run ArchFlow as the same Windows user that signed in to Codex. If authentication is missing, sign in to the extension or use `codex login`.

The app's session-protected local backend uses `POST /api/chatgpt/connect` and `/api/chatgpt/status` to manage sign-in. `POST /api/codex` accepts `folder`, `source`, `target`, optional `instructions`, and optional `constraint` (defaults to preserving existing code). Include the running app's `X-ArchFlow-Token` session header. It returns a diff and proposal token; applying still requires `POST /api/ai/apply` with that token. The normal `/api/ai` route also uses ChatGPT exclusively; it does not accept credentials or provider selection. These local application endpoints remain necessary for the desktop UI; there is no user-supplied paid API integration.

Requests run in an isolated temporary working directory, use a read-only sandbox, disable shell and multi-agent tools, ignore user configuration, and time out after 180 seconds. Only one local request runs at a time. Project writes remain controlled by ArchFlow's preview, constraint checks and explicit Apply step. The bridge never reads or copies login credentials. Temporary response files are removed when the request ends.

Reference: [Codex non-interactive mode](https://developers.openai.com/codex/noninteractive).

Verified: existing ChatGPT login, key-free live generation, unchanged target before Apply, explicit Apply, zero JavaScript errors, and browser regression coverage with no API-key controls. Browser sign-in for a signed-out account is implemented but was not exercised by signing the user's existing account out.
