"""Sonde de vérification de l'endpoint /agri/advice (temporaire)."""
import os
os.environ["GALSEN_API_KEYS"] = "test-key:user"

from fastapi.testclient import TestClient
from src.api import server

client = TestClient(server.app)

# 1. Question vide -> 422 attendu
r = client.post("/agri/advice", json={"question": "   "}, headers={"X-API-Key": "test-key"})
print("question vide ->", r.status_code, r.json())

# 2. Langue invalide -> 422 attendu
r = client.post("/agri/advice", json={"question": "Bonjour", "language": "xx"},
                headers={"X-API-Key": "test-key"})
print("langue invalide ->", r.status_code, r.json())

# 3. Clé absente -> 401 attendu
r = client.post("/agri/advice", json={"question": "Bonjour"})
print("sans clé ->", r.status_code, r.json())
