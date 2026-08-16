"""
Une production qui se souvient de tous les états qu'elle a traversés
(VOLET M02 du moteur média).

La directive §18 finit sur la règle qui donne sa forme à tout le reste :
**ne jamais détruire une version antérieure.** C'est facile à approuver et
facile à casser, parce que la façon naturelle d'écrire un éditeur est de muter
l'état courant — et une fois la timeline mutée sur place, la version qu'un
client a approuvée hier n'existe plus.

Ce que ces tests gardent :

1. **Aucune suppression n'existe** — pas gardée : absente.
2. **Une version est figée** ; un nouvel état est une version de plus.
3. **Identité et contenu sont deux empreintes distinctes.**
4. **Un artefact sourcé sans licence est incomplet**, jamais « probablement
   libre ».
5. **Une correction est une preuve, pas une règle.**
"""

import dataclasses
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.core.project import (  # noqa: E402
    ORIGINE_GENEREE,
    ORIGINE_INCONNUE,
    ORIGINE_SOURCEE,
    Artifact,
    MediaProject,
    ProjectRefused,
    ProjectVersion,
    VersionStatus,
    project_report,
)


@pytest.fixture
def projet():
    """Une production ouverte sur un objectif."""
    return MediaProject(
        objective="Transformer un entretien en documentaire de 3 minutes",
        created_by="awa",
    )


# ----------------------------------------------------------------------
# 1. Rien ne se détruit
# ----------------------------------------------------------------------

def test_aucune_methode_de_suppression_n_existe():
    """
    Pas gardée : absente.

    Une suppression gardée finit toujours par être appelée avec le bon argument.
    """
    noms = dir(MediaProject)

    assert not [n for n in noms if "delete" in n or "remove" in n or "purge" in n]
    assert not [n for n in noms if n.startswith("clear")]


def test_une_version_remplacee_reste_lisible(projet):
    """Une question sur la semaine dernière doit trouver la semaine dernière."""
    premiere = projet.current

    projet.new_version(created_by="awa", script="Nouvelle version du texte")

    conservee = projet.get_version(premiere.version_id)
    assert conservee is not None
    assert conservee.status is VersionStatus.SUPERSEDED
    assert len(projet.versions) == 2


def test_le_contenu_d_une_version_remplacee_est_intact(projet):
    """« Remplacée » n'est pas « vidée »."""
    projet.new_version(script="Premier texte")
    premiere_v2 = projet.get_version(f"{projet.project_id}-v2")
    empreinte = premiere_v2.content_hash()

    projet.new_version(script="Deuxième texte")

    relue = projet.get_version(f"{projet.project_id}-v2")
    assert relue.script == "Premier texte"
    assert relue.content_hash() == empreinte


def test_meme_tout_rejete_il_reste_quelque_chose_a_regarder(projet):
    """Une production sans version courante n'aurait rien à montrer."""
    projet.set_status(projet.current.version_id, VersionStatus.REJECTED, by="awa")

    assert projet.current is not None
    assert projet.current.status is VersionStatus.REJECTED


# ----------------------------------------------------------------------
# 2. Une version est figée
# ----------------------------------------------------------------------

def test_une_version_ne_peut_pas_etre_modifiee(projet):
    """Muter l'état courant efface ce qui a été approuvé."""
    with pytest.raises(dataclasses.FrozenInstanceError):
        projet.current.script = "réécrit"


def test_un_nouvel_etat_est_une_version_de_plus(projet):
    """Le seul chemin vers un nouvel état."""
    deuxieme = projet.new_version(created_by="moussa", script="Texte")

    assert deuxieme.number == 2
    assert deuxieme.derived_from == f"{projet.project_id}-v1"
    assert deuxieme.created_by == "moussa"


def test_une_nouvelle_version_herite_de_la_courante(projet):
    """Sinon chaque version repartirait de zéro."""
    projet.new_version(script="Texte", objective="Objectif affiné")

    troisieme = projet.new_version(models={"video": "wan-2.1"})

    assert troisieme.script == "Texte"
    assert troisieme.objective == "Objectif affiné"
    assert troisieme.models == {"video": "wan-2.1"}


def test_un_champ_inconnu_est_refuse(projet):
    """L'ignorer ferait croire qu'une modification a été prise en compte."""
    with pytest.raises(ProjectRefused) as refus:
        projet.new_version(couleur_preferee="bleu")

    assert "prise en compte" in str(refus.value)


def test_l_identite_et_le_rang_ne_sont_pas_modifiables(projet):
    """Les réécrire casserait le lien entre les versions."""
    for champ in ("version_id", "number", "created_at", "derived_from"):
        with pytest.raises(ProjectRefused):
            projet.new_version(**{champ: "triché"})


# ----------------------------------------------------------------------
# 3. Identité et contenu
# ----------------------------------------------------------------------

def test_deux_versions_de_meme_contenu_partagent_l_empreinte(projet):
    """« Rien n'a changé » doit être dicible sans comparer les objets."""
    projet.new_version(script="Texte identique")
    avant = projet.current.content_hash()

    projet.new_version()

    assert projet.current.content_hash() == avant
    assert projet.current.version_id != f"{projet.project_id}-v2"


def test_un_changement_d_etat_ne_change_pas_le_contenu(projet):
    """Un changement d'état n'est pas un changement d'œuvre."""
    version = projet.new_version(script="Texte")
    avant = version.content_hash()

    approuvee = projet.set_status(version.version_id, VersionStatus.APPROVED,
                                  by="awa")

    assert approuvee.content_hash() == avant
    assert approuvee.status is VersionStatus.APPROVED


def test_l_instant_de_creation_n_entre_pas_dans_l_empreinte():
    """
    Deux enregistrements du même contenu à deux instants sont le même contenu.

    Darra J a payé exactement cette confusion : `ingested_at` entrait dans
    l'empreinte, et deux imports du même décret paraissaient différents.
    """
    commune = {"version_id": "v", "number": 1, "script": "Texte"}
    tot = ProjectVersion(**commune, created_at=1.0, created_by="awa")
    tard = ProjectVersion(**commune, created_at=999.0, created_by="moussa")

    assert tot.content_hash() == tard.content_hash()


# ----------------------------------------------------------------------
# 4. La provenance ne se devine pas
# ----------------------------------------------------------------------

def test_un_artefact_source_sans_licence_est_incomplet():
    """Il n'est pas « probablement libre » : il est incomplet, et le dit."""
    sans = Artifact(artifact_id="a1", kind="music", origin=ORIGINE_SOURCEE,
                    source="https://exemple/musique.mp3")

    assert sans.provenance_complete is False


def test_un_artefact_source_complet_est_complet():
    """Le cas nominal existe."""
    complet = Artifact(
        artifact_id="a1", kind="music", origin=ORIGINE_SOURCEE,
        source="https://exemple/musique.mp3", licence="CC-BY-4.0",
    )

    assert complet.provenance_complete is True


def test_un_artefact_genere_doit_nommer_ce_qui_l_a_produit():
    """« Généré » sans producteur ne se reproduit ni ne se conteste."""
    anonyme = Artifact(artifact_id="a2", kind="video", origin=ORIGINE_GENEREE)
    nomme = Artifact(artifact_id="a3", kind="video", origin=ORIGINE_GENEREE,
                     produced_by="wan-2.1")

    assert anonyme.provenance_complete is False
    assert nomme.provenance_complete is True
    assert nomme.is_generated is True


def test_une_origine_inventee_est_refusee():
    """Elle rendrait indistinguable le généré du fourni."""
    with pytest.raises(ProjectRefused) as refus:
        Artifact(artifact_id="a4", kind="video", origin="PROBABLEMENT_LIBRE")

    assert "indistinguable" in str(refus.value)


def test_une_origine_inconnue_reste_incomplete():
    """`UNKNOWN_ORIGIN` est un aveu, pas un laissez-passer."""
    inconnu = Artifact(artifact_id="a5", kind="image", origin=ORIGINE_INCONNUE)

    assert inconnu.provenance_complete is False


def test_le_manifeste_signale_ce_qui_bloque_une_livraison(projet):
    """Un média dont personne ne sait d'où il vient est un problème juridique."""
    projet.new_version(artifacts=(
        Artifact(artifact_id="ok", kind="video", origin=ORIGINE_GENEREE,
                 produced_by="wan-2.1"),
        Artifact(artifact_id="douteux", kind="music", origin=ORIGINE_SOURCEE,
                 source="quelque part"),
    ))

    manifeste = projet.manifest()

    bloquants = [a["artifact_id"] for a in manifeste["artifacts_without_provenance"]]
    assert bloquants == ["douteux"]
    assert manifeste["generated_artifacts"] == ["ok"]


# ----------------------------------------------------------------------
# 5. Une correction est une preuve, pas une règle
# ----------------------------------------------------------------------

def test_une_correction_n_est_pas_promue_en_regle(projet):
    """Apprendre en silence l'appliquerait à un client qui n'a rien demandé."""
    correction = projet.record_correction(
        by="awa", target="scene-02", before="texte géant", after="titre discret",
    )

    assert correction.as_dict()["promoted_to_rule"] is False
    assert "acte délibéré" in correction.as_dict()["why"]


def test_une_correction_anonyme_est_refusee(projet):
    """Elle ne pourrait être ni discutée ni retirée."""
    with pytest.raises(ProjectRefused):
        projet.record_correction(by="  ", target="scene-01")


def test_les_corrections_sont_conservees_dans_l_ordre(projet):
    """Elles servent de preuve : les perdre perd l'argument."""
    projet.record_correction(by="awa", target="scene-01")
    projet.record_correction(by="moussa", target="scene-02")

    assert [c.target for c in projet.corrections] == ["scene-01", "scene-02"]
    assert len(projet.manifest()["corrections"]) == 2


# ----------------------------------------------------------------------
# 6. Ce que le noyau refuse
# ----------------------------------------------------------------------

def test_une_production_sans_objectif_est_refusee():
    """Rien ne dirait si elle a réussi."""
    with pytest.raises(ProjectRefused) as refus:
        MediaProject(objective="   ")

    assert "si elle a réussi" in str(refus.value)


def test_approuver_une_version_remplacee_est_refuse(projet):
    """Cela publierait un état que quelqu'un a déjà dépassé."""
    premiere = projet.current
    projet.new_version(script="Suite")

    with pytest.raises(ProjectRefused) as refus:
        projet.set_status(premiere.version_id, VersionStatus.APPROVED, by="awa")

    assert "déjà dépassé" in str(refus.value)


def test_le_manifeste_montre_toutes_les_versions(projet):
    """Un manifeste qui ne montre que l'état courant interdit le retour arrière."""
    projet.new_version(script="A")
    projet.new_version(script="B")

    manifeste = projet.manifest()

    assert manifeste["version_count"] == 3
    assert len(manifeste["versions"]) == 3
    assert manifeste["current_version"] == projet.current.version_id


def test_le_rapport_refuse_la_suppression_et_la_promotion_automatique():
    """Les règles sont écrites là où elles sont appliquées."""
    interdits = " ".join(project_report()["does_not"])

    assert "Supprimer une version" in interdits
    assert "correction en règle permanente" in interdits
    assert "Deviner la provenance" in interdits
