"""
La démonstration de bout en bout (phases 69.1, 69.2).

Le domaine 37 de la directive — démonstration de bout en bout — était mesuré
absent, et c'est le seul contrôle que les 4308 tests ne remplacent pas. Une suite
prouve que chaque pièce se comporte comme son auteur l'attendait ; elle ne prouve
pas qu'un travail traverse la plateforme d'un bout à l'autre. Les coutures sont
l'endroit où les choses cassent, et ce sont elles que personne ne teste.

Ce que ces tests gardent :

1. **Rien n'est simulé** : la démonstration appelle le vrai orchestrateur, et
   une démonstration qui bouchonnerait démontrerait le bouchon.
2. **Un blocage connu n'est pas une panne**, et il est **vérifié** à
   l'exécution — jamais répété depuis une note périmée.
3. **Le verdict est la somme de ce qui a été mesuré**, jamais un titre écrit
   d'avance.
4. **Le défaut que la démonstration a trouvé reste corrigé** : une question en
   phrase atteint la référence mondiale.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.demonstration import BLOQUE, ECHOUE, REUSSI, run_demonstration  # noqa: E402
from src.knowledge_engine.world import find_country  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def rapport():
    """Une seule exécution : elle fait tourner un workflow réel."""
    return run_demonstration()


# ----------------------------------------------------------------------
# 1. La chaîne réelle traverse
# ----------------------------------------------------------------------

def test_toutes_les_etapes_sont_rapportees(rapport):
    """Une étape absente du rapport est une étape que personne ne lira."""
    etapes = [etape["step"] for etape in rapport["steps"]]

    assert etapes == [
        "subsystems", "knowledge_routing", "world_knowledge",
        "routine_fires_workflow", "trail", "generation", "acquisition",
    ]


def test_aucune_etape_n_echoue_dans_ce_depot(rapport):
    """Le résultat mesuré aujourd'hui — et ce qui casserait se verrait ici."""
    assert rapport["failed"] == []


def test_la_couture_centrale_tient(rapport):
    """Routine → orchestrateur → point de reprise → identifiant."""
    travail = next(
        e for e in rapport["steps"] if e["step"] == "routine_fires_workflow"
    )

    assert travail["status"] == REUSSI
    assert travail["agents"] > 0
    assert travail["correlation_id"]


def test_le_travail_se_relit_dans_les_trois_sources(rapport):
    """C'est ce que l'observabilité du VOLET 66 promettait."""
    piste = next(e for e in rapport["steps"] if e["step"] == "trail")

    assert set(piste["found_in"]) == {
        "routine_runs", "audit_events", "workflow_runs",
    }


def test_rien_n_est_simule(rapport):
    """Une démonstration qui bouchonne l'orchestrateur démontre le bouchon."""
    regles = " ".join(rapport["rules"])

    assert "Rien n'est simulé" in regles
    assert "démontre le bouchon" in regles


# ----------------------------------------------------------------------
# 2. Un blocage connu n'est pas une panne
# ----------------------------------------------------------------------

def test_la_generation_est_bloquee_et_le_dit(rapport):
    """Aucun fournisseur ici : ce n'est ni un succès ni un échec."""
    etape = next(e for e in rapport["steps"] if e["step"] == "generation")

    assert etape["status"] == BLOQUE
    assert "fournisseur" in etape["detail"]


def test_l_acquisition_est_bloquee_et_nomme_ses_deux_causes(rapport):
    """Aucune source activée, et un mandataire qui refuse. Mesuré, non contourné."""
    etape = next(e for e in rapport["steps"] if e["step"] == "acquisition")

    assert etape["status"] == BLOQUE
    assert "aucune activée" in etape["detail"]
    assert "403" in etape["detail"]


def test_un_blocage_est_verifie_pas_suppose(monkeypatch):
    """
    Le jour où un fournisseur est configuré, l'étape doit le dire.

    Une limite répétée depuis une note périmée est une fausse mesure qui
    survit à sa cause.
    """
    from src.demonstration import scenario

    class _Moteur:
        def sovereignty_report(self):
            return {"configured_providers": ["local"]}

    monkeypatch.setattr(
        "src.integration.engine_registry.get_shared_registry",
        lambda: type("R", (), {"try_get": lambda self, nom: _Moteur()})(),
    )

    etape = scenario._generation()

    assert etape["status"] == REUSSI
    assert "local" in etape["detail"]


# ----------------------------------------------------------------------
# 3. Le verdict est la somme de ce qui a été mesuré
# ----------------------------------------------------------------------

def test_le_verdict_dit_partiel_quand_une_capacite_manque(rapport):
    """Ni vert ni rouge : la plateforme tourne, deux capacités dorment."""
    assert rapport["verdict"] == "PARTIAL"
    assert set(rapport["blocked"]) == {"generation", "acquisition"}


def test_une_etape_qui_leve_est_rapportee_pas_propagee():
    """Une démonstration qui s'arrête à la première anomalie n'en dit qu'une."""
    from src.demonstration import scenario

    etape = scenario._etape("cassee", lambda: (_ for _ in ()).throw(RuntimeError("boum")))

    assert etape["status"] == ECHOUE
    assert "boum" in etape["detail"]


def test_le_rapport_est_serialisable(rapport):
    """Il est lu par quelqu'un qui n'a pas le code sous les yeux."""
    import json

    json.dumps(rapport, ensure_ascii=False, default=str)
    for etape in rapport["steps"]:
        assert "journal" not in etape
        assert "checkpoints" not in etape


# ----------------------------------------------------------------------
# 4. Le défaut trouvé par la démonstration reste corrigé
# ----------------------------------------------------------------------

def test_une_question_en_phrase_atteint_la_reference_mondiale():
    """
    Le défaut du premier tour : le routage passait la question entière à une
    fonction qui attend un **nom de pays**. Invisible en test unitaire.
    """
    reponse = find_country("Quelle est la capitale du Ghana ?")

    assert reponse["status"] == "FOUND"
    assert reponse["country"]["iso3"] == "GHA"
    assert reponse["method"] == "exact_name"


def test_le_nom_le_plus_long_l_emporte():
    """« Guinée équatoriale » ne doit jamais se lire « Guinée »."""
    reponse = find_country("Quelle est la capitale de la Guinée équatoriale ?")

    assert reponse["country"]["iso3"] == "GNQ"


def test_aucun_rapprochement_approche():
    """« Niger » et « Nigeria » sont deux pays."""
    assert find_country("la capitale du Niger")["country"]["iso3"] == "NER"
    assert find_country("la capitale du Nigeria")["country"]["iso3"] == "NGA"


def test_aucun_code_iso_n_est_cherche_dans_une_phrase():
    """`EST` et `LA` sont des codes ISO et des mots français (piège du V54)."""
    reponse = find_country("Quelle est la monnaie de ce pays ?")

    assert reponse["status"] == "UNKNOWN"


def test_le_routage_utilise_bien_la_recherche_dans_la_phrase():
    """La correction doit être branchée, pas seulement écrite."""
    from src.knowledge_engine.routing import ask

    reponse = ask("Quelle est la capitale du Ghana ?")

    assert reponse["answered_by"] == "world"
    assert reponse["status"] == "FOUND"


# ----------------------------------------------------------------------
# 5. Le lanceur et sa documentation
# ----------------------------------------------------------------------

def test_le_script_rend_zero_malgre_les_blocages():
    """Une capacité non activée ne doit pas faire échouer une intégration continue."""
    execution = subprocess.run(
        [sys.executable, os.path.join(RACINE, "scripts", "demonstration.py")],
        capture_output=True, text=True, timeout=300,
    )

    assert execution.returncode == 0
    assert "Verdict : PARTIAL" in execution.stdout


def test_la_documentation_nomme_chaque_etape():
    """Une étape ajoutée sans être documentée fait échouer ce test."""
    chemin = os.path.join(RACINE, "docs", "demonstration", "README.md")
    with open(chemin, encoding="utf-8") as fichier:
        page = fichier.read()

    for etape in ("subsystems", "knowledge_routing", "world_knowledge",
                  "routine_fires_workflow", "trail", "generation", "acquisition"):
        assert etape in page, etape


def test_la_documentation_raconte_le_defaut_trouve():
    """Ce qu'une démonstration apporte se démontre par ce qu'elle a attrapé."""
    chemin = os.path.join(RACINE, "docs", "demonstration", "README.md")
    with open(chemin, encoding="utf-8") as fichier:
        page = fichier.read()

    assert "find_country" in page
    assert "Ghana" in page
