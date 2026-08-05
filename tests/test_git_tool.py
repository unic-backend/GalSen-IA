"""
Tests unitaires de l'outil Git.

Deux règles de `.claude/rules/git-workflow.md` sont appliquées dans le code et
non laissées à la discipline : interdiction de pousser sur une branche protégée
et interdiction du force push. Elles sont testées en premier, avec le verrou
d'écriture.

Les tests travaillent sur un dépôt Git créé dans un répertoire temporaire :
le dépôt du projet n'est jamais touché.
"""

import subprocess

import pytest

from src.tools.git.tool import GitNotAvailableError, GitTool


def _git(chemin, *arguments):
    """Lance une commande git dans le dépôt de test."""
    subprocess.run(["git", *arguments], cwd=str(chemin), check=True, capture_output=True)


@pytest.fixture
def depot(tmp_path):
    """Crée un dépôt Git minimal avec un commit et une branche de travail."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@galsen.sn")
    _git(tmp_path, "config", "user.name", "Test GalSen")
    (tmp_path / "README.md").write_text("# Dépôt de test\n", encoding="utf-8")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-q", "-m", "chore: initial commit")
    return tmp_path


@pytest.fixture
def lecture_seule(depot):
    """Outil sur le dépôt de test, écriture interdite (défaut)."""
    return GitTool({"repository_path": str(depot)})


@pytest.fixture
def ecriture(depot):
    """Outil sur le dépôt de test, écriture autorisée."""
    return GitTool({"repository_path": str(depot), "allow_write": True})


class TestReglesDuProjet:
    """Vérifie les règles de `git-workflow.md` appliquées dans le code."""

    def test_push_sur_branche_protegee_refuse(self, ecriture):
        """Pousser sur `main` doit être refusé, même écriture autorisée."""
        with pytest.raises(ValueError, match="branche protégée"):
            ecriture.execute("push", "origin", "main")

    def test_push_sur_master_refuse(self, ecriture):
        """`master` est protégée au même titre que `main`."""
        with pytest.raises(ValueError, match="branche protégée"):
            ecriture.execute("push", "origin", "master")

    def test_push_force_refuse(self, ecriture):
        """Le force push doit être refusé sur toute branche."""
        with pytest.raises(ValueError, match="force push"):
            ecriture.execute("push", "origin", "feature/test", force=True)

    def test_branches_protegees_configurables(self, depot):
        """La liste des branches protégées doit pouvoir être redéfinie."""
        outil = GitTool({
            "repository_path": str(depot),
            "allow_write": True,
            "protected_branches": ["production"],
        })
        with pytest.raises(ValueError, match="branche protégée"):
            outil.execute("push", "origin", "production")


class TestVerrouEcriture:
    """Vérifie que le dépôt n'est pas modifiable par défaut."""

    @pytest.mark.parametrize(
        "operation, arguments",
        [
            ("add", ("README.md",)),
            ("commit", ("feat: test",)),
            ("create_branch", ("feature/test",)),
            ("checkout", ("main",)),
            ("push", ()),
        ],
    )
    def test_operation_modifiante_refusee_par_defaut(self, lecture_seule, operation, arguments):
        """Toute opération modifiante doit être refusée sans allow_write."""
        with pytest.raises(ValueError, match="écriture est désactivée"):
            lecture_seule.execute(operation, *arguments)

    def test_lecture_reste_possible(self, lecture_seule):
        """Le verrou ne doit pas gêner les opérations de lecture."""
        assert lecture_seule.execute("current_branch") == "main"


class TestOperationsLecture:
    """Vérifie les opérations qui n'écrivent pas."""

    def test_is_repository(self, lecture_seule):
        """Un vrai dépôt doit être reconnu."""
        assert lecture_seule.execute("is_repository") is True

    def test_is_repository_hors_depot(self, tmp_path):
        """Un répertoire ordinaire ne doit pas être pris pour un dépôt."""
        ordinaire = tmp_path / "sans_git"
        ordinaire.mkdir()
        outil = GitTool({"repository_path": str(ordinaire)})
        assert outil.execute("is_repository") is False

    def test_current_branch(self, lecture_seule):
        """La branche courante doit être retournée sans décoration."""
        assert lecture_seule.execute("current_branch") == "main"

    def test_status_depot_propre(self, lecture_seule):
        """Un dépôt sans modification doit être signalé propre."""
        etat = lecture_seule.execute("status")
        assert etat["clean"] is True
        assert etat["branch"] == "main"

    def test_status_detecte_un_fichier_non_suivi(self, depot, lecture_seule):
        """Un nouveau fichier doit apparaître comme non suivi."""
        (depot / "note.txt").write_text("brouillon", encoding="utf-8")
        etat = lecture_seule.execute("status")
        assert etat["clean"] is False
        assert "note.txt" in etat["untracked"]

    def test_status_detecte_une_modification(self, depot, lecture_seule):
        """Un fichier suivi et modifié doit apparaître comme modifié."""
        (depot / "README.md").write_text("# Modifié\n", encoding="utf-8")
        assert "README.md" in lecture_seule.execute("status")["modified"]

    def test_branches(self, depot, lecture_seule):
        """Les branches locales doivent être listées."""
        _git(depot, "branch", "feature/essai")
        assert set(lecture_seule.execute("branches")) == {"main", "feature/essai"}

    def test_log_retourne_les_commits(self, lecture_seule):
        """log doit retourner les commits avec leurs métadonnées."""
        commits = lecture_seule.execute("log", limit=5)
        assert len(commits) == 1
        assert commits[0]["subject"] == "chore: initial commit"
        assert commits[0]["author"] == "Test GalSen"
        assert commits[0]["hash"]

    def test_log_respecte_la_limite(self, depot, lecture_seule):
        """La limite demandée doit être appliquée."""
        for index in range(3):
            (depot / f"f{index}.txt").write_text("x", encoding="utf-8")
            _git(depot, "add", f"f{index}.txt")
            _git(depot, "commit", "-q", "-m", f"feat: fichier {index}")
        assert len(lecture_seule.execute("log", limit=2)) == 2

    def test_diff_sans_changement(self, lecture_seule):
        """Sans modification, le diff doit être vide."""
        resultat = lecture_seule.execute("diff")
        assert resultat["has_changes"] is False

    def test_diff_avec_changement(self, depot, lecture_seule):
        """Une modification doit apparaître dans le diff."""
        (depot / "README.md").write_text("# Autre titre\n", encoding="utf-8")
        resultat = lecture_seule.execute("diff")
        assert resultat["has_changes"] is True
        assert "README.md" in resultat["diff"]

    def test_show(self, lecture_seule):
        """show doit décrire le commit demandé."""
        assert "initial commit" in lecture_seule.execute("show", "HEAD")

    def test_remotes_sans_distant(self, lecture_seule):
        """Un dépôt sans distant doit retourner un dictionnaire vide."""
        assert lecture_seule.execute("remotes") == {}

    def test_remotes_avec_distant(self, depot, lecture_seule):
        """Un distant configuré doit être retourné avec son URL."""
        _git(depot, "remote", "add", "origin", "https://exemple.sn/depot.git")
        assert lecture_seule.execute("remotes")["origin"] == "https://exemple.sn/depot.git"

    def test_summary(self, lecture_seule):
        """summary doit agréger l'état du dépôt."""
        resume = lecture_seule.execute("summary")
        assert resume["is_repository"] is True
        assert resume["branch"] == "main"
        assert resume["clean"] is True
        assert len(resume["recent_commits"]) == 1

    def test_summary_hors_depot_ne_leve_pas(self, tmp_path):
        """Hors dépôt, summary doit le signaler au lieu de lever."""
        ordinaire = tmp_path / "sans_git"
        ordinaire.mkdir()
        resume = GitTool({"repository_path": str(ordinaire)}).execute("summary")
        assert resume["is_repository"] is False
        assert "reason" in resume


class TestOperationsEcriture:
    """Vérifie les opérations modifiantes, écriture autorisée."""

    def test_add_puis_commit(self, depot, ecriture):
        """Un fichier ajouté puis commité doit apparaître dans l'historique."""
        (depot / "nouveau.txt").write_text("contenu", encoding="utf-8")
        ecriture.execute("add", "nouveau.txt")
        assert "nouveau.txt" in ecriture.execute("status")["staged"]

        ecriture.execute("commit", "feat: ajoute un fichier")
        assert ecriture.execute("log", limit=1)[0]["subject"] == "feat: ajoute un fichier"
        assert ecriture.execute("status")["clean"] is True

    def test_create_branch_puis_checkout(self, ecriture):
        """La création de branche doit basculer dessus, et le retour fonctionner."""
        ecriture.execute("create_branch", "feature/essai")
        assert ecriture.execute("current_branch") == "feature/essai"
        ecriture.execute("checkout", "main")
        assert ecriture.execute("current_branch") == "main"


class TestContratOutil:
    """Vérifie le contrat commun et la gestion des erreurs."""

    def test_operation_inconnue(self, lecture_seule):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            lecture_seule.execute("rebase_tout")

    def test_operation_manquante(self, lecture_seule):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            lecture_seule.execute()

    def test_available_operations(self, lecture_seule):
        """La liste annoncée doit couvrir lecture et écriture."""
        operations = lecture_seule.available_operations()
        assert {"status", "log", "diff", "commit", "push"} <= set(operations)

    def test_commande_git_en_echec_leve(self, lecture_seule):
        """Une révision inexistante doit lever une erreur explicite."""
        with pytest.raises(GitNotAvailableError):
            lecture_seule.execute("show", "revision-qui-nexiste-pas")
