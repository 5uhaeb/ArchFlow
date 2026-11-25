"""Local bridge to the Codex CLI bundled with the VS Code extension."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

BUSY = threading.Lock()


def executable() -> str:
    override = os.environ.get('ARCHFLOW_CODEX_PATH')
    if override:
        path = Path(override)
        if path.is_file() and path.suffix.lower() == '.exe':
            return str(path.resolve())
        raise ValueError('ARCHFLOW_CODEX_PATH must point to codex.exe.')
    installed = shutil.which('codex.exe') or shutil.which('codex')
    if installed:
        return installed
    candidates = []
    for directory in ['.vscode', '.vscode-insiders']:
        candidates.extend((Path.home() / directory / 'extensions').glob('openai.chatgpt-*/bin/windows-*/codex.exe'))
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise ValueError('Codex was not found. Install the Codex VS Code extension or set ARCHFLOW_CODEX_PATH.')


def generate(prompt: str, model: str = 'gpt-6.1-terra') -> str:
    if model != 'gpt-6.1-terra':
        raise ValueError('The local Codex provider currently supports gpt-6.1-terra.')
    if not BUSY.acquire(blocking=False):
        raise ValueError('Local Codex is busy. Wait for the current request to finish.')
    try:
        binary = executable()
        with tempfile.TemporaryDirectory(prefix='archflow-codex-') as temp:
            output = Path(temp) / 'answer.txt'
            command = [binary, '--no-daemon', '-a', 'never', 'exec', '--ignore-user-config', '--ephemeral',
                       '--skip-git-repo-check', '--sandbox', 'read-only', '--disable', 'shell_tool',
                       '--disable', 'multi_agent', '--disable', 'multi_agent_v2',
                       '--model', model, '--color', 'never', '--output-last-message', str(output), '-']
            environment = {k: v for k, v in os.environ.items() if k not in {'OPENAI_API_KEY', 'GEMINI_API_KEY', 'ANTHROPIC_API_KEY', 'ARCHFLOW_TEST_KEY'}}
            result = subprocess.run(command, input='Use only the supplied text. Return the requested response without invoking tools.\n'+prompt,
                                    cwd=temp, env=environment, text=True, encoding='utf-8', errors='replace',
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=180, check=False,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                error = result.stderr.lower()
                if any(word in error for word in ('unauthorized', 'not logged in', '401', 'authentication')):
                    raise ValueError('Codex login is required. Sign in to Codex in VS Code or run codex login as your Windows user.')
                if any(word in error for word in ('rate limit', 'usage limit', 'quota')):
                    raise ValueError('Codex usage limit reached. Check your ChatGPT plan limits.')
                raise ValueError('Local Codex failed. Check that GPT-6.1 Terra is available in your Codex account and that the extension is updated.')
            if not output.is_file() or output.stat().st_size > 2 * 1024 * 1024:
                raise ValueError('Codex returned no response or exceeded the response size limit.')
            answer = output.read_text(encoding='utf-8')
            if not answer.strip():
                raise ValueError('Codex returned an empty response.')
            return answer
    except subprocess.TimeoutExpired:
        raise ValueError('Local Codex timed out after 180 seconds. Try a smaller task.') from None
    except OSError:
        raise ValueError('Unable to start Codex. Check the installed extension and ARCHFLOW_CODEX_PATH.') from None
    finally:
        BUSY.release()
