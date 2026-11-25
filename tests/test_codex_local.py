from fastapi.testclient import TestClient

import main


def test_local_endpoint_previews_then_applies(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_text('source\n', encoding='utf-8')
    target = tmp_path / 'b.txt'
    target.write_text('keep\n', encoding='utf-8')
    calls = []

    def generate(prompt, model):
        calls.append((prompt, model))
        return 'keep\nadded\n'

    monkeypatch.setattr('codex_local.generate', generate)
    monkeypatch.setattr(main, 'ACTIVE_ROOT', None)
    client = TestClient(main.app, headers={'X-ArchFlow-Token': main.SESSION_TOKEN})
    assert client.post('/api/files', json={'path': str(tmp_path)}).status_code == 200
    response = client.post('/api/codex', json={'folder': str(tmp_path), 'source': 'a.txt', 'target': 'b.txt', 'instructions': 'Add one line.'})
    assert response.status_code == 200
    result = response.json()
    assert result['ok'] and not result['written'] and result['proposal']
    assert target.read_text(encoding='utf-8') == 'keep\n'
    assert calls[0][1] == 'gpt-6.1-terra' and 'Add one line.' in calls[0][0]
    assert client.post('/api/ai/apply', json={'proposal': result['proposal']}).json()['written']
    assert target.read_text(encoding='utf-8') == 'keep\nadded\n'


def test_local_endpoint_requires_session_token():
    assert TestClient(main.app).post('/api/codex', json={}).status_code == 401
