"""
Tests d'intégration du RBAC avec l'API FastAPI.

Utilise le même pattern que test_api_auth.py — l'environnement est
configuré AVANT l'import de l'application.
"""

import os
import sys

# Configuration RBAC avec rôles avant l'import de l'app
os.environ["GALSEN_API_KEYS"] = "admin-key:admin,user-key:user,ro-key:readonly,op-key:operator"
os.environ["GALSEN_STORAGE_BACKEND"] = "in-memory"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fastapi.testclient import TestClient

# Import après configuration de l'environnement
from api.server import app

client = TestClient(app)


def test_health_no_key():
    """Les endpoints de santé sont publics."""
    resp = client.get("/health")
    assert resp.status_code == 200


def test_ready_no_key():
    """GET /ready ne nécessite pas de clé."""
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)


def test_live_no_key():
    """GET /live ne nécessite pas de clé."""
    resp = client.get("/live")
    assert resp.status_code == 200


# --- /auth/me ---

def test_auth_me_admin():
    """Admin peut consulter /auth/me."""
    resp = client.get("/auth/me", headers={"X-API-Key": "admin-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "admin"
    assert data["authenticated"] is True
    assert "admin:manage" in data["permissions"]


def test_auth_me_user():
    """User peut consulter /auth/me."""
    resp = client.get("/auth/me", headers={"X-API-Key": "user-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "user"
    assert "memory:write" in data["permissions"]
    assert "admin:manage" not in data["permissions"]


def test_auth_me_requires_key():
    """/auth/me nécessite une clé API."""
    resp = client.get("/auth/me")
    assert resp.status_code == 401


# --- Permissions TOOL_EXECUTE ---

def test_tool_execute_allowed_for_user():
    """User peut exécuter des outils."""
    resp = client.post(
        "/tool/execute",
        json={"tool_id": "filesystem", "input": {"operation": "list", "path": "."}},
        headers={"X-API-Key": "user-key"},
    )
    # Pas d'erreur d'auth — le code d'erreur dépend de l'initialisation du moteur
    assert resp.status_code not in (401, 403), f"{resp.status_code}: {resp.text}"


def test_tool_execute_forbidden_for_readonly():
    """Readonly ne peut pas exécuter d'outils (403)."""
    resp = client.post(
        "/tool/execute",
        json={"tool_id": "filesystem", "input": {"operation": "list", "path": "."}},
        headers={"X-API-Key": "ro-key"},
    )
    assert resp.status_code == 403


# --- Permissions APPROVAL ---

def test_approval_pending_allowed_for_readonly():
    """Readonly peut voir les approbations."""
    resp = client.get("/approval/pending", headers={"X-API-Key": "ro-key"})
    assert resp.status_code == 200


def test_approval_approve_forbidden_for_user():
    """User ne peut pas approuver (403)."""
    resp = client.post(
        "/approval/fake-id/approve", json={},
        headers={"X-API-Key": "user-key"},
    )
    assert resp.status_code == 403


def test_approval_approve_allowed_for_operator():
    """Operator peut approuver (409 car ID inexistant, pas 403)."""
    resp = client.post(
        "/approval/fake-id/approve", json={},
        headers={"X-API-Key": "op-key"},
    )
    assert resp.status_code == 409, f"{resp.status_code}: {resp.text}"


def test_approval_approve_allowed_for_admin():
    """Admin peut approuver (409 car ID inexistant, pas 403)."""
    resp = client.post(
        "/approval/fake-id/approve", json={},
        headers={"X-API-Key": "admin-key"},
    )
    assert resp.status_code == 409, f"{resp.status_code}: {resp.text}"


# --- Permissions ADMIN_AUDIT (endpoint /auth/roles) ---

def test_roles_endpoint_forbidden_for_operator():
    """Operator ne peut pas lister les rôles (403, ADMIN_MANAGE requis)."""
    resp = client.get("/auth/roles", headers={"X-API-Key": "op-key"})
    assert resp.status_code == 403, f"{resp.status_code}: {resp.text}"


def test_roles_endpoint_allowed_for_admin():
    """Admin peut lister les rôles."""
    resp = client.get("/auth/roles", headers={"X-API-Key": "admin-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert "admin" in data
    assert "user" in data


# --- Test mémoire avec rôle ---

def test_memory_store_with_valid_user_key():
    """User peut écrire en mémoire (pas 401/403)."""
    resp = client.post(
        "/memory/store",
        json={"content": "test", "memory_type": "short_term"},
        headers={"X-API-Key": "user-key"},
    )
    assert resp.status_code not in (401, 403), f"{resp.status_code}: {resp.text}"


def test_memory_store_forbidden_for_readonly():
    """Readonly ne peut pas écrire en mémoire (403)."""
    resp = client.post(
        "/memory/store",
        json={"content": "test", "memory_type": "short_term"},
        headers={"X-API-Key": "ro-key"},
    )
    assert resp.status_code == 403


# --- Test modèle avec rôle ---

def test_model_generate_allowed_for_user():
    """User peut générer du texte (pas 401/403)."""
    resp = client.post(
        "/model/generate",
        json={"prompt": "Hello"},
        headers={"X-API-Key": "user-key"},
    )
    assert resp.status_code not in (401, 403), f"{resp.status_code}: {resp.text}"


if __name__ == "__main__":
    # Exécution simple sans pytest
    import traceback
    tests = [
        name for name in dir() if name.startswith("test_")
    ]
    passed = 0
    for name in tests:
        func = globals()[name]
        try:
            func()
            print(f"PASS: {name}")
            passed += 1
        except Exception as e:
            print(f"FAIL: {name} - {e}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} tests passed.")