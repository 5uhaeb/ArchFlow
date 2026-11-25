from fastapi.testclient import TestClient
import main

def test_empty_workspace_does_not_mean_cwd():
    # Reproduces the root cause without touching the source checkout.
    with TestClient(main.app, headers={'x-archflow-token':main.SESSION_TOKEN}) as client:
        response = client.post('/api/files', json={'path': ''})
    assert response.status_code == 400

def test_session_security():
    with TestClient(main.app) as client:
        assert client.post('/api/files',json={'path':''}).status_code==401
        assert client.get('/',headers={'host':'evil.example'}).status_code==403
        assert client.post('/api/files',headers={'x-archflow-token':main.SESSION_TOKEN,'origin':'https://evil.example'},json={'path':''}).status_code==403

def test_create_dedicated_workspace(tmp_path):
    with TestClient(main.app, headers={'x-archflow-token':main.SESSION_TOKEN}) as client:
        r=client.post('/api/create-workspace',json={'parent':str(tmp_path),'name':'TO-DO-APP'})
        assert r.status_code==200
        listing=client.post('/api/files',json={'path':r.json()['path']})
        assert listing.json()['files']==[]
        client.post('/api/mkdir',json={'folder':r.json()['path'],'name':'only-node'})
        listing=client.post('/api/files',json={'path':r.json()['path']})
        assert [e['name'] for e in listing.json()['files']]==['only-node']
