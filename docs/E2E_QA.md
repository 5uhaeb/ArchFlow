# TODO workspace UI verification

## Latest full rerun

The supplied OpenAI key was tested through the actual Enable AI button with gpt-6.1-terra. OpenAI returned HTTP 429; live OpenAI generation remains blocked, and this was not treated as a successful generation test. The user authorized using the local Codex Terra login for that step. A full rerun then created the TODO workspace through the UI, generated all three files with local gpt-6.1-terra, applied each preview explicitly, and verified adding, completing and deleting tasks in the generated app. No provider mocks were used for this final generation run.

The rerun reproduced and fixed a trash/legend overlap caused by later CSS overrides, wires hidden behind same-column nodes, incorrect Python defaults for web-file connections, stale AI Apply actions after changing instructions/settings, and missing Escape cancellation in the delete dialog. Answer cleanup now preserves blank prefixes for append-only files and embedded code fences. OpenAI requests now use the Responses endpoint and reject incomplete output; multi-part output and mixed source/target language hints are covered by regressions.

Real UI checks passed for creation visibility, Save, synchronized horizontal/vertical editor scrolling, gutter separation, highlighted text without markup leakage, wheel pan, Ctrl-wheel zoom, both themes, drag/click wiring, Delete/undo, wire cancellation, error/warning badges, trash drag, Escape cancellation, and confirmed subtree deletion. Pairwise control overlap and document overflow checks passed at 480, 700, 900 and 1400px viewport widths. Editor and canvas screenshots were visually inspected. There were zero JavaScript page errors in the final TODO run. Native OS dialog selection was substituted at the picker boundary; the Open button and subsequent workspace loading were real.

Final verification: 19 backend tests, Python compilation, Ruff, and the real browser regression suite passed. Temporary TODO projects, test harnesses, screenshots and credentials were excluded from the commit. These results cover exercised states, not an exhaustive proof that every possible UI state is bug-free.

## Earlier baseline

The real UI was exercised in headless Microsoft Edge (Chromium), using a temporary workspace outside this repository and the local app on port 8765. The Open button was clicked; only the native OS picker boundary returned the temporary directory programmatically. The OS dialog itself was not automated.

Passed: inline folder/file creation, starter edits and Save, double-click details and editor opening, synchronized long-line/vertical editor scrolling, theme switching, plain-wheel pan, Ctrl-wheel zoom, port drag/click connections, Delete/undo, Escape cancellation, AI task input, preview/Apply, and generated TODO add/complete/delete in a second browser page. No JavaScript page errors occurred. Overflow and trash/zoom intersection checks passed at viewport widths 1400, 700 and 480 pixels. These checks cover the exercised states, not every possible layout.

Live Gemini model discovery succeeded with the replacement temporary credential. Both requested gemini-2.0-flash and catalog-listed gemini-2.5-flash generation returned HTTP 404; gemini-3.8-flash and gemini-flash-latest returned HTTP 503. Generation succeeded with gemini-3.5-flash-lite. After initial mock-provider coverage, a complete separate live run created all three files via the UI, generated and applied each target through Run Wiring, and verified adding, completing and deleting TODOs in a second browser page. One live request returned HTTP 503 and succeeded on explicit retry. No credential or generated TODO project was saved in the repository.

Regression verification: Python compilation, Ruff, 14 backend tests, and the existing real browser regression suite passed. New regressions cover click wiring, cancellation, complete multi-part Gemini responses, rejection of truncated responses, and non-writing constraint previews. A single 1000-node render measured 69 ms; this is not a sustained frame-rate measurement.
