import os
import sys

import pytest
from fastapi.testclient import TestClient

# Ensure the application can be imported
sys.path.insert(0, os.path.dirname(__file__))

os.environ["GALSEN_API_KEYS"] = "test-key-123,another-key"

import src.api.server as serveur
from src.api.server import app
from src.api.rate_limiter import set_valid_api_key_digests

client = TestClient(app)


@pytest.fixture(autouse=True)
def cles_actives():
    """Garantit les clés de ce fichier pendant chaque test, puis rend l'état.

    Recharger à l'import ne suffit pas : le gestionnaire RBAC est partagé par
    tout le processus, et n'importe quelle suite exécutée ensuite peut le
    recharger avec d'autres clés. Ce fichier obtenait alors des 401 sur des
    clés qu'il venait de déclarer — un échec qui n'apparaissait qu'en suite
    complète, jamais isolément.
    """
    # `serveur.rbac_manager` et non le nom importé : `importlib.reload()` d'une
    # autre suite remplace l'objet dans le module, et les routes consultent
    # celui du module. Recharger l'ancien laissait l'application authentifier
    # avec un gestionnaire que ce fichier ne configurait plus.
    gestionnaire = serveur.rbac_manager
    ancien_mapping = dict(gestionnaire._key_role_map)
    anciennes_revocations = set(gestionnaire._revoked_digests)

    os.environ["GALSEN_API_KEYS"] = "test-key-123,another-key"
    gestionnaire.reload()
    set_valid_api_key_digests(gestionnaire.active_key_digests())

    yield

    gestionnaire._key_role_map = ancien_mapping
    gestionnaire._revoked_digests = anciennes_revocations
    set_valid_api_key_digests(gestionnaire.active_key_digests())

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