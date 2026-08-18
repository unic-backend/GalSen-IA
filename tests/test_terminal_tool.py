"""
Tests unitaires de l'outil terminal.

Cet outil exécute des commandes externes pour le compte des agents. Ses trois
garde-fous sont testés en premier, car ce sont eux qui rendent l'outil sûr :
absence de shell, liste blanche d'exécutables, délai maximum. Viennent ensuite
le confinement du répertoire de travail et la forme du résultat.

Les commandes réellement lancées se limitent à `python -c` et `echo` : rien
n'est installé, rien n'est supprimé.
"""

import sys

import pytest

from src.tools.terminal.tool import TerminalTool


@pytest.fixture
def racine(tmp_path):
    """Prépare un répertoire de travail isolé avec un sous-répertoire."""
    (tmp_path / "sous_dossier").mkdir()
    return tmp_path


@pytest.fixture
def terminal(racine):
    """Outil confiné au répertoire temporaire, python autorisé."""
    return TerminalTool({"working_directory": str(racine)})


class TestListeBlanche:
    """Vérifie qu'un agent ne peut lancer que les exécutables déclarés."""

    def test_commande_hors_liste_refusee(self, terminal):
        """Un exécutable absent de la liste blanche doit être refusé."""
        with pytest.raises(ValueError, match="non autorisée"):
            terminal.execute(["rm", "-rf", "/"])

    def test_message_d_erreur_liste_les_commandes_autorisees(self, terminal):
        """Le refus doit indiquer ce qui est permis."""
        with pytest.raises(ValueError, match="Commandes autorisées"):
            terminal.execute(["curl", "https://exemple.sn"])

    def test_liste_blanche_configurable(self, racine):
        """La configuration doit pouvoir restreindre la liste par défaut."""
        outil = TerminalTool({"working_directory": str(racine), "allowed_commands": ["echo"]})
        assert outil.is_command_allowed("echo") is True
        assert outil.is_command_allowed("python") is False

    def test_chemin_complet_ramene_au_nom_de_l_executable(self, terminal):
        """Un chemin absolu ne doit pas contourner la liste blanche."""
        assert terminal.is_command_allowed("/usr/bin/python") is True
        assert terminal.is_command_allowed("/usr/bin/curl") is False

    def test_extension_windows_ignoree(self, terminal):
        """`python.exe` doit être reconnu comme `python`."""
        assert terminal.is_command_allowed("python.exe") is True

    def test_allowed_command_list_est_triee(self, terminal):
        """La liste annoncée doit être triée et non vide."""
        commandes = terminal.allowed_command_list()
        assert commandes == sorted(commandes)
        assert "python" in commandes


class TestAbsenceDeShell:
    """Vérifie que les métacaractères ne peuvent pas devenir une seconde commande."""

    def test_metacaracteres_ne_lancent_pas_de_seconde_commande(self, terminal):
        """`;` dans un argument doit rester un argument, pas un séparateur."""
        resultat = terminal.execute([sys.executable, "-c", "print('ok'); import sys"])
        assert resultat["success"] is True
        assert "ok" in resultat["stdout"]

    def test_argument_contenant_un_pipe_reste_un_argument(self, terminal):
        """Un `|` transmis en argument doit être imprimé, pas interprété."""
        resultat = terminal.execute([sys.executable, "-c", "print('a | b')"])
        assert "a | b" in resultat["stdout"]

    def test_chaine_decoupee_en_respectant_les_guillemets(self, terminal):
        """Une commande fournie en chaîne doit être découpée par shlex."""
        resultat = terminal.execute(f'{sys.executable} -c "print(1 + 1)"')
        assert resultat["stdout"].strip() == "2"


class TestDelaiMaximum:
    """Vérifie qu'une commande bloquée ne peut pas figer la plateforme."""

    def test_commande_trop_longue_est_interrompue(self, terminal):
        """Au-delà du délai, la commande doit être signalée comme interrompue."""
        resultat = terminal.execute(
            [sys.executable, "-c", "import time; time.sleep(5)"], timeout=1
        )
        assert resultat["timed_out"] is True
        assert resultat["success"] is False
        assert resultat["returncode"] is None


class TestRepertoireDeTravail:
    """Vérifie le confinement du répertoire d'exécution."""

    def test_sous_repertoire_autorise(self, terminal):
        """Un sous-répertoire de la racine doit être accepté."""
        resultat = terminal.execute(
            [sys.executable, "-c", "import os; print(os.getcwd())"],
            working_directory="sous_dossier",
        )
        assert resultat["stdout"].strip().endswith("sous_dossier")

    def test_repertoire_exterieur_refuse(self, terminal):
        """Un répertoire hors racine doit être refusé."""
        with pytest.raises(ValueError, match="hors de"):
            terminal.execute([sys.executable, "-c", "print(1)"], working_directory="..")

    def test_repertoire_inexistant_refuse(self, terminal):
        """Un sous-répertoire absent doit être refusé."""
        with pytest.raises(ValueError, match="introuvable"):
            terminal.execute([sys.executable, "-c", "print(1)"], working_directory="absent")

    def test_racine_inexistante_refusee(self, tmp_path):
        """Une racine inexistante doit empêcher la construction de l'outil."""
        with pytest.raises(ValueError, match="Répertoire de travail introuvable"):
            TerminalTool({"working_directory": str(tmp_path / "absente")})


class TestResultat:
    """Vérifie la forme et le contenu du résultat retourné."""

    def test_commande_reussie(self, terminal):
        """Une commande réussie doit être signalée comme telle."""
        resultat = terminal.execute([sys.executable, "-c", "print('bonjour')"])
        assert resultat["success"] is True
        assert resultat["returncode"] == 0
        assert resultat["timed_out"] is False
        assert "bonjour" in resultat["stdout"]

    def test_commande_en_echec(self, terminal):
        """Un code de retour non nul doit être rapporté, sans exception."""
        resultat = terminal.execute([sys.executable, "-c", "import sys; sys.exit(3)"])
        assert resultat["success"] is False
        assert resultat["returncode"] == 3

    def test_sortie_erreur_capturee(self, terminal):
        """La sortie d'erreur doit être capturée séparément."""
        resultat = terminal.execute(
            [sys.executable, "-c", "import sys; print('souci', file=sys.stderr)"]
        )
        assert "souci" in resultat["stderr"]

    def test_entree_standard_transmise(self, terminal):
        """Le texte fourni doit arriver sur l'entrée standard."""
        resultat = terminal.execute(
            [sys.executable, "-c", "import sys; print(sys.stdin.read().strip().upper())"],
            input_text="dakar",
        )
        assert "DAKAR" in resultat["stdout"]

    def test_sortie_trop_longue_tronquee(self, racine):
        """Une sortie volumineuse doit être tronquée et signalée."""
        outil = TerminalTool({"working_directory": str(racine), "max_output_chars": 50})
        resultat = outil.execute([sys.executable, "-c", "print('x' * 500)"])
        assert "[sortie tronquée]" in resultat["stdout"]

    def test_variables_d_environnement_supplementaires(self, racine):
        """Les variables déclarées doivent atteindre le processus fils."""
        outil = TerminalTool({
            "working_directory": str(racine),
            "environment": {"GALSEN_TEST": "senegal"},
        })
        resultat = outil.execute(
            [sys.executable, "-c", "import os; print(os.environ.get('GALSEN_TEST'))"]
        )
        assert resultat["stdout"].strip() == "senegal"


class TestArgumentsInvalides:
    """Vérifie le rejet des appels mal formés."""

    def test_commande_absente(self, terminal):
        """Appeler l'outil sans commande doit être refusé."""
        with pytest.raises(ValueError, match="Une commande est requise"):
            terminal.execute()

    def test_commande_vide(self, terminal):
        """Une commande vide doit être refusée."""
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            terminal.execute([])

    def test_type_de_commande_invalide(self, terminal):
        """Un type non pris en charge doit être refusé explicitement."""
        with pytest.raises(ValueError, match="chaîne ou une liste"):
            terminal.execute(42)

    def test_executable_introuvable(self, racine):
        """Un exécutable autorisé mais absent du système doit lever une ValueError."""
        outil = TerminalTool({
            "working_directory": str(racine),
            "allowed_commands": ["executable-qui-nexiste-pas"],
        })
        with pytest.raises(ValueError, match="Exécutable introuvable"):
            outil.execute(["executable-qui-nexiste-pas"])
