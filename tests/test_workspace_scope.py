from fastapi.testclient import TestClient
import main

def test_empty_workspace_does_not_mean_cwd():
    # Reproduces the root cause without touching the source checkout.
    with TestClient(main.app) as client:
        response = client.post('/api/files', json={'path': ''})
    assert response.status_code == 400
