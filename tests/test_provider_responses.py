import io
import json
from unittest.mock import patch

import pytest

from ai_engine import ask_ai, guard_update


def response(reason):
    return io.BytesIO(json.dumps({'candidates': [{'finishReason': reason, 'content': {'parts': [{'text': 'first\n'}, {'text': 'second\n'}]}}]}).encode())


def test_gemini_joins_parts():
    with patch('urllib.request.urlopen', return_value=response('STOP')):
        code, _ = ask_ai('a.js', '', 'b.js', '', 'APPEND_ONLY', 'test', 'test', 'Gemini')
    assert code == 'first\nsecond\n'


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
