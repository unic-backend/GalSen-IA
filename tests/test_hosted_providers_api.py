"""
Chemin d'appel des fournisseurs distants (P1 du backlog).

`_call_api` est implémenté pour OpenAI, Anthropic et Google, et seule la branche
« aucune clé » était testée. Le reste — la requête construite, la réponse
analysée, les erreurs 401 / 429 / 400 — ne l'était pas, alors que c'est
exactement le chemin dont dépend le critère de sortie **C1**. Du code fournisseur
non testé est l'endroit où une panne silencieuse se cache.

Aucun appel réseau n'est fait : `urlopen` est remplacé, ce qui laisse sous test
ce qui est réellement en cause — la construction de la requête, la lecture de la
réponse et la traduction des erreurs.
"""

import io
import json
import urllib.error

import pytest

from src.model_engine.providers.anthropic_provider import AnthropicProvider
from src.model_engine.providers.base import (
    GenerationRequest,
    ProviderStatus,
    UnavailabilityReason,
)
from src.model_engine.providers.google_provider import GoogleProvider
from src.model_engine.providers.hosted_provider import detail_avec_corps, read_error_body
from src.model_engine.providers.openai_provider import OpenAIProvider

# Réponses telles que chaque API les rend réellement.
REPONSE_OPENAI = {
    "choices": [{"message": {"content": "Le mil se sème en juin."}}],
    "usage": {"prompt_tokens": 12, "completion_tokens": 7},
}
REPONSE_ANTHROPIC = {
    "content": [{"text": "Le mil se sème en juin."}],
    "usage": {"input_tokens": 12, "output_tokens": 7},
}
REPONSE_GOOGLE = {
    "candidates": [{"content": {"parts": [{"text": "Le mil se sème en juin."}]}}],
}


class _ReponseFactice:
    """Réponse HTTP minimale, utilisable comme gestionnaire de contexte."""

    def __init__(self, charge):
        self._corps = json.dumps(charge).encode("utf-8")

    def read(self):
        return self._corps

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _erreur_http(code: int, corps: bytes = b""):
    """Construit une `HTTPError` avec un corps lisible une seule fois."""
    return urllib.error.HTTPError("https://exemple", code, "erreur", {}, io.BytesIO(corps))


def _requete():
    """Requête de génération minimale."""
    return GenerationRequest(prompt="Quand semer le mil ?", model_name="modele-test",
                             max_tokens=64, temperature=0.2)


FOURNISSEURS = [
    ("OPENAI_API_KEY", OpenAIProvider, REPONSE_OPENAI),
    ("ANTHROPIC_API_KEY", AnthropicProvider, REPONSE_ANTHROPIC),
    ("GOOGLE_API_KEY", GoogleProvider, REPONSE_GOOGLE),
]


# ----------------------------------------------------------------------
# Le défaut trouvé : le corps d'erreur était lu deux fois
# ----------------------------------------------------------------------

def test_le_corps_d_erreur_se_lit_une_seule_fois():
    """
    Les trois fournisseurs écrivaient
    `e.read().decode() if e.read() else str(e)` : le premier appel consommait le
    flux, le second ne rendait plus rien. Le corps était donc **toujours vide**
    quand il existait — exactement le cas où il sert.
    """
    erreur = _erreur_http(400, b'{"error": {"status": "API_KEY_INVALID"}}')

    assert "API_KEY_INVALID" in read_error_body(erreur)


def test_un_corps_absent_ne_devient_pas_du_bruit():
    assert read_error_body(_erreur_http(500)) == ""
    assert detail_avec_corps("Erreur API: 500", "") == "Erreur API: 500"


def test_un_corps_trop_long_est_tronque():
    """Ce texte finit dans un message d'erreur ; un corps d'API fait des kilo-octets."""
    corps = read_error_body(_erreur_http(400, b"x" * 5000), limite=100)

    assert len(corps) <= 101
    assert corps.endswith("…")


def test_un_code_http_non_gere_ne_leve_plus():
    """
    Deuxième défaut, trouvé en écrivant ces tests : les trois fournisseurs
    référençaient `UnavailabilityReason.UNAVAILABLE`, **qui n'existe pas** dans
    l'énumération (`NO_CREDENTIALS`, `MISSING_DEPENDENCY`, `UNREACHABLE`,
    `QUOTA_EXCEEDED`, `UNAUTHORIZED`, `DISABLED`).

    Toute erreur autre qu'un 401 ou un 429 — donc 400, 403, 404, 500, 503 — et
    toute panne non HTTP levaient un `AttributeError` **hors** de `_call_api`,
    au lieu de rendre une réponse indisponible. C'est le chemin dont dépend le
    critère C1, et il cassait sur le premier appel réel qui ne serait ni une
    clé refusée ni un quota.
    """
    assert not hasattr(UnavailabilityReason, "UNAVAILABLE")
    assert UnavailabilityReason.UNREACHABLE is not None


def test_une_cle_google_invalide_est_reconnue_comme_telle(monkeypatch):
    """
    C'est la conséquence concrète du double `read()` : Google était le seul à
    utiliser le corps, et sa détection ne se déclenchait donc jamais. Une clé
    invalide était rapportée comme une erreur générique 400.
    """
    monkeypatch.setenv("GOOGLE_API_KEY", "cle-invalide")
    fournisseur = GoogleProvider()
    corps = b'{"error": {"message": "API key not valid", "status": "API_KEY_INVALID"}}'
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erreur_http(400, corps)))

    reponse = fournisseur._call_api(_requete())

    assert reponse.status is ProviderStatus.UNAVAILABLE
    assert reponse.reason is UnavailabilityReason.UNAUTHORIZED


# ----------------------------------------------------------------------
# Le chemin nominal, pour les trois fournisseurs
# ----------------------------------------------------------------------

@pytest.mark.parametrize("variable,classe,charge", FOURNISSEURS)
def test_une_generation_reussie_est_analysee(monkeypatch, variable, classe, charge):
    """Seule la branche « aucune clé » était testée : celle-ci ne l'était pas."""
    monkeypatch.setenv(variable, "cle-de-test")
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _ReponseFactice(charge))

    reponse = classe()._call_api(_requete())

    assert reponse.status is ProviderStatus.READY
    assert reponse.text == "Le mil se sème en juin."
    assert reponse.latency_seconds >= 0


@pytest.mark.parametrize("variable,classe,charge", FOURNISSEURS)
def test_la_requete_porte_la_cle_et_le_modele(monkeypatch, variable, classe, charge):
    """
    Une requête bien formée est la moitié du chemin C1, et rien ne la vérifiait.

    La clé est cherchée dans l'en-tête **ou** dans l'URL selon l'API : Google la
    passe en paramètre de requête, les deux autres en en-tête.
    """
    monkeypatch.setenv(variable, "cle-de-test")
    captures = {}

    def capturer(req, *args, **kwargs):
        captures["url"] = req.full_url
        captures["headers"] = {k.lower(): v for k, v in req.headers.items()}
        captures["body"] = json.loads(req.data.decode("utf-8"))
        return _ReponseFactice(charge)

    monkeypatch.setattr("urllib.request.urlopen", capturer)
    classe()._call_api(_requete())

    entetes = " ".join(captures["headers"].values())
    assert "cle-de-test" in entetes or "cle-de-test" in captures["url"]
    assert "modele-test" in json.dumps(captures["body"]) + captures["url"]
    assert "Quand semer le mil ?" in json.dumps(captures["body"], ensure_ascii=False)


# ----------------------------------------------------------------------
# Les erreurs que l'opérateur rencontrera réellement
# ----------------------------------------------------------------------

@pytest.mark.parametrize("variable,classe,charge", FOURNISSEURS)
def test_un_quota_depasse_est_distingue(monkeypatch, variable, classe, charge):
    """429 n'est pas une panne : c'est une limite, et un opérateur agit différemment."""
    monkeypatch.setenv(variable, "cle-de-test")
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erreur_http(429)))

    reponse = classe()._call_api(_requete())

    assert reponse.reason is UnavailabilityReason.QUOTA_EXCEEDED


@pytest.mark.parametrize("variable,classe,charge", FOURNISSEURS)
def test_une_panne_reseau_ne_leve_pas(monkeypatch, variable, classe, charge):
    """
    Un fournisseur injoignable rend une réponse indisponible, jamais une
    exception : une panne réseau ne doit pas faire tomber l'appelant.
    """
    monkeypatch.setenv(variable, "cle-de-test")
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("réseau injoignable")))

    reponse = classe()._call_api(_requete())

    assert reponse.status is ProviderStatus.UNAVAILABLE
    assert reponse.text in (None, "")


@pytest.mark.parametrize("variable,classe,charge",
                         [f for f in FOURNISSEURS if f[0] != "GOOGLE_API_KEY"])
def test_une_cle_refusee_est_reconnue(monkeypatch, variable, classe, charge):
    """OpenAI et Anthropic répondent 401 ; Google passe par un 400 spécifique."""
    monkeypatch.setenv(variable, "cle-de-test")
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erreur_http(401)))

    reponse = classe()._call_api(_requete())

    assert reponse.reason is UnavailabilityReason.UNAUTHORIZED


@pytest.mark.parametrize("variable,classe,charge", FOURNISSEURS)
def test_le_message_de_l_api_atteint_l_operateur(monkeypatch, variable, classe, charge):
    """
    Le corps était lu puis jeté : « Erreur API OpenAI: 400 » n'apprend rien,
    alors que l'API dit précisément ce qui ne va pas.
    """
    monkeypatch.setenv(variable, "cle-de-test")
    corps = b'{"error": {"message": "modele-test does not exist"}}'
    monkeypatch.setattr("urllib.request.urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(_erreur_http(400, corps)))

    reponse = classe()._call_api(_requete())

    assert "does not exist" in reponse.detail
