import io
import json
from unittest.mock import patch

import pytest

from ai_engine import _clean_answer, ask_ai, guard_update


def test_answer_preserves_blank_prefix_and_embedded_fences():
    code = '\n\nconst text = `example ```code``` string`;\n'
    assert _clean_answer(code) == code
    assert _clean_answer('```js\n\nconst x=1;\n```') == '\nconst x=1;\n'


def response(reason):
    return io.BytesIO(json.dumps({'candidates': [{'finishReason': reason, 'content': {'parts': [{'text': 'first\n'}, {'text': 'second\n'}]}}]}).encode())


def test_gemini_joins_parts():
    with patch('urllib.request.urlopen', return_value=response('STOP')):
        code, _ = ask_ai('a.js', '', 'b.js', '', 'APPEND_ONLY', 'test', 'test', 'Gemini')
    assert code == 'first\nsecond\n'


def test_openai_responses_collects_text_without_temperature():
    data = {'status': 'completed', 'output': [{'type': 'reasoning'}, {'type': 'message', 'content': [{'type': 'output_text', 'text': 'one\n'}, {'type': 'output_text', 'text': 'two\n'}]}]}
    with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(data).encode())) as call:
        code, _ = ask_ai('a.css', '/* source */', 'b.html', '', 'APPEND_ONLY', 'test', 'gpt-6.1-terra')
    assert code == 'one\ntwo\n'
    request = call.call_args.args[0]
    assert request.full_url.endswith('/v1/responses')
    payload = json.loads(request.data)
    assert 'temperature' not in payload
    assert '```css' in payload['input'] and '```html' in payload['input']


def test_openai_incomplete_response_is_rejected():
    with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"status":"incomplete","output":[]}')):
        with pytest.raises(ValueError, match='did not complete'):
            ask_ai('a.js', '', 'b.js', '', 'APPEND_ONLY', 'test', 'gpt-6.1-terra')


def test_gemini_rejects_truncated_response():
    with patch('urllib.request.urlopen', return_value=response('MAX_TOKENS')):
        with pytest.raises(ValueError, match='truncated'):
            ask_ai('a.js', '', 'b.js', '', 'APPEND_ONLY', 'test', 'test', 'Gemini')


def test_preview_checks_constraint_without_writing(tmp_path):
    target = tmp_path / 'a.js'
    target.write_text('// preserve\n', encoding='utf-8')
    assert not guard_update(target, '// replaced\n', 'ADD_AND_REWRITE_NO_DELETE', write=False)['ok']
    result = guard_update(target, '// preserve\nconst x=1;\n', 'ADD_AND_REWRITE_NO_DELETE', write=False)
    assert result['ok'] and not result['written']
    assert target.read_text(encoding='utf-8') == '// preserve\n'
