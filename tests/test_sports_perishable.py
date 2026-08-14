"""
Sport : ce qui périme en jours, et ce qui ne périme jamais (phases 56.1 et 56.2).

Le sport casse le modèle de fraîcheur du VOLET 53, et il le casse d'une façon
qui mérite d'être nommée. Ce modèle mesure en **années**, parce qu'il a été écrit
pour des statistiques : un chiffre de population publié une fois l'an est frais à
deux ans. Un classement est périmé le dimanche soir. Une cadence en années ne
peut pas dire cela — sa plus petite unité est l'année, et déclarer une table
fraîche pendant un an serait la réponse la plus confortablement fausse que cette
plateforme puisse donner.

La seconde distinction est celle que le sport rend évidente et que tous les
domaines partagent :

- **Un résultat est daté et permanent.** La finale du 18 décembre 2022 aura
  toujours été jouée, avec le même score, en 2050. La marquer `STALE` serait une
  absurdité ; la marquer `FRESH` en serait une autre. Elle est `PERMANENT`, une
  **troisième** chose.
- **Un classement est daté et périme.** Le servir sans sa date n'est pas « un peu
  dépassé » : c'est une affirmation sur aujourd'hui que personne n'a faite.

Et rien ici ne classe un texte : le genre d'un fait est **déclaré**. Un genre
deviné poserait une étiquette « permanent » sur ce qui expire — le défaut exact
que ce module existe pour empêcher.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.domains import NOT_ENABLED, domain_state  # noqa: E402
from src.knowledge_engine.freshness import Freshness  # noqa: E402
from src.knowledge_engine.perishable import (  # noqa: E402
    GENRES,
    PERMANENT,
    freshness_of_date,
    kind_of,
    perishability_report,
    valid_until,
)
from src.knowledge_engine.scope import (  # noqa: E402
    NATIONAL_SUBJECTS,
    KnowledgeSubject,
    parse_subject,
)


def _le(annee, mois, jour):
    """Un instant de référence : le temps vient de l'appelant."""
    return datetime(annee, mois, jour, tzinfo=timezone.utc)


# ----------------------------------------------------------------------
# 1. Un résultat ne vieillit pas (56.1)
# ----------------------------------------------------------------------

def test_un_resultat_est_permanent_ni_frais_ni_perime():
    """
    La finale du 18 décembre 2022 aura toujours été jouée. `STALE` serait une
    absurdité, `FRESH` en serait une autre : c'est une troisième chose.
    """
    verdict = freshness_of_date("2022-12-18", "result", now=_le(2050, 1, 1))

    assert verdict["status"] == PERMANENT
    assert verdict["status"] not in (Freshness.FRESH.value, Freshness.STALE.value)
    assert verdict["age_days"] > 9000


def test_un_record_reste_vrai_meme_battu():
    """Ce qui change alors, c'est qu'un **autre** fait daté existe."""
    verdict = freshness_of_date("1968-10-18", "record", now=_le(2026, 8, 14))

    assert verdict["status"] == PERMANENT
    assert "reste vrai même battu" in verdict["reason"]


# ----------------------------------------------------------------------
# 2. Un classement périme en jours
# ----------------------------------------------------------------------

def test_un_classement_est_frais_quelques_jours():
    """Sept jours : la durée d'une journée de championnat."""
    verdict = freshness_of_date("2026-08-10", "standing", now=_le(2026, 8, 14))

    assert verdict["status"] == Freshness.FRESH.value
    assert verdict["age_days"] == 4
    assert verdict["valid_days"] == 7


def test_un_classement_de_six_semaines_est_perime_et_rendu_quand_meme():
    """
    Le remplacer par une valeur d'apparence plus récente serait une
    fabrication ; il reste rendu **avec sa date**.
    """
    verdict = freshness_of_date("2026-07-01", "standing", now=_le(2026, 8, 14))

    assert verdict["status"] == Freshness.STALE.value
    assert verdict["date"] == "2026-07-01"
    assert "fabrication" in verdict["reason"]


def test_la_frontiere_des_jours_est_explicite():
    """
    Écrite ici pour qu'un changement de seuil se voie dans un diff plutôt que
    de faire basculer des faits en silence.
    """
    statuts = {
        jour: freshness_of_date(
            f"2026-08-{jour:02d}", "standing", now=_le(2026, 8, 20),
        )["status"]
        for jour in (13, 12, 10, 9)
    }

    # Validité 7 jours, marge 3 : frais jusqu'à 7, vieillissant jusqu'à 10,
    # périmé au-delà. Le jour 12 fait 8 jours d'âge — déjà hors validité.
    assert statuts == {13: "FRESH", 12: "AGING", 10: "AGING", 9: "STALE"}


def test_chaque_genre_perissable_declare_sa_duree():
    """Un genre périssable sans durée serait un genre qui ne périme jamais."""
    for nom, genre in GENRES.items():
        if genre["perishable"]:
            assert genre.get("valid_days"), f"« {nom} » périme sans durée déclarée"


def test_la_date_limite_se_calcule_pour_ce_qui_perime():
    """Et pas pour ce qui ne périme pas : elle n'aurait aucun sens."""
    assert valid_until("2026-08-10", "standing") == "2026-08-17"
    assert valid_until("2022-12-18", "result") is None


# ----------------------------------------------------------------------
# 3. Rien n'est deviné
# ----------------------------------------------------------------------

def test_un_genre_non_declare_ne_recoit_aucun_verdict():
    """
    Le deviner poserait une étiquette « permanent » sur ce qui expire : c'est
    le défaut que ce module existe pour empêcher.
    """
    verdict = freshness_of_date("2026-08-13", "rumeur", now=_le(2026, 8, 14))

    assert verdict["status"] == Freshness.UNKNOWN.value
    assert "Le deviner poserait" in verdict["reason"]
    assert "standing" in verdict["reason"], "Les genres connus sont nommés"


def test_un_fait_sans_date_n_est_pas_recent():
    """Une donnée non datée n'est pas récente — elle en a seulement l'air."""
    verdict = freshness_of_date("", "result")

    assert verdict["status"] == Freshness.UNKNOWN.value
    assert verdict["age_days"] == "UNKNOWN"


def test_une_date_illisible_ne_devient_pas_aujourd_hui():
    """Rien n'est deviné, surtout pas une date."""
    assert freshness_of_date("hier", "standing")["age_days"] == "UNKNOWN"


def test_le_temps_vient_de_l_appelant():
    """Une fonction qui lit l'horloge en douce ne se teste qu'en attendant."""
    premier = freshness_of_date("2026-08-01", "squad", now=_le(2026, 8, 2))
    second = freshness_of_date("2026-08-01", "squad", now=_le(2027, 8, 2))

    assert premier["age_days"] == 1
    assert second["status"] == Freshness.STALE.value


def test_un_genre_inconnu_n_a_pas_de_declaration():
    """`kind_of` doit distinguer déclaré et inventé."""
    assert kind_of("standing")["perishable"] is True
    assert kind_of("rumeur") is None


# ----------------------------------------------------------------------
# 4. Le domaine sport (56.2)
# ----------------------------------------------------------------------

def test_sports_est_un_sujet_declare():
    """Ajouté après relecture, comme l'énumération l'exige."""
    assert parse_subject("sports") is KnowledgeSubject.SPORTS


def test_le_sport_n_est_pas_un_sujet_territorial():
    """
    Sa particularité n'est pas le territoire mais le temps : une Coupe du monde
    n'appartient à aucun pays, et un classement mondial non plus.
    """
    assert KnowledgeSubject.SPORTS not in NATIONAL_SUBJECTS


def test_le_domaine_sport_a_des_sources_inscrites_et_endormies():
    """
    Mesuré : deux fédérations sont inscrites, **aucune n'est activée**. Le
    domaine n'a donc jamais eu le droit d'essayer — ce n'est pas un échec
    d'acquisition.
    """
    etat = domain_state("sports", "global")

    assert etat["state"] == NOT_ENABLED
    assert "FIFA" in etat["declared_sources"]
    assert etat["enabled_sources"] == []


def test_aucune_connaissance_sportive_n_a_ete_ecrite():
    """
    **La garde du VOLET.** Aucune source n'est joignable ; écrire un palmarès
    de mémoire serait exactement ce que ce dépôt refuse. Le domaine est vide,
    et il le dit.
    """
    etat = domain_state("sports", "global")

    assert etat["items"] is None
    assert "Activer une source" in etat["action"]


def test_le_rapport_dit_pourquoi_l_echelle_est_en_jours():
    """La raison doit survivre à celui qui l'a écrite."""
    rapport = perishability_report()

    assert rapport["scale"] == "jours"
    assert "années" in rapport["why_days"]
    assert "dimanche soir" in rapport["why_days"]


def test_le_rapport_nomme_ses_regles_et_ses_limites():
    """Ce qu'un lecteur doit savoir avant de lire un verdict."""
    rapport = perishability_report()

    regles = " ".join(rapport["rules"])
    assert "troisième chose" in regles
    assert "jamais deviné" in regles
    assert any("ne lit aucun contenu" in ligne for ligne in rapport["does_not"])


def test_une_federation_ne_fait_autorite_que_sur_ses_competitions():
    """
    Lui attribuer un pays entier serait faux : un championnat national relève
    de sa propre fédération, qui n'est pas inscrite ici.
    """
    from src.knowledge_engine.source_registry import load_registry

    fifa = [s for s in load_registry()["sources"] if s["name"] == "FIFA"][0]

    assert "Pas les championnats nationaux" in fifa["authority_scope"]
    assert fifa["enabled"] is False
