"""
Plusieurs racines, et des opérations qu'on peut défaire (VOLET 34, ch. 07).

L'état des lieux (phase 1.1) avait conclu que le manque n'était **pas** la
sécurité : l'outil de fichiers résout déjà chemins absolus, `..` et liens
symboliques contre une racine, et l'écriture y est coupée par défaut. Ce qui
manquait, c'était de pouvoir déclarer **plusieurs** racines — `C:\\`, un disque
externe, un dossier de projets — et de rendre les opérations **réversibles**.

Ce fichier éprouve les deux, et surtout la propriété qui les justifie : quand un
agent se trompe, le travail de quelqu'un a bougé, et le moment où on s'en aperçoit
est rarement celui où l'on peut encore reconstituer l'état d'avant.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.storage.reversible import (  # noqa: E402
    QUARANTAINE,
    OperationRefused,
    ReversibleFiles,
    UndoRefused,
)
from src.storage.roots import RootRefused, declared_roots, report, resolve  # noqa: E402


@pytest.fixture
def deux_racines(tmp_path):
    """Une racine inscriptible et une racine en lecture seule."""
    projets = tmp_path / "projets"
    archives = tmp_path / "archives"
    projets.mkdir()
    archives.mkdir()
    (projets / "note.txt").write_text("contenu", encoding="utf-8")
    return declared_roots(f"projets:{projets}:rw,archives:{archives}")


@pytest.fixture
def fichiers(tmp_path, deux_racines):
    """Opérations réversibles, avec un journal isolé."""
    return ReversibleFiles(deux_racines, journal=str(tmp_path / "journal.jsonl"))


# ----------------------------------------------------------------------
# Déclarer des racines
# ----------------------------------------------------------------------

def test_plusieurs_racines_se_declarent(deux_racines):
    """Le manque que le brief nommait : une seule racine ne suffit pas."""
    assert [racine.name for racine in deux_racines] == ["projets", "archives"]
    assert [racine.writable for racine in deux_racines] == [True, False]


def test_une_racine_est_en_lecture_seule_par_defaut(tmp_path):
    """
    Déclarer un répertoire et vouloir y écrire sont deux intentions. Les
    confondre ferait de chaque déclaration une autorisation d'écriture.
    """
    (tmp_path / "docs").mkdir()

    racines = declared_roots(f"docs:{tmp_path / 'docs'}")

    assert racines[0].writable is False


def test_une_racine_malformee_est_signalee_et_ecartee(tmp_path, caplog):
    """
    Deviner une racine reviendrait à donner accès à un répertoire que personne
    n'a déclaré.
    """
    (tmp_path / "bon").mkdir()

    with caplog.at_level("ERROR"):
        racines = declared_roots(f"sans_chemin,inexistant:/n/existe/pas,bon:{tmp_path / 'bon'}")

    assert [racine.name for racine in racines] == ["bon"]
    assert "ignorée" in caplog.text


def test_un_nom_declare_deux_fois_est_refuse(tmp_path, caplog):
    """Deux racines du même nom rendraient la résolution non déterministe."""
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()

    with caplog.at_level("ERROR"):
        racines = declared_roots(f"p:{tmp_path / 'a'}:rw,p:{tmp_path / 'b'}:rw")

    assert len(racines) == 1
    assert racines[0].path.endswith("a")


# ----------------------------------------------------------------------
# Résoudre, et refuser
# ----------------------------------------------------------------------

def test_un_chemin_prefixe_du_nom_de_racine_se_resout(deux_racines):
    """C'est la forme qu'un agent lit et écrit le plus naturellement."""
    racine, absolu = resolve("projets/note.txt", deux_racines)

    assert racine.name == "projets"
    assert absolu.endswith("note.txt")


def test_un_chemin_hors_racines_est_refuse(deux_racines):
    """La propriété que l'outil de fichiers avait déjà, conservée à plusieurs racines."""
    with pytest.raises(RootRefused, match="hors des racines"):
        resolve("/etc/passwd", deux_racines)


def test_une_remontee_est_refusee(deux_racines):
    """`..` ne doit pas plus fonctionner avec deux racines qu'avec une."""
    with pytest.raises(RootRefused):
        resolve("projets/../../etc/passwd", deux_racines)


def test_un_lien_symbolique_qui_sort_est_refuse(tmp_path, deux_racines):
    """
    Le nom de la racine était bon, la destination ne l'est pas. La résolution
    passe par `realpath` **avant** la comparaison, pour cette raison précise.
    """
    dehors = tmp_path / "dehors.txt"
    dehors.write_text("secret", encoding="utf-8")
    lien = deux_racines[0].path + os.sep + "lien.txt"
    os.symlink(dehors, lien)

    with pytest.raises(RootRefused, match="sort de la racine"):
        resolve("projets/lien.txt", deux_racines)


def test_un_chemin_relatif_est_ambigu_quand_plusieurs_racines_existent(deux_racines):
    """
    Deviner la racine visée écrirait au hasard. Le refus nomme la forme
    attendue plutôt que de laisser chercher.
    """
    with pytest.raises(RootRefused, match="ambigu"):
        resolve("note.txt", deux_racines)


def test_un_chemin_relatif_reste_accepte_avec_une_seule_racine(tmp_path):
    """Le contre-test : ne pas casser le cas simple pour couvrir le cas double."""
    (tmp_path / "seule").mkdir()
    (tmp_path / "seule" / "x.txt").write_text("x", encoding="utf-8")
    racines = declared_roots(f"seule:{tmp_path / 'seule'}:rw")

    racine, absolu = resolve("x.txt", racines)

    assert racine.name == "seule" and absolu.endswith("x.txt")


def test_ecrire_dans_une_racine_en_lecture_seule_est_refuse(deux_racines):
    """Une racine déclarée sans `:rw` refuse l'écriture, pas seulement par convention."""
    with pytest.raises(RootRefused, match="lecture seule"):
        resolve("archives/x.txt", deux_racines, pour_ecriture=True)


def test_sans_racine_declaree_tout_est_refuse():
    """
    Le défaut sûr : aucune racine déclarée ne veut pas dire « tout le disque ».
    Le message dit quoi renseigner.
    """
    with pytest.raises(RootRefused, match="GALSEN_STORAGE_ROOTS"):
        resolve("/tmp/x", [])


def test_un_agent_peut_savoir_ou_il_a_le_droit_de_regarder(deux_racines):
    """Le découvrir par une série de refus serait une mauvaise façon de l'apprendre."""
    etat = report(deux_racines)

    assert etat["count"] == 2
    assert etat["writable_count"] == 1


# ----------------------------------------------------------------------
# Défaire ce qui a été fait
# ----------------------------------------------------------------------

def test_un_deplacement_s_annule(fichiers, deux_racines):
    """La propriété qui justifie tout ce module."""
    origine = os.path.join(deux_racines[0].path, "note.txt")
    operation = fichiers.move("projets/note.txt", "projets/rangé/note.txt", raison="tri")

    assert not os.path.exists(origine)

    fichiers.undo(operation.id)

    assert os.path.exists(origine)


def test_une_annulation_ne_se_rejoue_pas(fichiers):
    """Rejouer une annulation écraserait un état plus récent : une seconde perte."""
    operation = fichiers.move("projets/note.txt", "projets/a/note.txt", raison="tri")
    fichiers.undo(operation.id)

    with pytest.raises(UndoRefused, match="déjà annulée"):
        fichiers.undo(operation.id)


def test_rien_n_est_supprime_seulement_mis_en_quarantaine(fichiers, deux_racines):
    """
    Une suppression qu'un agent décide et qu'un humain découvre trois jours plus
    tard doit pouvoir se défaire. `os.remove` ne le permet pas.
    """
    operation = fichiers.remove("projets/note.txt", raison="obsolète")

    assert QUARANTAINE in operation.destination
    assert os.path.exists(operation.destination)
    assert open(operation.destination, encoding="utf-8").read() == "contenu"


def test_une_mise_en_quarantaine_s_annule(fichiers, deux_racines):
    """Le contre-test de la précédente : la corbeille doit se vider vers l'origine."""
    origine = os.path.join(deux_racines[0].path, "note.txt")
    operation = fichiers.remove("projets/note.txt", raison="obsolète")

    fichiers.undo(operation.id)

    assert os.path.exists(origine)


def test_la_quarantaine_reste_dans_la_racine(fichiers, deux_racines):
    """
    Elle garde l'opération sur le même volume — un déplacement y est atomique —
    et la corbeille ne traverse jamais une frontière de racine.
    """
    operation = fichiers.remove("projets/note.txt")

    assert operation.destination.startswith(deux_racines[0].path + os.sep)


def test_rien_n_est_ecrase(fichiers, deux_racines):
    """Écraser silencieusement serait une perte que le journal ne rattraperait pas."""
    (os.path.join(deux_racines[0].path, "occupe.txt"))
    open(os.path.join(deux_racines[0].path, "occupe.txt"), "w").write("déjà là")

    with pytest.raises(OperationRefused, match="existe déjà"):
        fichiers.move("projets/note.txt", "projets/occupe.txt")


def test_renommer_ne_deplace_pas(fichiers):
    """
    Confondre les deux ferait traverser un répertoire — ou une racine — par
    accident, sous couvert d'un simple changement de nom.
    """
    with pytest.raises(OperationRefused, match="séparateur"):
        fichiers.rename("projets/note.txt", "autre/note.txt")


def test_renommer_garde_le_fichier_dans_son_repertoire(fichiers, deux_racines):
    """Le contre-test : le cas légitime doit marcher."""
    operation = fichiers.rename("projets/note.txt", "note-2026.txt", raison="datation")

    assert os.path.dirname(operation.source) == os.path.dirname(operation.destination)
    assert os.path.exists(operation.destination)


def test_archiver_ne_supprime_pas_l_original(fichiers, deux_racines):
    """
    « Archiver » et « supprimer après avoir archivé » sont deux décisions. Les
    fondre ferait disparaître des données au premier échec de compression.
    """
    dossier = os.path.join(deux_racines[0].path, "campagne")
    os.makedirs(dossier)
    open(os.path.join(dossier, "a.txt"), "w").write("x")

    operation = fichiers.archive("projets/campagne", raison="fin de saison")

    assert os.path.exists(operation.destination)
    assert os.path.isdir(dossier)


def test_une_ecriture_hors_racine_inscriptible_est_refusee(fichiers):
    """La racine en lecture seule tient aussi pour les opérations réversibles."""
    with pytest.raises(RootRefused, match="lecture seule"):
        fichiers.move("projets/note.txt", "archives/note.txt")


# ----------------------------------------------------------------------
# Le journal
# ----------------------------------------------------------------------

def test_le_journal_precede_l_acte(tmp_path, deux_racines, monkeypatch):
    """
    L'ordre inverse laisserait une fenêtre où un fichier a bougé sans que rien
    ne sache le défaire — le raisonnement d'ADR-016 sur les octets et l'index.
    """
    journal = str(tmp_path / "journal.jsonl")
    fichiers = ReversibleFiles(deux_racines, journal=journal)

    import shutil as vrai_shutil

    def echouer(*args, **kwargs):
        raise OSError("disque plein")

    monkeypatch.setattr(vrai_shutil, "move", echouer)

    with pytest.raises(OSError):
        fichiers.move("projets/note.txt", "projets/ailleurs/note.txt", raison="tri")

    # Le déplacement a échoué, mais il est inscrit : on sait qu'il a été tenté.
    assert len(fichiers.history()) == 1


def test_l_historique_rend_la_derniere_version_d_une_operation(fichiers):
    """Le journal est ajouté en continu ; la dernière ligne d'un identifiant fait foi."""
    operation = fichiers.move("projets/note.txt", "projets/b/note.txt")
    fichiers.undo(operation.id)

    historique = fichiers.history()

    assert len(historique) == 1
    assert historique[0].undone is True


def test_une_ligne_illisible_est_signalee_et_ignoree(tmp_path, deux_racines, caplog):
    """
    Reconstruire une opération approximative ferait annuler autre chose que ce
    qui avait été fait.
    """
    journal = tmp_path / "journal.jsonl"
    journal.write_text('{"id": "op_1", "kind": "mo\n', encoding="utf-8")
    fichiers = ReversibleFiles(deux_racines, journal=str(journal))

    with caplog.at_level("ERROR"):
        historique = fichiers.history()

    assert historique == []
    assert "illisible" in caplog.text


def test_le_journal_conserve_la_raison(fichiers):
    """Un humain qui relit trois jours plus tard a besoin du pourquoi, pas du quoi."""
    fichiers.move("projets/note.txt", "projets/c/note.txt", raison="rangement trimestriel")

    with open(fichiers._journal, encoding="utf-8") as fichier:
        inscrit = json.loads(fichier.readline())

    assert inscrit["reason"] == "rangement trimestriel"


def test_annuler_ce_qui_a_bouge_depuis_est_refuse(fichiers, deux_racines):
    """
    Quelque chose a changé entre-temps : écraser à l'aveugle serait une seconde
    perte déguisée en réparation.
    """
    operation = fichiers.move("projets/note.txt", "projets/d/note.txt")
    os.remove(operation.destination)

    with pytest.raises(UndoRefused, match="introuvable"):
        fichiers.undo(operation.id)
