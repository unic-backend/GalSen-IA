"""
Ce qui fonctionne encore quand quelque chose est tombé
(VOLET 18 de Darra J).

La forme dangereuse de la dégradation est la forme élégante. Un système qui
« se replie » quand un composant tombe est un système qui répond depuis
ailleurs, et ailleurs est exactement là où vit l'invention.

Ce que ces tests gardent :

1. **Un fait de curriculum survit à l'absence de modèle** (directive XXXV), et
   il est **identique** avec et sans.
2. **Chaque capacité dégradée fait moins**, jamais autre chose.
3. **Un registre vide n'est pas une panne** : `UNKNOWN` est la bonne réponse.
4. **Le registre tient sous accès concurrent** — mesuré, pas supposé.
"""

import os
import sys
import threading

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    CurriculumStatus,
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Subject,
    make_provenance,
)
from src.darra_j.registry import CurriculumRegistry  # noqa: E402
from src.darra_j.resilience import (  # noqa: E402
    CAPACITES,
    measure_latency,
    probe_curriculum,
    resilience_report,
    survives_without_model,
)
from src.darra_j.resolution import CurriculumQuery  # noqa: E402
from src.integration.degradation import (  # noqa: E402
    DEGRADE,
    DISPONIBLE,
)

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


@pytest.fixture
def registre():
    """Un registre publié, avec une unité en semaine 10."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    depot.add_unit(CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject("maths", "Mathématiques"),
        period=Period(academic_year="2026-2027", week=10),
        official_title="Les fractions",
        objectives=("Comparer deux fractions",),
        provenance=_officielle(),
    ))
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        depot.advance("v-2026", etat)
    depot.publish("v-2026", decided_by="Direction des curricula")
    return depot


def _question(**extra):
    """Une question complète sur la semaine 10."""
    champs = {"academic_year": "2026-2027", "grade_id": "g6",
              "subject": "maths", "week": 10}
    champs.update(extra)
    return CurriculumQuery(**champs)


# ----------------------------------------------------------------------
# 1. Le curriculum survit à l'absence de modèle
# ----------------------------------------------------------------------

def test_le_fait_officiel_est_identique_avec_et_sans_modele(registre):
    """
    Si un modèle changeait l'enregistrement, il en serait la source.

    C'est la distinction critique de la directive XXXV, mesurée plutôt
    qu'affirmée.
    """
    verdict = survives_without_model(_question(), registre)

    assert verdict["retrievable_without_model"] is True
    assert verdict["canonical_identical"] is True
    assert verdict["explanation_without"] is None


def test_la_recuperation_reste_disponible_sans_generateur(registre):
    """Une école a besoin de la semaine 10 même si `ollama` ne tourne pas."""
    sonde = probe_curriculum(registre, generator_available=False)

    assert sonde["capabilities"]["curriculum_retrieval"]["state"] == DISPONIBLE
    assert sonde["capabilities"]["explanation"]["state"] == DEGRADE


# ----------------------------------------------------------------------
# 2. Dégrader, c'est faire moins
# ----------------------------------------------------------------------

def test_chaque_capacite_dit_ce_qu_elle_cesse_de_faire():
    """Une capacité dégradée sans description invite à imaginer un repli."""
    for nom, description in CAPACITES.items():
        assert description.strip(), nom


def test_une_capacite_degradee_ne_substitue_rien(registre):
    """La raison doit nommer ce qui **n'est pas** fait à la place."""
    sonde = probe_curriculum(registre, generator_available=False)

    raison = sonde["capabilities"]["explanation"]["reason"]
    assert "leçon générique" in raison
    assert "fait moins" in sonde["note"]


def test_l_absence_de_table_d_alias_degrade_sans_deviner(registre):
    """Les questions dans la langue de publication résolvent encore."""
    sonde = probe_curriculum(registre, alias_table_available=False)

    pont = sonde["capabilities"]["multilingual_bridge"]
    assert pont["state"] == DEGRADE
    assert "aucune traduction n'est devinée" in pont["reason"]


def test_tout_disponible_donne_un_etat_global_disponible(registre):
    """Le cas nominal existe."""
    sonde = probe_curriculum(registre, generator_available=True,
                             alias_table_available=True)

    assert sonde["state"] == DISPONIBLE


# ----------------------------------------------------------------------
# 3. Un registre vide n'est pas une panne
# ----------------------------------------------------------------------

def test_un_registre_vide_ne_rend_pas_la_recuperation_indisponible():
    """`UNKNOWN` est une réponse ; la confondre avec une panne masquerait l'état."""
    sonde = probe_curriculum(CurriculumRegistry())

    assert sonde["capabilities"]["curriculum_retrieval"]["state"] == DISPONIBLE
    assert "une réponse et non une panne" in \
        sonde["capabilities"]["curriculum_retrieval"]["reason"]


def test_le_compte_des_versions_officielles_est_lu_de_la_bonne_cle(registre):
    """
    Le défaut que ce volet a trouvé.

    `registry_report()` ne porte pas de clé « published ». Un
    `.get("published", 0)` aurait lu 0 en silence, et la sonde aurait toujours
    dit « aucune version publiée ».
    """
    sonde = probe_curriculum(registre)

    assert sonde["official_versions"] == 1
    assert "1 version(s) publiée(s)" in \
        sonde["capabilities"]["curriculum_retrieval"]["reason"]


# ----------------------------------------------------------------------
# 4. Le registre tient sous accès concurrent
# ----------------------------------------------------------------------

def test_le_registre_tient_sous_lectures_et_ecritures_concurrentes(registre):
    """
    Le verrou est dans le registre ; ce test mesure qu'il tient.

    Les écritures visent une version **en préparation** : le registre refuse
    d'ajouter une unité à une version publiée, et c'est sa règle, pas un défaut
    de concurrence. Écrire le test contre la version publiée aurait mesuré ce
    refus au lieu du verrou.
    """
    registre.register_version(CurriculumVersion(
        version_id="v-2027", education_system=SYSTEME,
        academic_year="2027-2028", provenance=_officielle(),
    ))
    erreurs = []
    resultats = []

    def _lire():
        try:
            for _ in range(50):
                resultats.append(
                    registre.provenance_of(
                        registre.units_in_version("v-2026")[0].unit_id,
                    )["status"],
                )
        except Exception as erreur:  # pragma: no cover - défaut réel si atteint
            erreurs.append(erreur)

    def _ecrire(indice):
        try:
            for semaine in range(20, 30):
                registre.add_unit(CurriculumUnit(
                    version_id="v-2027", grade=Grade(f"g{indice}", "Niveau"),
                    subject=Subject("maths", "Mathématiques"),
                    period=Period(academic_year="2027-2028", week=semaine),
                    official_title=f"Unité {indice}-{semaine}",
                    provenance=_officielle(),
                ))
        except Exception as erreur:  # pragma: no cover - défaut réel si atteint
            erreurs.append(erreur)

    fils = [threading.Thread(target=_lire) for _ in range(4)]
    fils += [threading.Thread(target=_ecrire, args=(i,)) for i in range(1, 4)]
    for fil in fils:
        fil.start()
    for fil in fils:
        fil.join()

    assert erreurs == []
    assert set(resultats) == {"FOUND"}
    assert registre.registry_report()["units"] == 1 + 3 * 10


# ----------------------------------------------------------------------
# 5. La latence est mesurée, pas promise
# ----------------------------------------------------------------------

def test_la_latence_est_mesuree_sans_seuil_declare(registre):
    """Une cible de performance est une décision de déploiement."""
    mesure = measure_latency(_question(), registre, runs=20)

    assert mesure["measured"] is True
    assert mesure["min_ms"] <= mesure["median_ms"] <= mesure["max_ms"]
    assert "décision de déploiement" in mesure["note"]


def test_aucune_repetition_ne_produit_aucune_mesure(registre):
    """Zéro répétition ne doit pas rendre un chiffre."""
    assert measure_latency(_question(), registre, runs=0)["measured"] is False


# ----------------------------------------------------------------------
# 6. Ce que la résilience ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_le_repli_depuis_un_cache():
    """Répondre depuis ailleurs, c'est répondre depuis l'invention."""
    interdits = " ".join(resilience_report()["does_not"])

    assert "depuis un cache" in interdits
    assert "leçon générique" in interdits
    assert "cible de latence" in interdits


def test_le_rapport_reutilise_les_etats_de_la_plateforme(registre):
    """Un second vocabulaire serait une chose de plus à garder alignée."""
    rapport = resilience_report(registre)

    assert DISPONIBLE in rapport["states"]
    assert rapport["probe"]["state"] in rapport["states"]
