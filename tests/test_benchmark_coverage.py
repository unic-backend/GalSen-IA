"""
Le barème dit ce qu'il ne couvre pas (phases 68.1, 68.2).

`benchmark_report()` comptait les entrées : combien existent, combien sont
vérifiées. Cela ne dit pas **ce qui n'est pas évalué**, qui est la seule des deux
informations sur laquelle on puisse agir. Les vagues III à VI ont ajouté des
domaines entiers — construction, sport, connaissance mondiale — et rien ne
signalait qu'aucune question ne les touchait.

Ce que ces tests gardent :

1. **Chaque entrée déclare son domaine**, et un domaine inconnu de
   `KnowledgeSubject` est **nommé** — sinon il ne serait couvert par personne,
   en silence.
2. **Un domaine vide ne s'évalue pas.** Noter zéro sur un domaine sans
   connaissance mesure le vide, pas la plateforme.
3. **« Personne n'a compté » n'est pas « rien à évaluer ».** Les deux appellent
   des gestes opposés : brancher un compteur, ou acquérir des sources.
4. **Un domaine peuplé sans question est un trou d'évaluation** : il se
   dégraderait sans que rien ne le dise.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.factual_evaluation import (  # noqa: E402
    COUVERTURE_INCONNUE,
    EVALUABLE,
    RIEN_A_EVALUER,
    SANS_ENTREE,
    benchmark_coverage,
    load_benchmark,
)
from src.knowledge_engine.scope import KnowledgeSubject  # noqa: E402


class _Compteur:
    """Un compteur qui rend ce qu'on lui dit, par sujet."""

    def __init__(self, par_sujet):
        self._par_sujet = par_sujet

    def count(self, scope=None, subject=None):
        return self._par_sujet.get(subject, 0)


# ----------------------------------------------------------------------
# 1. Chaque entrée déclare son domaine
# ----------------------------------------------------------------------

def test_toutes_les_entrees_declarent_un_domaine():
    """Sans domaine, on compte des questions sans savoir ce qu'elles couvrent."""
    sans_domaine = [entree.question for entree in load_benchmark() if not entree.domain]

    assert sans_domaine == []


def test_chaque_domaine_declare_est_un_sujet_connu():
    """Un domaine mal écrit ne serait couvert par personne, en silence."""
    sujets = {sujet.value for sujet in KnowledgeSubject}

    inconnus = sorted(
        {entree.domain for entree in load_benchmark() if entree.domain not in sujets}
    )

    assert inconnus == []


def test_un_domaine_inconnu_est_nomme_par_le_rapport(tmp_path):
    """C'est tout l'intérêt : le silence est le défaut à empêcher."""
    fichier = tmp_path / "bareme.jsonl"
    fichier.write_text(
        '{"question": "x", "status": "to_source", "domain": "astrologie"}\n',
        encoding="utf-8",
    )

    rapport = benchmark_coverage(str(fichier))

    assert rapport["unknown_domains"] == ["astrologie"]


# ----------------------------------------------------------------------
# 2. Un domaine vide ne s'évalue pas
# ----------------------------------------------------------------------

def test_un_domaine_sans_connaissance_ne_s_evalue_pas():
    """Noter zéro sur un domaine vide mesure le vide, pas la plateforme."""
    rapport = benchmark_coverage()

    assert rapport["nothing_to_evaluate"]
    prive = next(
        etat for etat in rapport["domains"]
        if etat["state"] == RIEN_A_EVALUER
    )
    assert prive["note"]


def test_la_regle_est_ecrite_pas_seulement_appliquee():
    """Un lecteur doit savoir pourquoi un domaine vide n'est pas noté."""
    regles = " ".join(benchmark_coverage()["rules"])

    assert "mesure le vide" in regles
    assert "trou d'évaluation" in " ".join(benchmark_coverage()["rules"])


def test_le_rapport_refuse_de_combler_un_trou_de_memoire():
    """Écrire une question de mémoire mesurerait cette mémoire."""
    interdits = " ".join(benchmark_coverage()["does_not"])

    assert "de mémoire" in interdits


# ----------------------------------------------------------------------
# 3. « Personne n'a compté » n'est pas « rien à évaluer »
# ----------------------------------------------------------------------

def test_un_domaine_non_mesure_n_est_pas_dit_vide(monkeypatch):
    """
    Les deux appellent des gestes opposés.

    La première version de ce rapport confondait les deux — exactement le piège
    que `domains.py` avait déjà dû corriger pour lui-même.
    """
    from src.knowledge_engine import factual_evaluation as module
    from src.knowledge_engine.domains import NOT_MEASURED

    monkeypatch.setattr(
        "src.knowledge_engine.domains.domain_coverage",
        lambda **kwargs: {
            "scope": "country:sn",
            "domains": [{"subject": "health", "state": NOT_MEASURED, "reason": ""}],
        },
    )

    rapport = module.benchmark_coverage()

    assert rapport["coverage_unknown"] == ["health"]
    assert rapport["nothing_to_evaluate"] == []


def test_le_rapport_dit_s_il_a_ete_mesure():
    """Sans compteur, la couverture est une lecture, pas une mesure."""
    assert benchmark_coverage()["measured"] is False


# ----------------------------------------------------------------------
# 4. Un domaine peuplé sans question est un trou
# ----------------------------------------------------------------------

def test_un_domaine_peuple_sans_question_est_un_trou(monkeypatch, tmp_path):
    """Il se dégraderait sans que rien ne le dise."""
    from src.knowledge_engine import factual_evaluation as module
    from src.knowledge_engine.domains import POPULATED

    monkeypatch.setattr(
        "src.knowledge_engine.domains.domain_coverage",
        lambda **kwargs: {
            "scope": "country:sn",
            "domains": [
                {"subject": "health", "state": POPULATED, "reason": ""},
                {"subject": "law", "state": POPULATED, "reason": ""},
            ],
        },
    )
    fichier = tmp_path / "bareme.jsonl"
    fichier.write_text(
        '{"question": "x", "status": "to_source", "domain": "law"}\n',
        encoding="utf-8",
    )

    rapport = module.benchmark_coverage(str(fichier))

    assert rapport["evaluable"] == ["law"]
    assert rapport["no_entry"] == ["health"]
    assert next(
        e for e in rapport["domains"] if e["domain"] == "health"
    )["state"] == SANS_ENTREE


def test_un_domaine_avec_question_et_connaissance_est_evaluable(monkeypatch, tmp_path):
    """Le seul état où une note aurait un sens."""
    from src.knowledge_engine import factual_evaluation as module
    from src.knowledge_engine.domains import POPULATED

    monkeypatch.setattr(
        "src.knowledge_engine.domains.domain_coverage",
        lambda **kwargs: {
            "scope": "country:sn",
            "domains": [{"subject": "agriculture", "state": POPULATED, "reason": ""}],
        },
    )
    fichier = tmp_path / "bareme.jsonl"
    fichier.write_text(
        '{"question": "x", "status": "to_source", "domain": "agriculture"}\n',
        encoding="utf-8",
    )

    rapport = module.benchmark_coverage(str(fichier))

    assert rapport["domains"][0]["state"] == EVALUABLE
    assert rapport["domains"][0]["questions"] == 1


def test_les_quatre_etats_sont_distincts():
    """Trois absences qui se ressemblent appellent trois gestes différents."""
    assert len({EVALUABLE, SANS_ENTREE, RIEN_A_EVALUER, COUVERTURE_INCONNUE}) == 4


# ----------------------------------------------------------------------
# 5. Le compte des entrées n'a pas changé de sens
# ----------------------------------------------------------------------

def test_les_domaines_ajoutes_par_les_vagues_recentes_sont_interroges():
    """
    Construction, sport, géographie, langues : ajoutés en vagues IV à VI, et
    aucune question ne les touchait.

    Les entrées restent `to_source` — elles nomment la question et la source qui
    la trancherait, jamais la réponse.
    """
    domaines = {entree.domain for entree in load_benchmark()}

    assert {"construction", "sports", "geography", "languages"} <= domaines


def test_aucune_entree_ajoutee_ne_porte_de_reponse():
    """Une entrée écrite de mémoire ferait de chaque mesure future une mesure
    de cette mémoire."""
    for entree in load_benchmark():
        if entree.status == "to_source":
            assert entree.expected_claims == (), entree.question
            assert entree.source == "", entree.question


def test_le_barème_reste_vide_et_le_dit():
    """Zéro entrée vérifiée est l'état honnête, et il ne bouge pas ici."""
    from src.knowledge_engine.factual_evaluation import benchmark_report

    rapport = benchmark_report()

    assert rapport["verified"] == 0
    assert rapport["entries"] == rapport["to_source"]


@pytest.fixture
def client_bareme(monkeypatch):
    """Client HTTP et clé nommée."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_publie_la_couverture(client_bareme):
    """Un lecteur doit voir les trous sans ouvrir le code."""
    client, cle = client_bareme

    rapport = client.get("/knowledge/benchmark-coverage", headers=cle).json()

    assert rapport["entries"] >= 10
    assert rapport["entries_without_domain"] == 0
    assert rapport["unknown_domains"] == []


def test_la_route_de_couverture_exige_une_cle(client_bareme):
    """Elle n'est pas publique."""
    client, _ = client_bareme

    assert client.get("/knowledge/benchmark-coverage").status_code in (401, 403)
