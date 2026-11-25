"""Small, dependency-free AI request and guarded file-update helpers."""
from __future__ import annotations

import difflib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


def _clean_answer(text: str) -> str:
    """Accept a full Python file, optionally surrounded by a Markdown fence."""
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.S | re.I)
    return (match.group(1) if match else text).strip("\n") + "\n"


def ask_ai(source_name: str, source: str, target_name: str, target: str,
           constraint: str, api_key: str, model: str, provider: str = "OpenAI", base_url: str = "") -> tuple[str, str]:
    extension = Path(target_name).suffix.lstrip(".") or "text"
    prompt = f"""You are wiring source files. Source ({source_name}):
```{extension}
{source}
```
Target ({target_name}):
```{extension}
{target}
```
Constraint: {constraint}. Return ONLY the complete proposed target Python file, no explanation or markdown. Make it useful while honoring the constraint."""
    if not api_key.strip():
        raise ValueError("Enter an API key before running AI.")
    if provider == "Gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + api_key
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        header = {"Content-Type": "application/json"}
        extractor = lambda d: d["candidates"][0]["content"]["parts"][0]["text"]
    elif provider == "Claude":
        url = "https://api.anthropic.com/v1/messages"
        payload = {"model": model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}]}
        header = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
        extractor = lambda d: "".join(p["text"] for p in d["content"] if p.get("type") == "text")
    else:
        url = "https://api.openai.com/v1/chat/completions"
        if provider == "Custom": url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        header = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
        extractor = lambda d: d["choices"][0]["message"]["content"]
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=header)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            answer = extractor(json.loads(response.read().decode()))
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise ValueError(f"AI request failed: {exc}") from exc
    return _clean_answer(answer), "AI proposed a complete guarded target-file update."


def _nonblank_subsequence(old: list[str], new: list[str]) -> bool:
    """Every pre-existing meaningful line must remain, in order."""
    meaningful = [line.rstrip() for line in old if line.strip()]
    iterator = iter(line.rstrip() for line in new)
    return all(any(candidate == line for candidate in iterator) for line in meaningful)


def guard_update(path: Path, proposed: str, constraint: str) -> dict:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    old, new = original.splitlines(), proposed.splitlines()
    diff = "\n".join(difflib.unified_diff(old, new, fromfile=path.name, tofile=path.name + " (proposed)", lineterm=""))
    added = sum(1 for line in difflib.ndiff(old, new) if line.startswith("+ "))
    modified = sum(1 for tag, _, _, _, _ in difflib.SequenceMatcher(None, old, new).get_opcodes() if tag == "replace")
    result = {"ok": True, "written": False, "added": added, "modified": modified, "diff": diff}
    if constraint == "SUGGEST_ONLY":
        return result
    if constraint == "APPEND_ONLY" and not proposed.startswith(original):
        return {**result, "ok": False, "error": "APPEND_ONLY rejected: original file must be an exact prefix."}
    if constraint == "ADD_AND_REWRITE_NO_DELETE" and not _nonblank_subsequence(old, new):
        return {**result, "ok": False, "error": "No-delete guard rejected: an existing non-empty line was removed or changed."}
    path.write_text(proposed, encoding="utf-8")
    result["written"] = True
    return result
