"""
Le registre des versions officielles (VOLET 3 de Darra J).

Un registre de curriculum a une obligation qu'un magasin ordinaire n'a pas :
**il doit être incapable de perdre l'histoire.** Quand une autorité publie le
programme 2027, celui de 2026 ne devient pas faux — il devient *le programme de
2026*, et une question sur cette année-là doit encore le trouver.

Ce que ces tests gardent :

1. **Rien n'est remplacé en silence.** Réinscrire un identifiant avec un autre
   contenu est refusé, les deux empreintes nommées.
2. **Publier remplace sans détruire.** La version précédente passe `SUPERSEDED`
   et reste lisible.
3. **Publier exige un décideur nommé** : l'autorité institutionnelle reste
   humaine.
4. **Deux versions officielles simultanées rendent `AMBIGUOUS`**, jamais un
   choix.
5. **La provenance se remonte entièrement** — « d'où vient exactement ce fait ? »
   a une réponse ou n'en a aucune, jamais une moitié.
"""

import os
import sys

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
from src.darra_j import fixture_provenance as provenance_de_fixture  # noqa: E402
from src.darra_j.registry import (  # noqa: E402
    AMBIGU,
    INCONNU,
    TROUVE,
    CurriculumRegistry,
    RegistryRefused,
    unit_refusal_rules,
)

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle(document="jo://curriculum/2026"):
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document=document,
        document_hash="a" * 64,
        publication_date="2026-07-01",
    )


def _version(identifiant="v-2026", annee="2026-2027", provenance=None, **extra):
    """Une version de curriculum."""
    return CurriculumVersion(
        version_id=identifiant, education_system=SYSTEME, academic_year=annee,
        provenance=provenance or _officielle(), **extra,
    )


def _unite(version_id="v-2026", titre="Titre officiel", semaine=10, provenance=None):
    """Une unité de curriculum."""
    return CurriculumUnit(
        version_id=version_id, grade=Grade("g6", "Sixième"),
        subject=Subject("maths", "Mathématiques"),
        period=Period(academic_year="2026-2027", week=semaine),
        official_title=titre, provenance=provenance or _officielle(),
    )


@pytest.fixture
def registre():
    """Un registre neuf."""
    return CurriculumRegistry()


def _publier(registre, version, decideur="Direction des curricula"):
    """Amène une version jusqu'à la publication."""
    registre.register_version(version)
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        registre.advance(version.version_id, etat)
    return registre.publish(version.version_id, decided_by=decideur)


# ----------------------------------------------------------------------
# 1. Rien n'est remplacé en silence
# ----------------------------------------------------------------------

def test_reinscrire_a_l_identique_est_sans_effet(registre):
    """Ce n'est pas une erreur : c'est un import rejoué."""
    registre.register_version(_version())

    rendue = registre.register_version(_version())

    assert rendue.version_id == "v-2026"
    assert registre.registry_report()["versions"] == 1


def test_reinscrire_un_contenu_different_est_refuse(registre):
    """Le remplacement silencieux est la seule panne sans trace."""
    registre.register_version(_version(provenance=_officielle("jo://a")))

    with pytest.raises(RegistryRefused) as refus:
        registre.register_version(_version(provenance=_officielle("jo://b")))

    assert "contenu différent" in str(refus.value)
    assert "…" in str(refus.value)  # les deux empreintes sont nommées


def test_aucune_methode_de_suppression_n_existe(registre):
    """Il n'y a rien à appeler dans un moment de confiance."""
    interdits = {"delete", "remove", "drop", "clear", "purge"}

    assert not interdits & {nom for nom in dir(registre) if not nom.startswith("_")}


def test_une_unite_contradictoire_est_refusee(registre):
    """Deux textes officiels pour la même case sont un conflit."""
    registre.register_version(_version())
    registre.add_unit(_unite(titre="Le texte officiel"))

    with pytest.raises(RegistryRefused) as refus:
        registre.add_unit(_unite(titre="Un autre texte officiel"))

    assert "conflit" in str(refus.value)


def test_on_n_ajoute_pas_une_unite_a_une_version_publiee(registre):
    """Ce serait modifier l'officiel sans que rien ne le dise."""
    version = _version()
    _publier(registre, version)

    with pytest.raises(RegistryRefused) as refus:
        registre.add_unit(_unite())

    assert "en vigueur" in str(refus.value)


# ----------------------------------------------------------------------
# 2. Publier remplace sans détruire
# ----------------------------------------------------------------------

def test_publier_remplace_la_version_precedente(registre):
    """La précédente passe `SUPERSEDED`, elle ne disparaît pas."""
    _publier(registre, _version("v-2026"))
    resultat = _publier(registre, _version("v-2026-bis"))

    assert resultat["superseded"]["version_id"] == "v-2026"
    assert registre.get_version("v-2026").status is CurriculumStatus.SUPERSEDED


def test_une_version_remplacee_reste_lisible(registre):
    """Une question historique doit encore la trouver."""
    _publier(registre, _version("v-2026"))
    _publier(registre, _version("v-2026-bis"))

    ancienne = registre.resolve_version("2026-2027", version_id="v-2026")

    assert ancienne["status"] == TROUVE
    assert ancienne["version"].status is CurriculumStatus.SUPERSEDED


def test_une_version_publiee_ne_redevient_pas_brouillon(registre):
    """La machine d'états du modèle canonique s'applique au registre."""
    _publier(registre, _version())

    with pytest.raises(RegistryRefused):
        registre.advance("v-2026", CurriculumStatus.PARSED)


# ----------------------------------------------------------------------
# 3. Publier exige un décideur
# ----------------------------------------------------------------------

def test_publier_sans_decideur_est_refuse(registre):
    """Une publication anonyme ne peut être ni contestée ni confirmée."""
    version = _version()
    registre.register_version(version)
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        registre.advance(version.version_id, etat)

    with pytest.raises(RegistryRefused) as refus:
        registre.publish("v-2026", decided_by="   ")

    assert "qui décide" in str(refus.value)


def test_le_decideur_est_consigne(registre):
    """Sans trace, la décision n'appartient à personne."""
    _publier(registre, _version(), decideur="Inspection générale")

    trace = registre.history()

    assert any(e.get("decided_by") == "Inspection générale" for e in trace)


# ----------------------------------------------------------------------
# 4. Résolution : trouvée, inconnue, ou ambiguë
# ----------------------------------------------------------------------

def test_sans_version_officielle_la_resolution_rend_inconnu(registre):
    """C'est l'état attendu aujourd'hui, et il se lit."""
    resultat = registre.resolve_version("2026-2027")

    assert resultat["status"] == INCONNU
    assert "vide tant qu'une autorité" in resultat["reason"]


def test_une_seule_version_officielle_est_trouvee(registre):
    """Le cas nominal."""
    _publier(registre, _version())

    resultat = registre.resolve_version("2026-2027")

    assert resultat["status"] == TROUVE
    assert resultat["version"].version_id == "v-2026"


def test_deux_versions_officielles_simultanees_rendent_ambigu(registre):
    """En masquer une par un tri arbitraire la rendrait invisible."""
    _publier(registre, _version("v-a"))
    # Publier la seconde en nommant explicitement qu'elle ne remplace rien.
    version = _version("v-b")
    registre.register_version(version)
    for etat in (CurriculumStatus.PARSED, CurriculumStatus.VALIDATION_REQUIRED,
                 CurriculumStatus.VALIDATED):
        registre.advance("v-b", etat)
    registre.advance("v-b", CurriculumStatus.PUBLISHED, decided_by="X")

    resultat = registre.resolve_version("2026-2027")

    assert resultat["status"] == AMBIGU
    assert set(resultat["candidates"]) == {"v-a", "v-b"}


def test_une_fixture_publiee_ne_fait_pas_autorite(registre):
    """Publiée ou non, une fixture ne répond jamais comme officielle."""
    _publier(registre, _version(provenance=provenance_de_fixture("v3")))

    resultat = registre.resolve_version("2026-2027")

    assert resultat["status"] == INCONNU


def test_une_version_non_officielle_existe_sans_repondre(registre):
    """Elle est lisible ; elle ne fait pas autorité."""
    registre.register_version(_version(provenance=provenance_de_fixture("v3")))

    demandee = registre.resolve_version("2026-2027", version_id="v-2026")

    assert demandee["status"] == INCONNU
    assert "ne fait pas autorité" in demandee["reason"]
    assert registre.get_version("v-2026") is not None


# ----------------------------------------------------------------------
# 5. La provenance se remonte entièrement
# ----------------------------------------------------------------------

def test_la_provenance_d_une_unite_remonte_jusqu_au_document(registre):
    """« D'où vient exactement ce fait ? » doit avoir une réponse complète."""
    registre.register_version(_version())
    unite = registre.add_unit(_unite())

    chaine = registre.provenance_of(unite.unit_id)

    assert chaine["status"] == TROUVE
    assert chaine["authority"] == "Ministère de l'Éducation nationale"
    assert chaine["source_document"] == "jo://curriculum/2026"
    assert chaine["document_hash"] == "a" * 64
    assert chaine["unit"]["content_hash"]
    assert chaine["version"]["version_id"] == "v-2026"


def test_une_unite_inconnue_ne_rend_pas_une_chaine_partielle(registre):
    """Une moitié de provenance se lirait comme une réponse."""
    chaine = registre.provenance_of("inexistante")

    assert chaine["status"] == INCONNU
    assert "authority" not in chaine


def test_la_provenance_dit_si_le_fait_est_officiel(registre):
    """C'est la question qu'un lecteur pose juste après « d'où vient-il ? »."""
    registre.register_version(_version(provenance=provenance_de_fixture("v3")))
    unite = registre.add_unit(_unite(provenance=provenance_de_fixture("v3")))

    assert registre.provenance_of(unite.unit_id)["is_official"] is False


# ----------------------------------------------------------------------
# 6. Le rapport
# ----------------------------------------------------------------------

def test_le_rapport_dit_que_rien_n_est_persiste(registre):
    """Laisser croire qu'un redémarrage garde une version officielle serait pire."""
    rapport = registre.registry_report()

    assert rapport["persisted"] is False
    assert "ADR-005" in rapport["persistence_note"]


def test_le_rapport_dit_l_etat_honnete_du_curriculum(registre):
    """L'état attendu aujourd'hui est écrit noir sur blanc."""
    interdits = " ".join(registre.registry_report()["does_not"])

    assert "OFFICIAL CURRICULUM DATA PENDING" in interdits


def test_les_refus_d_ajout_sont_documentes():
    """Un refus qu'on ne peut pas lire est un refus qu'on contourne."""
    regles = " ".join(unit_refusal_rules())

    assert "version publiée" in regles
    assert "conflit" in regles
