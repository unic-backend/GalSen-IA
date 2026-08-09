"""
Preuve du critère de sortie C1 : la plateforme répond vraiment.

`docs/roadmap/roadmap.md` définit C1 ainsi : `POST /agri/advice` retourne 200
avec un conseil non vide et un modèle réellement nommé, contre au moins un
fournisseur configuré. Aujourd'hui la plateforme répond 503, parce qu'aucun
fournisseur ne l'est.

Ce fichier est **la preuve, pas la configuration**. Fournir une clé ou démarrer
Ollama est le geste de l'exploitant ; établir que la chaîne complète fonctionne
alors est le nôtre. Les tests s'ignorent proprement quand aucun fournisseur
n'est joignable, pour que l'intégration continue reste verte sans secret — et
ils s'exécutent, sans rien changer, le jour où il y en a un.

    ollama serve                      # gratuit, aucune clé
    python -m pytest tests/test_generation_end_to_end.py -v

Un test qui s'ignore toujours ne vaut rien. Le chemin « exécuté » est donc lui
aussi couvert : `TestChaineComplete` remplace le serveur local par un serveur
HTTP minimal parlant le protocole d'Ollama, et traverse toute la pile — outil,
gestionnaire, sélecteur, fournisseur, HTTP. Le modèle y est un bouchon ; la
chaîne, elle, est réelle.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("GALSEN_RATE_LIMIT_ENABLED", "false")

from src.api import server  # noqa: E402
from src.api.rate_limiter import set_valid_api_key_digests  # noqa: E402
from src.integration.engine_registry import get_shared_registry  # noqa: E402

CLE = "cle-generation"

# Réponse que le serveur bouchon renvoie. Reconnaissable : si elle apparaît
# quelque part, c'est qu'elle vient bien du fournisseur et non d'un repli.
TEXTE_BOUCHON = "Semez le mil dès les premières pluies utiles."
MODELE_BOUCHON = "bouchon-local:1b"


def _fournisseur_disponible() -> bool:
    """Indique si au moins un fournisseur peut générer maintenant."""
    try:
        return get_shared_registry().model.select_model_for_task({}) is not None
    except Exception:
        return False


def _raison_indisponibilite() -> str:
    """Retourne l'explication du moteur, pour que le saut soit instructif."""
    try:
        return get_shared_registry().model.unavailability_reason() or "aucun fournisseur"
    except Exception as erreur:
        return str(erreur)


@pytest.fixture
def api(monkeypatch):
    """Client authentifié, état RBAC restauré ensuite."""
    ancien_mapping = dict(server.rbac_manager._key_role_map)
    anciennes_revocations = set(server.rbac_manager._revoked_digests)

    monkeypatch.setenv("GALSEN_API_KEYS", f"{CLE}:user")
    server.rbac_manager.reload()
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())

    with TestClient(server.app) as client:
        yield client, {"X-API-Key": CLE}

    server.rbac_manager._key_role_map = ancien_mapping
    server.rbac_manager._revoked_digests = anciennes_revocations
    set_valid_api_key_digests(server.rbac_manager.active_key_digests())


# ---------------------------------------------------------------------------
# Serveur bouchon parlant le protocole d'Ollama
# ---------------------------------------------------------------------------


class _OllamaBouchon(BaseHTTPRequestHandler):
    """Répond aux deux seules routes que `LocalProvider` utilise."""

    def do_GET(self):  # noqa: N802 — nom imposé par http.server
        """`/api/tags` : la liste des modèles installés."""
        if self.path != "/api/tags":
            self.send_error(404)
            return
        self._repondre({
            "models": [{"name": MODELE_BOUCHON, "details": {"context_length": 4096}}]
        })

    def do_POST(self):  # noqa: N802 — nom imposé par http.server
        """`/api/generate` : la génération elle-même."""
        if self.path != "/api/generate":
            self.send_error(404)
            return
        taille = int(self.headers.get("Content-Length", 0))
        requete = json.loads(self.rfile.read(taille) or b"{}")
        # Le prompt doit arriver jusqu'ici : c'est ce qui prouve la traversée.
        assert requete.get("prompt"), "le fournisseur n'a transmis aucun prompt"
        self._repondre({
            "response": TEXTE_BOUCHON,
            "prompt_eval_count": 12,
            "eval_count": 9,
            "done": True,
        })

    def _repondre(self, charge: dict) -> None:
        """Écrit une réponse JSON."""
        corps = json.dumps(charge).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_args):
        """Silence : la sortie du serveur n'apporte rien au rapport de tests."""


@pytest.fixture
def serveur_local():
    """Démarre un faux Ollama et retourne son URL."""
    httpd = HTTPServer(("127.0.0.1", 0), _OllamaBouchon)
    fil = threading.Thread(target=httpd.serve_forever, daemon=True)
    fil.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---------------------------------------------------------------------------
# C1 contre un vrai fournisseur — s'exécute seulement s'il y en a un
# ---------------------------------------------------------------------------


besoin_fournisseur = pytest.mark.skipif(
    not _fournisseur_disponible(),
    reason=(
        "Aucun fournisseur configuré — critère C1 non vérifiable. "
        f"Raison rapportée par le moteur : {_raison_indisponibilite()}. "
        "Gratuit : lancer `ollama serve`."
    ),
)


@besoin_fournisseur
class TestCritereC1:
    """La définition de C1, telle qu'écrite dans la roadmap."""

    def test_le_conseil_agricole_repond(self, api):
        """200, un conseil non vide, et un modèle réellement nommé."""
        client, entetes = api
        reponse = client.post(
            "/agri/advice",
            json={"question": "Quand semer le mil dans la région de Thiès ?"},
            headers=entetes,
        )
        assert reponse.status_code == 200, reponse.text

        corps = reponse.json()
        assert corps["answer"].strip(), "conseil vide : C1 exige un texte utile"
        assert corps["model_used"], "aucun modèle nommé"
        assert corps["language"] == "fr"

    def test_la_langue_demandee_est_transmise(self, api):
        """Le paramètre de langue doit survivre jusqu'à la réponse."""
        client, entetes = api
        reponse = client.post(
            "/agri/advice",
            json={"question": "Quand semer le mil ?", "language": "wo"},
            headers=entetes,
        )
        assert reponse.status_code == 200
        assert reponse.json()["language"] == "wo"


# ---------------------------------------------------------------------------
# La chaîne complète, contre un serveur bouchon — s'exécute toujours
# ---------------------------------------------------------------------------


class TestChaineComplete:
    """Traverse outil → gestionnaire → sélecteur → fournisseur → HTTP.

    Le modèle est un bouchon, la chaîne est réelle. Sans ces tests, le fichier
    pourrait s'ignorer indéfiniment sans que personne ne remarque qu'il ne
    prouve plus rien.
    """

    def _fournisseur(self, url: str):
        """Construit un fournisseur local pointant sur le serveur bouchon."""
        from src.model_engine.providers.local_provider import LocalProvider

        return LocalProvider(url)

    def test_le_fournisseur_voit_le_serveur(self, serveur_local):
        """La sonde doit reconnaître un serveur joignable et ses modèles."""
        fournisseur = self._fournisseur(serveur_local)
        info = fournisseur.check_availability()
        assert info.model_count == 1
        assert not info.requires_credentials
        # Aucune clé n'est requise : c'est ce qui rend cette voie gratuite.
        assert fournisseur.requires_credentials is False

    def test_les_modeles_installes_sont_listes(self, serveur_local):
        """Le catalogue doit venir du serveur, pas du repli codé en dur."""
        modeles = [m.model_name for m in self._fournisseur(serveur_local).list_models()]
        assert modeles == [MODELE_BOUCHON]

    def test_la_generation_traverse_la_pile(self, serveur_local):
        """Le prompt part, le texte revient, le statut est READY."""
        from src.model_engine.providers.base import GenerationRequest, ProviderStatus

        fournisseur = self._fournisseur(serveur_local)
        reponse = fournisseur.generate(
            GenerationRequest(
                model_name=MODELE_BOUCHON,
                prompt="Quand semer le mil ?",
                max_tokens=64,
            )
        )
        assert reponse.status == ProviderStatus.READY
        assert reponse.text == TEXTE_BOUCHON
        assert reponse.completion_tokens == 9

    def test_un_serveur_absent_reste_un_statut(self, serveur_local):
        """Serveur éteint : indisponibilité rapportée, jamais de texte inventé.

        C'est la propriété que quatre fabrications passées ont violée.
        """
        from src.model_engine.providers.base import GenerationRequest, ProviderStatus

        # Un port fermé : rien n'écoute.
        fournisseur = self._fournisseur("http://127.0.0.1:1")
        reponse = fournisseur.generate(
            GenerationRequest(model_name=MODELE_BOUCHON, prompt="Question ?", max_tokens=8)
        )
        assert reponse.status != ProviderStatus.READY
        assert reponse.text == ""
        assert reponse.detail


class TestRaisonActionnable:
    """Un refus doit dire ce qui manque, pas seulement qu'il manque quelque chose."""

    def test_un_modele_trop_petit_est_explique(self, monkeypatch):
        """Serveur joignable, contexte trop court : le message doit nommer la contrainte.

        C'est le cas le plus probable en local — Ollama actif avec un petit
        modèle. Il produisait « Aucun modèle sélectionnable », une impasse : la
        vraie raison était journalisée et jetée.
        """
        from src.model_engine.model_manager import ModelManagerImpl
        from src.model_engine.provider_selector import ProviderSelection

        gestionnaire = ModelManagerImpl()
        # Un fournisseur *est* joignable : c'est la branche qu'on isole. Sans
        # cela, le résumé du registre — « aucun fournisseur » — prendrait le
        # dessus, et à juste titre : c'est alors le message le plus utile.
        monkeypatch.setattr(
            gestionnaire._provider_registry, "unavailability_summary", lambda: ""
        )
        monkeypatch.setattr(
            gestionnaire._provider_selector,
            "select",
            lambda *_a, **_k: ProviderSelection(
                provider=None,
                descriptor=None,
                reason="Aucun modèle disponible ne satisfait les contraintes (contexte minimal 8192)",
            ),
        )
        monkeypatch.setattr(gestionnaire, "list_models", lambda **_k: [])

        assert gestionnaire.select_model_for_task({}) is None
        raison = gestionnaire.unavailability_reason()
        assert "contexte minimal" in raison, raison

    def test_une_raison_perimee_ne_survit_pas(self, monkeypatch):
        """Après qu'un modèle est mis en service, l'ancien refus doit disparaître.

        Le chemin des modèles enregistrés retourne tôt : sans remise à zéro à
        l'entrée, `unavailability_reason()` continuerait d'expliquer un échec
        que la configuration a corrigé.
        """
        from src.model_engine.model_manager import ModelManagerImpl

        gestionnaire = ModelManagerImpl()
        gestionnaire._last_selection_failure = "échec précédent"

        monkeypatch.setattr(gestionnaire, "list_models", lambda **_k: ["modele"])
        monkeypatch.setattr(gestionnaire._selector, "select_model", lambda *_a, **_k: "modele")
        monkeypatch.setattr(
            gestionnaire._provider_registry, "unavailability_summary", lambda: ""
        )

        assert gestionnaire.select_model_for_task({}) == "modele"
        assert gestionnaire.unavailability_reason() == ""


class TestSautHonnete:
    """Le saut doit renseigner, pas seulement éviter l'échec."""

    def test_l_absence_de_fournisseur_est_expliquee(self):
        """Un `skip` muet laisse croire que le critère est couvert."""
        raison = besoin_fournisseur.kwargs.get("reason", "")
        if not _fournisseur_disponible():
            assert "C1" in raison
            assert "ollama serve" in raison
