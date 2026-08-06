"""
Interface web de la plateforme GalSen IA.

Client web sans étape de construction : HTML, CSS et modules JavaScript servis
tels quels par l'application FastAPI (ADR-008). Rien à installer, rien à
compiler — `uvicorn src.api.server:app` suffit à servir l'interface.

Le répertoire `static/` contient l'intégralité du client. `api_client.js` est le
seul module qui connaisse les routes de l'API : les pages ne font jamais d'appel
réseau elles-mêmes, ce qui garde le frontend indépendant des détails du backend
(VOLET 02, chapitre 02).
"""

import os

# Répertoire des fichiers servis, résolu depuis ce module pour ne dépendre
# d'aucun répertoire de travail courant.
STATIC_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# Préfixe sous lequel l'interface est servie.
UI_PREFIX = "/ui"

__all__ = ["STATIC_DIRECTORY", "UI_PREFIX"]
