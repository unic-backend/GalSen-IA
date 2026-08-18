"""
Une production qui survit au processus qui l'a faite — ADR-005, pas une règle
de plus (VOLET M02 du moteur média).

`MediaProject` ne peut pas détruire une version en mémoire. Un magasin capable
d'en détruire une sur disque rendrait toute la garantie vaine, et un magasin qui
laisserait tomber un champ ferait revenir une production **subtilement
différente** de celle qui a été approuvée — le même échec, arrivé par la porte
de derrière.

Ce que ces tests gardent :

1. **L'aller-retour est sans perte** : mêmes versions, mêmes empreintes.
2. **Aucune suppression n'est exposée**, ni en mémoire ni en SQLite.
3. **Un enregistrement sans version est refusé**, jamais réparé.
4. **La décision du magasin vient d'ADR-005**, pas d'un second interrupteur.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.core.project import (  # noqa: E402
    ORIGINE_GENEREE,
    ORIGINE_SOURCEE,
    Artifact,
    MediaProject,
    VersionStatus,
)
from src.media.core.store import (  # noqa: E402
    InMemoryProjectStore,
    ProjectStoreError,
    SQLiteProjectStore,
    from_record,
    project_store,
    store_report,
    to_record,
)


def _projet_riche():
    """Une production avec plusieurs versions, artefacts et corrections."""
    projet = MediaProject(objective="Documentaire de 3 minutes", created_by="awa")
    projet.new_version(
        created_by="awa", script="Texte v2",
        scenes=({"id": "s1", "duration": 4.0},),
        timeline=({"start": 0.0, "end": 4.0, "source": "rush-01"},),
        artifacts=(
            Artifact(artifact_id="a1", kind="video", origin=ORIGINE_GENEREE,
                     produced_by="wan-2.1"),
            Artifact(artifact_id="a2", kind="music", origin=ORIGINE_SOURCEE,
                     source="https://exemple/x.mp3", licence="CC-BY-4.0"),
        ),
        models={"video": "wan-2.1"}, prompts={"video": "un plan large"},
        outputs=("master.webm",),
    )
    projet.new_version(created_by="moussa", script="Texte v3")
    projet.set_status(projet.current.version_id, VersionStatus.APPROVED, by="awa")
    projet.record_correction(by="awa", target="scene-01", after="titre discret")
    return projet


@pytest.fixture(params=["memoire", "sqlite"])
def magasin(request, tmp_path):
    """Les deux magasins, soumis au même contrat."""
    if request.param == "memoire":
        return InMemoryProjectStore()
    return SQLiteProjectStore(str(tmp_path / "projets.sqlite"))


# ----------------------------------------------------------------------
# 1. L'aller-retour est sans perte
# ----------------------------------------------------------------------

def test_un_aller_retour_conserve_toutes_les_versions(magasin):
    """Ne garder que la version courante rendrait la règle fausse au redémarrage."""
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    assert [v.version_id for v in relu.versions] == \
        [v.version_id for v in projet.versions]
    assert len(relu.versions) == 3


def test_un_aller_retour_conserve_les_empreintes_de_contenu(magasin):
    """
    La garantie qui compte.

    Une production qui revient avec une empreinte différente est une production
    différente, même si elle *paraît* identique.
    """
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    assert [v.content_hash() for v in relu.versions] == \
        [v.content_hash() for v in projet.versions]


def test_un_aller_retour_conserve_les_etats(magasin):
    """« Approuvée » et « remplacée » doivent survivre au redémarrage."""
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    assert [v.status for v in relu.versions] == [v.status for v in projet.versions]
    assert relu.current.status is VersionStatus.APPROVED


def test_un_aller_retour_conserve_artefacts_et_provenance(magasin):
    """Perdre une licence en chemin fait sortir un média sans droits connus."""
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    artefacts = {a.artifact_id: a for a in relu.get_version(
        f"{projet.project_id}-v2").artifacts}
    assert artefacts["a2"].licence == "CC-BY-4.0"
    assert artefacts["a1"].produced_by == "wan-2.1"
    assert artefacts["a1"].is_generated is True


def test_un_aller_retour_conserve_les_corrections(magasin):
    """Elles servent de preuve : les perdre perd l'argument."""
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    assert [c.target for c in relu.corrections] == ["scene-01"]
    assert relu.corrections[0].by == "awa"


def test_le_manifeste_survit_a_l_aller_retour(magasin):
    """C'est le manifeste qu'un humain relira, pas les objets."""
    projet = _projet_riche()

    magasin.save(projet)
    relu = magasin.load(projet.project_id)

    avant, apres = projet.manifest(), relu.manifest()
    assert avant["version_count"] == apres["version_count"]
    assert avant["current_version"] == apres["current_version"]
    assert [v["content_hash"] for v in avant["versions"]] == \
        [v["content_hash"] for v in apres["versions"]]


# ----------------------------------------------------------------------
# 2. Rien ne se détruit, ici non plus
# ----------------------------------------------------------------------

@pytest.mark.parametrize("classe", [InMemoryProjectStore, SQLiteProjectStore])
def test_aucun_magasin_n_expose_de_suppression(classe):
    """Un magasin qui peut détruire rend la garantie mémoire vaine."""
    noms = dir(classe)

    assert not [n for n in noms if "delete" in n or "remove" in n or "purge" in n]
    assert not [n for n in noms if n.startswith("clear")]


def test_un_second_enregistrement_ne_perd_aucune_version(magasin):
    """Réécrire une production ne doit jamais la raccourcir."""
    projet = _projet_riche()
    magasin.save(projet)

    projet.new_version(created_by="awa", script="Texte v4")
    magasin.save(projet)

    relu = magasin.load(projet.project_id)
    assert len(relu.versions) == 4
    assert relu.get_version(f"{projet.project_id}-v1") is not None


def test_une_production_inconnue_rend_none(magasin):
    """`None` est une réponse ; fabriquer une production vide n'en est pas une."""
    assert magasin.load("prj-inexistant") is None


def test_les_productions_sont_listees(magasin):
    """Un magasin qu'on ne peut pas énumérer ne s'audite pas."""
    for objectif in ("Documentaire", "Publicité", "Leçon"):
        magasin.save(MediaProject(objective=objectif, created_by="awa"))

    assert len(magasin.list_projects()) == 3


# ----------------------------------------------------------------------
# 3. Un enregistrement abîmé est signalé, pas réparé
# ----------------------------------------------------------------------

def test_un_enregistrement_sans_version_est_refuse():
    """En fabriquer une masquerait la perte au lieu de la signaler."""
    with pytest.raises(ProjectStoreError) as refus:
        from_record({"project_id": "prj-x", "objective": "Un objectif",
                     "versions": []})

    assert "masquerait la perte" in str(refus.value)


def test_l_enregistrement_porte_tout_ce_qu_il_faut_pour_relire():
    """Un champ absent de l'enregistrement est un champ perdu au redémarrage."""
    enregistrement = to_record(_projet_riche())

    assert set(enregistrement) >= {
        "project_id", "objective", "created_at", "created_by", "versions",
        "corrections",
    }
    assert len(enregistrement["versions"]) == 3


# ----------------------------------------------------------------------
# 4. La décision du magasin vient d'ADR-005
# ----------------------------------------------------------------------

def test_le_defaut_est_le_magasin_par_defaut_de_la_plateforme(monkeypatch):
    """`in-memory` n'est pas un bouchon : c'est le défaut déclaré."""
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)

    assert project_store().backend == "in-memory"


def test_sqlite_est_choisi_par_la_variable_declaree(monkeypatch, tmp_path):
    """La règle a un seul endroit, et ce n'est pas ici."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))

    magasin = project_store()

    assert magasin.backend == "sqlite"
    assert str(tmp_path) in magasin.path


def test_le_rapport_refuse_un_second_interrupteur():
    """Huit copies d'une même règle finissent par diverger."""
    rapport = store_report()

    interdits = " ".join(rapport["does_not"])
    assert "GALSEN_STORAGE_BACKEND" in interdits
    assert "Supprimer une production" in interdits
    assert any("ADR-005" in regle for regle in rapport["rules"])
