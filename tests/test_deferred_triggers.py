"""
Les capacités différées et leurs déclencheurs mesurés (VOLET 36, ch. H).

Le dernier chapitre du VOLET est le seul à ne rien construire — et c'est sa
conclusion qui est le travail. Base vectorielle, base graphe, stockage objet,
flux d'événements, acquisition automatisée : chacune est différée **avec son
déclencheur écrit**.

Un déclencheur écrit dans un document est un déclencheur que personne ne relit :
« au-delà de 100 000 entités » est vrai le jour où on l'écrit et oublié six mois
plus tard. Ces tests épinglent que la mesure existe, qu'elle se tait tant que
rien n'est franchi, et qu'elle distingue « mesuré, en dessous » de « ce fait ne
se lit pas depuis le dépôt ».
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine import deferred_triggers  # noqa: E402
from src.knowledge_engine.deferred_triggers import (  # noqa: E402
    SEUIL_ENTITES,
    SEUIL_VECTEURS,
    deferred_report,
)
from src.proactive.detectors import DETECTEURS, capacites_differees  # noqa: E402

#: Les cinq capacités que le plan diffère.
ATTENDUES = {
    "vector_database", "graph_database", "object_storage_for_knowledge",
    "event_streams", "automated_acquisition",
}


def test_les_cinq_capacites_differees_portent_leur_declencheur():
    """
    Différé n'est pas refusé : chaque capacité dit ce qui rouvrirait la décision.
    """
    rapport = deferred_report()
    capacites = {entree["capability"]: entree for entree in rapport["capabilities"]}

    assert set(capacites) == ATTENDUES
    for nom, entree in capacites.items():
        assert entree["trigger"], f"« {nom} » ne dit pas ce qui rouvrirait la décision"
        assert entree["note"], f"« {nom} » ne dit pas pourquoi elle est différée"


def test_aucun_declencheur_n_est_atteint_aujourd_hui(monkeypatch):
    """
    L'état mesuré du dépôt, et non une opinion sur ce qu'il faudrait construire.

    Ce test échouera le jour où un seuil sera franchi — c'est exactement son
    rôle : il transforme un paragraphe en alarme.

    Le compte des documents sénégalais est neutralisé ici : le moteur de
    connaissances est un singleton de processus, et un autre test qui y dépose
    un élément `country:sn` ferait échouer celui-ci pour une raison qui n'a rien
    à voir avec le dépôt. Le déclencheur d'acquisition a son propre test.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_documents_senegalais", lambda: 0)

    rapport = deferred_report()

    assert rapport["met"] == [], (
        "Un déclencheur est franchi : rouvrir la décision avec un ADR plutôt "
        "que de modifier ce test."
    )


def test_une_source_activee_declenche_l_acquisition_automatisee(monkeypatch):
    """
    **Ce test a changé de mesure le 2026-08-14 (ADR-021), et c'est le sujet.**

    Il vérifiait que le premier document sénégalais renversait le déclencheur.
    C'était circulaire : rien dans le dépôt ne pouvait produire ce document tant
    que l'acquisition n'existait pas, donc `met` ne pouvait devenir vrai par
    aucun chemin. Le déclencheur mesurait le **résultat** de la capacité
    différée.

    Il mesure désormais ce qu'une personne décide — une source activée au
    registre — et cela peut bouger sans que la capacité existe.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_sources_activees", lambda: 0)
    avant = next(e for e in deferred_report()["capabilities"]
                 if e["capability"] == "automated_acquisition")

    monkeypatch.setattr(deferred_triggers, "_compter_sources_activees", lambda: 2)
    apres = next(e for e in deferred_report()["capabilities"]
                 if e["capability"] == "automated_acquisition")

    assert avant["met"] is False
    assert apres["met"] is True and apres["measured"] == 2


def test_le_declencheur_de_l_acquisition_ne_mesure_plus_son_propre_resultat(monkeypatch):
    """
    La garde qui empêche la circularité de revenir : le nombre de documents
    sénégalais ne doit plus décider du déclencheur.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_sources_activees", lambda: 0)
    monkeypatch.setattr(deferred_triggers, "_compter_documents_senegalais", lambda: 5000)

    entree = next(e for e in deferred_report()["capabilities"]
                  if e["capability"] == "automated_acquisition")

    assert entree["met"] is False, "Le corpus décide encore du déclencheur"
    assert entree["measured"] == 0
    assert "activée" in entree["trigger"]
    # La capacité est construite : ce qui reste est une décision humaine.
    assert entree["status"] == "built_and_gated"


def test_non_mesurable_n_est_pas_la_meme_reponse_que_non_atteint():
    """
    `met: false` dit « mesuré, en dessous ». `measurable: false` dit « ce fait
    ne se lit pas depuis le dépôt » — un second déploiement est une réalité
    d'exploitation, pas une ligne de code. Les confondre ferait passer une
    absence de mesure pour une mesure rassurante.
    """
    capacites = {e["capability"]: e for e in deferred_report()["capabilities"]}

    assert capacites["object_storage_for_knowledge"]["measurable"] is False
    assert capacites["event_streams"]["measurable"] is False
    assert capacites["vector_database"]["measurable"] is True
    assert set(deferred_report()["unmeasurable"]) == {
        "object_storage_for_knowledge", "event_streams",
    }


def test_une_mesure_impossible_ne_devient_pas_zero(monkeypatch):
    """
    Une panne de lecture rendue `0` ferait passer une base illisible pour une
    base vide — et un seuil non atteint pour une bonne nouvelle.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_connaissances", lambda: None)

    entree = next(
        e for e in deferred_report()["capabilities"] if e["capability"] == "vector_database"
    )

    assert entree["measured"] is None
    assert entree["measurable"] is False
    assert entree["met"] is False


def test_le_compte_d_entites_dit_quel_magasin_l_a_rendu():
    """
    En `in-memory`, le compte vaut 0 par construction — rien ne persiste. Le
    dire évite de lire ce 0 comme une mesure du corpus.
    """
    entree = next(
        e for e in deferred_report()["capabilities"] if e["capability"] == "graph_database"
    )

    assert "in-memory" in entree["note"] or "sqlite" in entree["note"]
    assert entree["threshold"] == SEUIL_ENTITES


# ----------------------------------------------------------------------
# Le détecteur : silencieux tant que rien n'est franchi
# ----------------------------------------------------------------------

def test_le_detecteur_se_tait_tant_qu_aucun_seuil_n_est_franchi(monkeypatch):
    """
    C'est ce silence qui fait sa valeur. Un détecteur qui parlerait à chaque
    scan pour dire « toujours pas 100 000 entités » deviendrait invisible.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_documents_senegalais", lambda: 0)

    assert capacites_differees() == []


def test_le_detecteur_parle_le_jour_ou_un_seuil_est_franchi(monkeypatch):
    """
    La contrepartie du silence, vérifiée plutôt que supposée : sans ce test,
    rien ne dirait que le détecteur sait parler.
    """
    monkeypatch.setattr(deferred_triggers, "_compter_documents_senegalais", lambda: 0)
    monkeypatch.setattr(
        deferred_triggers, "_compter_connaissances", lambda: SEUIL_VECTEURS + 1
    )

    trouvees = capacites_differees()

    assert len(trouvees) == 1
    observation = trouvees[0].to_dict()
    assert "vector_database" in observation["finding"]
    assert observation["evidence"]["capabilities"][0]["measured"] == SEUIL_VECTEURS + 1
    assert "ADR" in observation["suggested_action"]
    assert "Rien n'a été construit" in observation["suggested_action"]


def test_le_detecteur_est_declare_au_registre_des_scans():
    """Un détecteur absent du registre ne tourne jamais."""
    assert DETECTEURS["deferred_capabilities"] is capacites_differees


@pytest.mark.parametrize("capacite", sorted(ATTENDUES))
def test_aucune_de_ces_capacites_n_a_ete_construite(capacite):
    """
    Le chapitre H ne construit rien, et ce test le garde.

    Il échouera si quelqu'un ajoute une dépendance à l'une de ces
    infrastructures sans passer par un ADR — ce qui est le moment de la décision,
    pas un détail d'implémentation.
    """
    interdits = {
        "vector_database": ("qdrant", "weaviate", "pinecone", "milvus", "chromadb"),
        "graph_database": ("neo4j", "networkx", "arangodb", "janusgraph"),
        # `boto3` n'est pas dans cette liste : le stockage objet **existe** pour
        # le service de fichiers depuis l'ADR-016. Ce qui est différé, c'est d'y
        # déplacer la connaissance — et cela se verrait dans le moteur de
        # connaissances, pas dans les dépendances.
        "object_storage_for_knowledge": ("minio", "s3fs"),
        "event_streams": ("kafka", "pika", "celery", "redis"),
        "automated_acquisition": ("scrapy", "apscheduler"),
    }[capacite]

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "requirements.txt"), encoding="utf-8") as fichier:
        dependances = fichier.read().lower()

    presentes = [nom for nom in interdits if nom in dependances]
    assert presentes == [], (
        f"« {capacite} » a une dépendance ({', '.join(presentes)}) alors que son "
        "déclencheur n'est pas atteint : écrire l'ADR qui l'assume."
    )


def test_un_parcours_refuse_est_compte_et_franchit_le_declencheur_graphe():
    """
    La deuxième clause du déclencheur était **écrite et non mesurée** : le
    magasin refusait au-delà de la profondeur 3, et personne ne comptait. Un
    refus est pourtant le signal le plus direct qu'une base graphe manque —
    quelqu'un a posé la question que le magasin ne sait pas traiter.

    Corrigé le 2026-08-14, suite au relevé de l'ADR-021.
    """
    from src.knowledge_engine.entities import (
        EntityRefused,
        InMemoryEntityStore,
        depth_refusals,
        reset_depth_refusals,
    )

    reset_depth_refusals()
    try:
        avant = next(e for e in deferred_report()["capabilities"]
                     if e["capability"] == "graph_database")
        assert avant["met"] is False
        assert avant["depth_refusals"] == 0

        magasin = InMemoryEntityStore()
        for _ in range(deferred_triggers.SEUIL_REFUS_DE_PROFONDEUR):
            with pytest.raises(EntityRefused):
                magasin.neighbours("x", depth=5)

        apres = next(e for e in deferred_report()["capabilities"]
                     if e["capability"] == "graph_database")
        assert apres["depth_refusals"] == deferred_triggers.SEUIL_REFUS_DE_PROFONDEUR
        assert apres["met"] is True, "Une demande observée ne franchit pas le seuil"
        assert depth_refusals()["max_requested"] == 5
    finally:
        # Le compteur est partagé par le processus : le laisser plein ferait
        # passer les tests suivants pour une demande de base graphe.
        reset_depth_refusals()


def test_un_parcours_dans_les_bornes_ne_compte_pas_comme_une_demande():
    """La contrepartie : un compteur qui monte tout seul ne mesure rien."""
    from src.knowledge_engine.entities import (
        InMemoryEntityStore,
        depth_refusals,
        reset_depth_refusals,
    )

    reset_depth_refusals()
    try:
        InMemoryEntityStore().neighbours("x", depth=3)
        assert depth_refusals()["count"] == 0
    finally:
        reset_depth_refusals()
