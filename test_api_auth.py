import os
import sys
from fastapi.testclient import TestClient

# Ensure the application can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variable for API keys before importing the app
os.environ["GALSEN_API_KEYS"] = "test-key-123,another-key"

from api.server import app, rbac_manager

# S'assurer que le RBACManager est synchronisé avec la variable d'environnement
# (nécessaire quand l'import a déjà eu lieu avec d'autres valeurs)
rbac_manager.reload()

client = TestClient(app)

def test_health_endpoint_no_auth():
    """Le endpoint /health doit être accessible sans clé API."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    # Le nouveau format retourne un rapport de santé complet
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "uptime" in data
    assert "components" in data

def test_memory_store_without_key():
    """Accessing protected endpoint without API key should return 401."""
    response = client.post("/memory/store", json={
        "content": "test",
        "memory_type": "short_term"
    })
    assert response.status_code == 401
    # Le message d'erreur est en français (Clé API manquante/invalide)
    detail = response.json().get("detail", "")
    assert "API" in detail and ("manquante" in detail or "invalide" in detail)

def test_memory_store_with_invalid_key():
    """Invalid API key should return 401."""
    response = client.post("/memory/store", json={
        "content": "test",
        "memory_type": "short_term"
    }, headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

def test_memory_store_with_valid_key():
    """Valid API key should allow access (may fail for other reasons, but not 401)."""
    response = client.post("/memory/store", json={
        "content": "test memory",
        "memory_type": "short_term"
    }, headers={"X-API-Key": "test-key-123"})
    # Might succeed (200) or fail due to missing dependencies (500), but should not be 401
    assert response.status_code != 401

def test_model_generate_with_valid_key():
    """Test model endpoint with valid key."""
    response = client.post("/model/generate", json={
        "prompt": "Hello"
    }, headers={"X-API-Key": "test-key-123"})
    # Expect not 401; could be 503 if no model loaded, but that's okay for auth test
    assert response.status_code != 401

def test_tool_execute_with_valid_key():
    """Test tool endpoint with valid key."""
    response = client.post("/tool/execute", json={
        "tool_id": "filesystem",
        "input": {"operation": "list", "path": "."}
    }, headers={"X-API-Key": "test-key-123"})
    assert response.status_code != 401

def test_knowledge_search_with_valid_key():
    """Test knowledge endpoint with valid key."""
    response = client.post("/knowledge/search", json={
        "query": "test",
        "limit": 5
    }, headers={"X-API-Key": "test-key-123"})
    assert response.status_code != 401

if __name__ == "__main__":
    # Simple test runner
    import traceback
    tests = [
        test_health_endpoint_no_auth,
        test_memory_store_without_key,
        test_memory_store_with_invalid_key,
        test_memory_store_with_valid_key,
        test_model_generate_with_valid_key,
        test_tool_execute_with_valid_key,
        test_knowledge_search_with_valid_key,
    ]
    passed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {test.__name__} - {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} tests passed.")