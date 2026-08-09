"""
Tests du fournisseur compatible OpenAI (ADR-003).

Ce fournisseur existe pour une raison de trajectoire : il ouvre vLLM, LM Studio,
llama.cpp, LocalAI, OpenRouter, Groq et un futur serveur loué avec le **même
code**. Seule l'URL change. C'est ce qui rend le passage « portable → serveur →
hébergeur » possible sans réécriture.

Ces tests tournent contre un serveur HTTP local parlant le protocole OpenAI. Le
modèle est un bouchon ; le protocole, lui, est réel — les mêmes requêtes
partiraient vers un vrai service.

Trois propriétés valent le reste :

1. **Rien n'est deviné.** Sans URL déclarée, le fournisseur se dit indisponible
   au lieu de pointer quelque part par défaut.
2. **Le catalogue est découvert.** Une liste écrite en dur mentirait dès que
   l'exploitant change de modèle.
3. **Un échec porte son motif.** 401 et 429 appellent des gestes différents ;
   les confondre laisserait l'exploitant sans piste.
"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.providers.base import (  # noqa: E402
    GenerationRequest,
    ProviderStatus,
    UnavailabilityReason,
)
from src.model_engine.providers.openai_compatible_provider import (  # noqa: E402
    CONTEXTE_PAR_DEFAUT,
    CONTEXT_VARIABLE,
    KEY_VARIABLE,
    URL_VARIABLE,
    OpenAICompatibleProvider,
)

MODELE = "mon-modele-maison"
TEXTE = "Semez le mil dès les premières pluies utiles."

# Code que le serveur bouchon doit renvoyer ; réglé par test.
CODE_FORCE = {"valeur": None}
DERNIERE_REQUETE = {}


class _ServiceCompatible(BaseHTTPRequestHandler):
    """Sert `/v1/models` et `/v1/chat/completions`, comme vLLM ou Groq."""

    def do_GET(self):  # noqa: N802 — nom imposé par http.server
        """Catalogue des modèles servis."""
        if not self.path.endswith("/models"):
            self.send_error(404)
            return
        self._repondre({"data": [{"id": MODELE, "object": "model"}]})

    def do_POST(self):  # noqa: N802 — nom imposé par http.server
        """Génération, ou le code d'erreur demandé par le test."""
        if CODE_FORCE["valeur"]:
            self.send_error(CODE_FORCE["valeur"])
            return

        taille = int(self.headers.get("Content-Length", 0))
        DERNIERE_REQUETE.clear()
        DERNIERE_REQUETE.update(json.loads(self.rfile.read(taille) or b"{}"))
        DERNIERE_REQUETE["_authorization"] = self.headers.get("Authorization")

        self._repondre({
            "model": MODELE,
            "choices": [{"message": {"role": "assistant", "content": TEXTE}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 8},
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
        """Silence : la sortie du serveur n'apporte rien au rapport."""


@pytest.fixture
def service():
    """Démarre un service compatible OpenAI et retourne son URL `/v1`."""
    CODE_FORCE["valeur"] = None
    httpd = HTTPServer(("127.0.0.1", 0), _ServiceCompatible)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    finally:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def sans_variables(monkeypatch):
    """Environnement vierge : aucune URL, aucune clé, aucun contexte imposé."""
    for variable in (URL_VARIABLE, KEY_VARIABLE, CONTEXT_VARIABLE):
        monkeypatch.delenv(variable, raising=False)


def _requete(modele: str = MODELE) -> GenerationRequest:
    """Construit une requête de génération minimale."""
    return GenerationRequest(model_name=modele, prompt="Quand semer le mil ?", max_tokens=64)


class TestRienNEstDevine:
    """Sans URL, le fournisseur doit se taire plutôt que pointer ailleurs."""

    def test_indisponible_sans_url(self, sans_variables):
        """Un fournisseur qui devine une adresse est pire qu'un absent."""
        info = OpenAICompatibleProvider().check_availability()
        assert info.status is ProviderStatus.UNAVAILABLE
        assert URL_VARIABLE in info.detail

    def test_catalogue_vide_sans_url(self, sans_variables):
        """Aucun modèle ne doit être annoncé pour un service inexistant."""
        assert OpenAICompatibleProvider().list_models() == []

    def test_generation_refusee_sans_url(self, sans_variables):
        """Et surtout : aucun texte de remplacement."""
        reponse = OpenAICompatibleProvider().generate(_requete())
        assert reponse.status is not ProviderStatus.READY
        assert reponse.text == ""

    def test_l_url_de_l_environnement_est_lue(self, service, monkeypatch):
        """C'est le mode d'emploi : une variable, rien d'autre."""
        monkeypatch.setenv(URL_VARIABLE, service)
        assert OpenAICompatibleProvider().check_availability().status is ProviderStatus.READY


class TestCatalogueDecouvert:
    """Le service dit ce qu'il sert ; on ne le devine pas."""

    def test_les_modeles_viennent_du_service(self, service):
        """Une liste en dur mentirait dès un changement de modèle."""
        modeles = OpenAICompatibleProvider(service).list_models()
        assert [m.model_name for m in modeles] == [MODELE]

    def test_le_contexte_par_defaut_rend_le_modele_selectionnable(self, service, sans_variables):
        """`/v1/models` ne dit pas la fenêtre : le défaut doit passer le sélecteur.

        Le sélecteur exige 8192 par défaut. Annoncer moins écarterait
        silencieusement tous les modèles de ce fournisseur.
        """
        modele = OpenAICompatibleProvider(service).list_models()[0]
        assert modele.context_window == CONTEXTE_PAR_DEFAUT
        assert modele.context_window >= 8192

    def test_le_contexte_est_reglable(self, service, monkeypatch):
        """Un serveur qui accepte plus doit pouvoir le déclarer."""
        monkeypatch.setenv(CONTEXT_VARIABLE, "32768")
        assert OpenAICompatibleProvider(service).list_models()[0].context_window == 32768

    def test_un_contexte_illisible_retombe_sur_le_defaut(self, service, monkeypatch):
        """Une variable fautive ne doit pas rendre le fournisseur inutilisable."""
        monkeypatch.setenv(CONTEXT_VARIABLE, "beaucoup")
        assert (
            OpenAICompatibleProvider(service).list_models()[0].context_window
            == CONTEXTE_PAR_DEFAUT
        )

    def test_aucun_prix_invente(self, service):
        """Un service auto-hébergé n'a pas de prix : en inventer fausserait la sélection."""
        assert OpenAICompatibleProvider(service).list_models()[0].pricing_per_1k_tokens is None


class TestGeneration:
    """Le protocole doit être parlé correctement, dans les deux sens."""

    def test_le_texte_revient(self, service):
        """La traversée complète : requête envoyée, réponse lue."""
        reponse = OpenAICompatibleProvider(service).generate(_requete())
        assert reponse.status is ProviderStatus.READY
        assert reponse.text == TEXTE
        assert reponse.completion_tokens == 8

    def test_le_prompt_part_bien(self, service):
        """Un fournisseur qui répond sans transmettre la question ne sert à rien."""
        OpenAICompatibleProvider(service).generate(_requete())
        assert DERNIERE_REQUETE["messages"][-1]["content"] == "Quand semer le mil ?"
        assert DERNIERE_REQUETE["model"] == MODELE

    def test_l_invite_systeme_est_transmise(self, service):
        """Le rôle `system` porte le cadrage : le perdre change la réponse."""
        requete = GenerationRequest(
            model_name=MODELE, prompt="Question ?", max_tokens=16,
            system_prompt="Tu es un expert agricole sénégalais.",
        )
        OpenAICompatibleProvider(service).generate(requete)
        assert DERNIERE_REQUETE["messages"][0]["role"] == "system"


class TestCleFacultative:
    """C'est la différence avec `OpenAIProvider`, et elle est délibérée."""

    def test_fonctionne_sans_cle(self, service, sans_variables):
        """Un serveur local n'en demande pas ; exiger une clé le rendrait inutilisable."""
        assert OpenAICompatibleProvider(service).generate(_requete()).status is ProviderStatus.READY
        assert DERNIERE_REQUETE["_authorization"] is None

    def test_la_cle_est_envoyee_quand_elle_existe(self, service, monkeypatch):
        """OpenRouter ou Groq en exigent une : elle doit partir en en-tête."""
        monkeypatch.setenv(KEY_VARIABLE, "cle-secrete")
        OpenAICompatibleProvider(service).generate(_requete())
        assert DERNIERE_REQUETE["_authorization"] == "Bearer cle-secrete"

    def test_le_fournisseur_n_exige_pas_d_identifiants(self, sans_variables):
        """Déclaré au contrat : sinon le moteur le classerait indisponible d'office."""
        assert OpenAICompatibleProvider().requires_credentials is False


class TestMotifsDEchec:
    """401 et 429 appellent des gestes différents : ils doivent se distinguer."""

    @pytest.mark.parametrize("code,motif", [
        (401, UnavailabilityReason.UNAUTHORIZED),
        (403, UnavailabilityReason.UNAUTHORIZED),
        (429, UnavailabilityReason.QUOTA_EXCEEDED),
        (500, UnavailabilityReason.UNREACHABLE),
    ])
    def test_le_code_http_devient_un_motif(self, service, code, motif):
        """Un motif générique laisserait l'exploitant sans piste."""
        CODE_FORCE["valeur"] = code
        reponse = OpenAICompatibleProvider(service).generate(_requete())
        assert reponse.status is not ProviderStatus.READY
        assert reponse.reason is motif
        assert reponse.text == ""

    def test_un_service_eteint_est_injoignable(self, sans_variables):
        """Port fermé : indisponibilité rapportée, jamais de texte inventé."""
        reponse = OpenAICompatibleProvider("http://127.0.0.1:1/v1").generate(_requete())
        assert reponse.reason is UnavailabilityReason.UNREACHABLE
        assert reponse.text == ""
        assert reponse.detail
