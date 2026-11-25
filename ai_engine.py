"""Small, dependency-free AI request and guarded file-update helpers."""
from __future__ import annotations

import difflib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _clean_answer(text: str) -> str:
    """Accept a complete source file, optionally surrounded by a Markdown fence."""
    match = re.fullmatch(r'\s*```[^\n]*\n(.*?)```\s*', text, re.DOTALL)
    code = match.group(1) if match else text
    return code if code.endswith('\n') else code + '\n'


def ask_ai(source_name: str, source: str, target_name: str, target: str,
           constraint: str, api_key: str, model: str, provider: str = "OpenAI", base_url: str = "", instruction: str | None = None, request_notes: str = '') -> tuple[str, str]:
    extension = Path(target_name).suffix.lstrip(".") or "text"
    source_extension = Path(source_name).suffix.lstrip('.') or 'text'
    prompt = f"""You are wiring source files. Source ({source_name}):
```{source_extension}
{source}
```
Target ({target_name}):
```{extension}
{target}
```
Constraint: {constraint}. Return ONLY the complete proposed target file in its original language, no explanation or markdown. Preserve Existing Code requires every original nonblank line in order; Append Only requires the original content as an exact prefix."""
    if provider != 'CodexLocal' and not api_key.strip():
        raise ValueError("Enter an API key before running AI.")
    if instruction is not None:
        prompt = instruction + '\nInput:\n' + source
    elif request_notes.strip():
        prompt += '\nUser task (obey the constraint above):\n' + request_notes[:8000]
    if provider == 'CodexLocal':
        from codex_local import generate
        return _clean_answer(generate(prompt, model)), 'Local Codex proposed a guarded update using GPT-6.1 Terra.'
    payload: dict[str, Any]
    if provider == "Gemini":
        url = "https://generativelanguage.googleapis.com/v1beta/models/" + model.removeprefix('models/') + ":generateContent"
        payload = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 8192}}
        header = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        extractor = lambda d: ''.join(p['text'] for p in d['candidates'][0]['content']['parts'] if 'text' in p and not p.get('thought'))
    elif provider == "Claude":
        url = "https://api.anthropic.com/v1/messages"
        payload = {"model": model, "max_tokens": 8192, "messages": [{"role": "user", "content": prompt}]}
        header = {"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
        extractor = lambda d: "".join(p["text"] for p in d["content"] if p.get("type") == "text")
    elif provider == 'OpenAI':
        url = 'https://api.openai.com/v1/responses'
        payload = {'model': model, 'input': prompt, 'max_output_tokens': 8192}
        header = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key}
        extractor = lambda d: ''.join(part['text'] for item in d['output'] if item.get('type') == 'message' for part in item.get('content', []) if part.get('type') == 'output_text')
    else:
        url = "https://api.openai.com/v1/chat/completions"
        if provider == "Custom": url = base_url.rstrip("/") + "/chat/completions"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        header = {"Content-Type": "application/json", "Authorization": "Bearer " + api_key}
        extractor = lambda d: d["choices"][0]["message"]["content"]
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=header)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024: raise ValueError('Provider response exceeds size limit.')
            data = json.loads(raw.decode())
            if provider == 'OpenAI' and data.get('status') != 'completed':
                raise ValueError('OpenAI did not complete the response. Reduce the task or retry; no files were changed.')
            reason = data.get('candidates', [{}])[0].get('finishReason') if provider == 'Gemini' else data.get('stop_reason') if provider == 'Claude' else data.get('choices', [{}])[0].get('finish_reason')
            if reason in {'MAX_TOKENS', 'max_tokens', 'length'}:
                raise ValueError('Provider truncated the generated code. Reduce the task size and generate again; no files were changed.')
            if provider == 'Gemini' and reason not in {None, 'STOP'}:
                raise ValueError('Provider did not complete the response. Revise the task and try again.')
            answer = extractor(data)
            if not isinstance(answer, str) or not answer.strip(): raise TypeError('Provider did not return text.')
    except urllib.error.HTTPError as exc:
        message = "Rate limit or API quota reached." if exc.code == 429 else "API key was rejected or does not have access." if exc.code in {401, 403} else f"Provider returned HTTP {exc.code}."
        if exc.code == 429:
            try:
                error = json.loads(exc.read(16384)).get('error', {})
                code = error.get('code') if isinstance(error, dict) else None
            except (OSError, ValueError, AttributeError):
                code = None
            if code == 'insufficient_quota':
                message = 'OpenAI API quota is exhausted. Check project billing and usage limits before retrying.'
            elif code == 'rate_limit_exceeded':
                message = 'OpenAI request rate limit reached. Wait before retrying.'
        if exc.code == 404:
            message = f"{provider}: model '{model}' was not found or is unavailable for this API key. Choose another model."
            if provider == 'Custom':
                message += ' Also check the custom API base URL.'
        elif exc.code in {500, 502, 503, 504}:
            message = f'{provider} is temporarily unavailable (HTTP {exc.code}). Try again or choose another model.'
        raise ValueError(message) from None
    except (urllib.error.URLError, KeyError, IndexError, TypeError, UnicodeError, TimeoutError, OSError, json.JSONDecodeError):
        raise ValueError('Provider request failed or returned malformed data. Check connectivity and provider settings.') from None
    return _clean_answer(answer), "AI proposed a complete guarded target-file update."


def available_models(api_key: str) -> list[str]:
    """Fetch Gemini's current catalog rather than relying on retired model names."""
    if not api_key.strip():
        raise ValueError('Enter an API key first.')
    url = 'https://generativelanguage.googleapis.com/v1beta/models'
    models = []
    try:
        for _ in range(10):
            request = urllib.request.Request(url, headers={'x-goog-api-key': api_key})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read(2 * 1024 * 1024))
            models.extend(m['name'].removeprefix('models/') for m in data.get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', []))
            token = data.get('nextPageToken')
            if not token:
                return sorted(set(models))
            from urllib.parse import quote
            url = 'https://generativelanguage.googleapis.com/v1beta/models?pageToken=' + quote(token, safe='')
    except urllib.error.HTTPError as exc:
        raise ValueError(f'Gemini model catalog returned HTTP {exc.code}. Check API key access.') from None
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError('Could not load Gemini models. Check connectivity and try again.') from None
    return sorted(set(models))


def _nonblank_subsequence(old: list[str], new: list[str]) -> bool:
    """Every pre-existing meaningful line must remain, in order."""
    meaningful = [line.rstrip() for line in old if line.strip()]
    iterator = iter(line.rstrip() for line in new)
    return all(any(candidate == line for candidate in iterator) for line in meaningful)


def guard_update(path: Path, proposed: str, constraint: str, write: bool = True) -> dict:
    if constraint not in {"SUGGEST_ONLY", "APPEND_ONLY", "ADD_AND_REWRITE_NO_DELETE"}:
        raise ValueError("Unknown constraint.")
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
    if write:
        path.write_text(proposed, encoding="utf-8")
        result["written"] = True
    return result
