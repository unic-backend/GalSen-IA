"""
Tests unitaires de l'outil système de fichiers.

Cet outil donne aux agents un accès en lecture et en écriture au disque : ses
garde-fous sont la partie la plus sensible du projet. Les tests couvrent en
priorité le confinement à la racine (`..`, chemin absolu, lien symbolique) et
le verrou d'écriture, puis les opérations elles-mêmes.

Chaque test travaille dans un répertoire temporaire : rien n'est écrit dans le
dépôt.
"""

import os

import pytest

from src.tools.filesystem.tool import FileSystemTool


@pytest.fixture
def racine(tmp_path):
    """Prépare une arborescence de travail isolée."""
    (tmp_path / "notes.txt").write_text("Dakar\nThiès\nSaint-Louis\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "agent.py").write_text("# agent GalSen\nvaleur = 42\n", encoding="utf-8")
    (tmp_path / "src" / "outil.py").write_text("# outil\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def lecture_seule(racine):
    """Outil confiné à la racine temporaire, écriture interdite (défaut)."""
    return FileSystemTool({"root": str(racine)})


@pytest.fixture
def ecriture(racine):
    """Outil confiné à la racine temporaire, écriture autorisée."""
    return FileSystemTool({"root": str(racine), "allow_write": True})


class TestConfinement:
    """Vérifie qu'un agent ne peut pas sortir du répertoire autorisé."""

    def test_remontee_par_double_point_refusee(self, lecture_seule):
        """Un chemin remontant au-dessus de la racine doit être refusé."""
        with pytest.raises(ValueError, match="hors du répertoire autorisé"):
            lecture_seule.execute("read", "../secret.txt")

    def test_chemin_absolu_exterieur_refuse(self, lecture_seule):
        """Un chemin absolu hors racine doit être refusé."""
        with pytest.raises(ValueError, match="hors du répertoire autorisé"):
            lecture_seule.execute("read", os.path.abspath(__file__))

    def test_lien_symbolique_vers_exterieur_refuse(self, racine, lecture_seule, tmp_path_factory):
        """Un lien symbolique pointant hors de la racine doit être refusé."""
        exterieur = tmp_path_factory.mktemp("dehors") / "cible.txt"
        exterieur.write_text("contenu externe", encoding="utf-8")
        lien = racine / "piege.txt"
        try:
            lien.symlink_to(exterieur)
        except (OSError, NotImplementedError):  # pragma: no cover - dépend du système
            pytest.skip("Les liens symboliques ne sont pas disponibles ici")
        with pytest.raises(ValueError, match="hors du répertoire autorisé"):
            lecture_seule.execute("read", "piege.txt")

    def test_chemin_vide_refuse(self, lecture_seule):
        """Un chemin vide doit être rejeté avant toute résolution."""
        with pytest.raises(ValueError, match="chaîne non vide"):
            lecture_seule.execute("read", "   ")

    def test_racine_inexistante_refusee(self, tmp_path):
        """Une racine inexistante doit empêcher la construction de l'outil."""
        with pytest.raises(ValueError, match="Racine du système de fichiers introuvable"):
            FileSystemTool({"root": str(tmp_path / "absente")})


class TestVerrouEcriture:
    """Vérifie que l'écriture reste interdite tant qu'elle n'est pas activée."""

    @pytest.mark.parametrize(
        "operation, arguments",
        [
            ("write", ("nouveau.txt", "contenu")),
            ("append", ("notes.txt", "ligne")),
            ("mkdir", ("dossier",)),
            ("delete", ("notes.txt",)),
            ("copy", ("notes.txt", "copie.txt")),
            ("move", ("notes.txt", "deplace.txt")),
        ],
    )
    def test_operation_ecriture_refusee_par_defaut(self, lecture_seule, operation, arguments):
        """Toute opération modifiante doit être refusée sans allow_write."""
        with pytest.raises(ValueError, match="écriture est désactivée"):
            lecture_seule.execute(operation, *arguments)

    def test_lecture_reste_possible_sans_ecriture(self, lecture_seule):
        """Le verrou d'écriture ne doit pas gêner la lecture."""
        assert lecture_seule.execute("exists", "notes.txt") is True

    def test_racine_non_supprimable(self, ecriture):
        """La racine elle-même ne doit jamais pouvoir être supprimée."""
        with pytest.raises(ValueError, match="racine .* ne peut pas être supprimée"):
            ecriture.execute("delete", ".")


class TestOperationsLecture:
    """Vérifie les opérations qui ne modifient rien."""

    def test_read_retourne_le_contenu(self, lecture_seule):
        """read doit retourner le contenu du fichier."""
        resultat = lecture_seule.execute("read", "notes.txt")
        assert "Dakar" in resultat["content"]

    def test_read_refuse_un_fichier_trop_gros(self, racine):
        """Un fichier dépassant la taille maximale ne doit pas être lu."""
        outil = FileSystemTool({"root": str(racine), "max_read_bytes": 5})
        with pytest.raises(ValueError):
            outil.execute("read", "notes.txt")

    def test_exists_sur_fichier_absent(self, lecture_seule):
        """exists doit retourner False sans lever."""
        assert lecture_seule.execute("exists", "absent.txt") is False

    def test_stat_decrit_le_fichier(self, lecture_seule):
        """stat doit retourner la taille et la nature de l'entrée."""
        infos = lecture_seule.execute("stat", "notes.txt")
        assert infos["size"] > 0
        assert infos["is_file"] is True

    def test_list_enumere_le_repertoire(self, lecture_seule):
        """list doit énumérer les entrées de la racine."""
        noms = {entree["name"] for entree in lecture_seule.execute("list", ".")}
        assert {"notes.txt", "src"} <= noms

    def test_search_filtre_par_motif(self, lecture_seule):
        """search doit retrouver les fichiers correspondant au motif."""
        resultats = lecture_seule.execute("search", "*.py")
        assert sorted(resultats) == ["src/agent.py", "src/outil.py"]

    def test_grep_retourne_les_lignes_correspondantes(self, lecture_seule):
        """grep doit retourner le fichier et le numéro de ligne."""
        resultats = lecture_seule.execute("grep", "Thiès")
        assert resultats
        assert resultats[0]["path"] == "notes.txt"
        assert resultats[0]["line"] == 2

    def test_tail_retourne_les_dernieres_lignes(self, lecture_seule):
        """tail doit retourner les dernières lignes seulement."""
        resultat = lecture_seule.execute("tail", "notes.txt", lines=1)
        assert resultat["lines"] == ["Saint-Louis"]
        assert resultat["line_count"] == 1

    def test_tail_refuse_un_nombre_de_lignes_invalide(self, lecture_seule):
        """Un nombre de lignes nul ou négatif doit être rejeté."""
        with pytest.raises(ValueError, match="au moins 1"):
            lecture_seule.execute("tail", "notes.txt", lines=0)

    def test_tree_liste_l_arborescence(self, lecture_seule):
        """tree doit inclure les fichiers des sous-répertoires."""
        arbre = lecture_seule.execute("tree", ".")
        assert any("agent.py" in entree for entree in arbre)


class TestOperationsEcriture:
    """Vérifie les opérations modifiantes, écriture autorisée."""

    def test_write_puis_read(self, ecriture):
        """Un fichier écrit doit être relisible à l'identique."""
        ecriture.execute("write", "rapport.txt", "première ligne")
        assert ecriture.execute("read", "rapport.txt")["content"] == "première ligne"

    def test_append_ajoute_a_la_suite(self, ecriture):
        """append ne doit pas écraser le contenu existant."""
        ecriture.execute("write", "journal.txt", "un")
        ecriture.execute("append", "journal.txt", "\ndeux")
        assert ecriture.execute("read", "journal.txt")["content"] == "un\ndeux"

    def test_mkdir_cree_le_repertoire(self, ecriture):
        """mkdir doit créer le répertoire demandé."""
        ecriture.execute("mkdir", "rapports/2026")
        assert ecriture.execute("stat", "rapports/2026")["is_directory"] is True

    def test_copy_conserve_l_original(self, ecriture):
        """copy doit laisser la source en place."""
        ecriture.execute("copy", "notes.txt", "notes-copie.txt")
        assert ecriture.execute("exists", "notes.txt") is True
        assert ecriture.execute("exists", "notes-copie.txt") is True

    def test_move_deplace_le_fichier(self, ecriture):
        """move doit faire disparaître la source."""
        ecriture.execute("move", "notes.txt", "archive.txt")
        assert ecriture.execute("exists", "notes.txt") is False
        assert ecriture.execute("exists", "archive.txt") is True

    def test_delete_supprime_le_fichier(self, ecriture):
        """delete doit retirer le fichier de la racine."""
        ecriture.execute("delete", "notes.txt")
        assert ecriture.execute("exists", "notes.txt") is False


class TestContratOutil:
    """Vérifie le contrat commun à tous les outils."""

    def test_operation_inconnue_refusee(self, lecture_seule):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            lecture_seule.execute("formater_le_disque", "notes.txt")

    def test_operation_manquante_refusee(self, lecture_seule):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            lecture_seule.execute()

    def test_available_operations_couvre_les_operations_reelles(self, lecture_seule):
        """La liste annoncée doit contenir les opérations effectivement servies."""
        operations = lecture_seule.available_operations()
        assert isinstance(operations, list)
        assert {"read", "write", "list", "grep", "delete"} <= set(operations)
