from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_agent_context_is_versioned_and_contains_semantic_evidence():
    response = client.post("/api/v1/agent/context", json={
        "query": "What calls helper?",
        "files": [{"path": "src/service.py", "content": '''
def run(value):
    return helper(value)

def helper(value):
    return value
'''}],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["schema_version"] == "1.0"
    assert data["provenance"]["content_retention"] == "request-only"
    assert any(symbol["name"] == "run" for symbol in data["symbols"])
    assert any(relation["type"] == "calls" for relation in data["relations"])
    assert "issues" in data["audit"]


def test_strict_profile_rejects_unsupported_extensions():
    response = client.post("/api/v1/graph/local", json={
        "profile": "strict",
        "files": [{"path": "notes.txt", "content": "not source"}],
    })
    assert response.status_code == 422
