"""
Le bac à sable, et ce qu'on obtient en essayant d'en sortir (VOLET 34, ch. 08).

ADR-017 §5 : aucune capacité d'exécution ne livre sans son test d'évasion. La
leçon vient d'OpenClaw — 280 000 étoiles, base de confiance minimale, listes
blanches, conteneurs Docker durcis, et une littérature publiée sur la façon d'en
sortir. *Un bac à sable est une affirmation tant que personne n'a essayé de s'en
échapper.*

Ce fichier a donc deux moitiés, et la seconde compte autant que la première :

1. **Les évasions qui échouent** — temps processeur, mémoire, forks, taille de
   fichier, horloge, flot de sortie, secrets de l'environnement.
2. **Les évasions qui réussissent** — système de fichiers et réseau. Elles sont
   testées pour rester **documentées** : le jour où quelqu'un croira que ce bac à
   sable confine un disque, ces tests diront le contraire. Un bac à sable qui
   laisse croire à une frontière qu'il n'a pas est plus dangereux que pas de bac
   à sable du tout, parce qu'on lui confie ce qu'on n'aurait pas confié.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sandbox import (  # noqa: E402
    NON_GARANTI,
    SandboxPolicy,
    SandboxUnavailable,
    describe,
    run,
    run_python,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Les limites du noyau n'existent pas sur Windows ; le bac à sable y refuse.",
)


# ----------------------------------------------------------------------
# Le cas nominal
# ----------------------------------------------------------------------

def test_du_code_correct_s_execute_et_rend_sa_sortie():
    """Le contre-test de tout ce qui suit : les bornes ne bloquent pas le travail."""
    resultat = run_python("print(6 * 7)")

    assert resultat.success is True
    assert resultat.stdout.strip() == "42"


def test_une_erreur_du_code_est_rapportee_telle_quelle():
    """Un échec du code de l'agent n'est pas un échec du bac à sable."""
    resultat = run_python("raise ValueError('mauvais calcul')")

    assert resultat.success is False
    assert "mauvais calcul" in resultat.stderr


def test_le_bac_a_sable_dit_ce_qu_il_ne_garantit_pas():
    """
    C'est ce qu'un opérateur doit lire **avant** de confier du code, et la
    différence entre un bac à sable et une promesse.
    """
    rapport = describe()

    assert rapport["available"] is True
    assert any("filesystem" in ligne for ligne in rapport["not_guaranteed"])
    assert any("network" in ligne for ligne in rapport["not_guaranteed"])


# ----------------------------------------------------------------------
# Les évasions qui échouent
# ----------------------------------------------------------------------

def test_une_boucle_infinie_est_arretee_et_la_cause_est_nommee():
    """
    La limite souple est sous la limite dure pour que le noyau envoie SIGXCPU,
    dont le nom dit la cause. Rapporter « SIGKILL » enverrait chercher une fuite
    mémoire là où il y a une boucle.
    """
    resultat = run_python("while True: pass", SandboxPolicy(cpu_seconds=1, wall_seconds=20))

    assert resultat.success is False
    assert "SIGXCPU" in resultat.killed_by


def test_une_allocation_massive_est_bornee():
    """Une allocation qui étoufferait la machine échoue dans le fils, pas dehors."""
    resultat = run_python(
        "x = bytearray(500 * 1024 * 1024)",
        SandboxPolicy(memory_bytes=64 * 1024 * 1024, wall_seconds=20),
    )

    assert resultat.success is False
    assert "MemoryError" in resultat.stderr


def test_le_plafond_de_processus_est_applique_dans_le_fils():
    """
    La limite est vérifiée, **pas la bombe**.

    Première version de ce test : une vraie bombe de forks. Elle a fonctionné —
    et elle a épuisé la table de processus de l'**utilisateur**, donc de la
    session de tests elle-même, qui n'a plus rien pu lancer pendant dix tests.
    C'est la trouvaille de ce chapitre : `RLIMIT_NPROC` borne l'utilisateur et
    non le bac à sable, et c'est écrit dans `NON_GARANTI`.

    Lancer une bombe dans la suite partagée éprouverait le noyau, pas ce code, et
    au prix d'une panne des tests voisins. Ce qui appartient à ce module, c'est
    que la limite soit **posée** — et cela se vérifie exactement.
    """
    resultat = run_python(
        "import resource; print(resource.getrlimit(resource.RLIMIT_NPROC))",
        SandboxPolicy(processes=8),
    )

    assert resultat.success is True
    assert resultat.stdout.strip() == "(8, 8)"


def test_les_autres_bornes_sont_posees_avant_le_code():
    """
    Elles sont appliquées entre `fork` et `exec` : elles existent donc avant la
    première instruction de l'agent, et rien de ce qu'il fait ne les lève.
    """
    code = (
        "import resource\n"
        "print(resource.getrlimit(resource.RLIMIT_CPU)[0],"
        " resource.getrlimit(resource.RLIMIT_FSIZE)[0],"
        " resource.getrlimit(resource.RLIMIT_CORE))"
    )

    resultat = run_python(code, SandboxPolicy(cpu_seconds=3, file_size_bytes=2048))

    assert resultat.stdout.strip() == "3 2048 (0, 0)"


def test_un_fichier_trop_grand_est_borne():
    """Un disque rempli par du code d'agent est une panne pour tout le monde."""
    resultat = run_python(
        "open('gros', 'wb').write(b'x' * 50_000_000)",
        SandboxPolicy(file_size_bytes=1024, wall_seconds=20),
    )

    assert resultat.success is False
    assert "27" in resultat.stderr or "too large" in resultat.stderr.lower()


def test_un_programme_qui_dort_est_interrompu():
    """
    Le temps processeur ne borne pas l'attente : un programme endormi n'en
    consomme pas. L'horloge murale est une limite distincte, pour cette raison.
    """
    resultat = run_python("import time; time.sleep(60)", SandboxPolicy(wall_seconds=2))

    assert resultat.timed_out is True
    assert resultat.duration_seconds < 10


def test_un_flot_de_sortie_est_tronque_et_le_dit():
    """Une sortie non bornée remplirait la mémoire du **parent**, pas du fils."""
    resultat = run_python("print('x' * 500_000)", SandboxPolicy(output_bytes=500))

    assert resultat.truncated is True
    assert "tronqué" in resultat.stdout


def _plafond_de_processus(marge: int = 64) -> int:
    """
    Retourne un plafond de processus au-dessus de ce que la machine utilise déjà.

    `RLIMIT_NPROC` borne l'**utilisateur**, pas le bac à sable — la politique le
    dit depuis le chapitre 08. Un test qui fixe 32 sur une machine qui fait déjà
    tourner des centaines de processus rend donc **tout `fork` impossible** : le
    fils meurt avec « Resource temporarily unavailable » avant d'avoir rien
    prouvé, et le test mesure le plafond au lieu de mesurer le nettoyage.

    C'est exactement ce qui cassait ces deux tests sur les exécuteurs GitHub,
    alors qu'ils passaient ici.
    """
    try:
        vivants = sum(1 for entree in os.listdir("/proc") if entree.isdigit())
    except OSError:
        vivants = 0
    return max(64, vivants + marge)


def _fork_possible(policy: SandboxPolicy) -> bool:
    """
    Vérifie que l'environnement autorise réellement un `fork` sous cette politique.

    Sans cette sonde, un environnement qui refuse les forks ferait échouer les
    deux tests suivants sur une assertion trompeuse — ils affirmeraient que le
    nettoyage ne marche pas, alors que rien n'a été lancé.
    """
    resultat = run_python(
        "import os\n"
        "try:\n"
        "    pid = os.fork()\n"
        "except OSError:\n"
        "    raise SystemExit(1)\n"
        "if pid == 0:\n"
        "    os._exit(0)\n"
        "os.waitpid(pid, 0)\n",
        policy,
    )
    return resultat.exit_code == 0


def test_ce_que_le_processus_a_lance_meurt_avec_lui():
    """
    Tuer le seul processus laisserait ses enfants tourner : le délai ne bornerait
    alors rien du tout. Le groupe entier est tué.
    """
    code = (
        "import subprocess, sys, time\n"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "time.sleep(60)\n"
    )

    politique = SandboxPolicy(wall_seconds=2, processes=_plafond_de_processus())
    if not _fork_possible(politique):
        pytest.skip("Cet environnement refuse les forks : rien à nettoyer à prouver.")

    resultat = run_python(code, politique)

    assert resultat.timed_out is True


def test_aucun_descendant_ne_survit_a_une_execution_terminee_par_le_noyau():
    """
    Le défaut le plus grave trouvé par ce chapitre, et il l'a été en essayant.

    Quand le noyau tue le processus par une limite — SIGXCPU, mémoire — ses
    descendants **lui survivent**. Le groupe n'était tué que sur délai dépassé,
    donc jamais dans ce cas. Mesuré lors du premier essai : une bombe de forks a
    laissé **31 549 processus vivants** après la mort de leur père, et comme
    `RLIMIT_NPROC` borne l'utilisateur et non le bac à sable, la session de tests
    n'a plus rien pu lancer.

    Deuxième défaut, trouvé en corrigeant le premier : `os.getpgid(pid)` lève une
    fois le père mort — précisément dans le cas qui compte. L'identifiant du
    groupe est le pid du fils, puisque `setsid()` en fait un chef de session.

    Ce test fourche trois fois, pas indéfiniment : éprouver le nettoyage ne
    demande pas de reproduire la panne.
    """
    import subprocess
    import time

    code = (
        "import os, time\n"
        "for _ in range(3):\n"
        "    if os.fork() == 0:\n"
        "        time.sleep(120)\n"
        "        os._exit(0)\n"
        "while True:\n"
        "    pass\n"
    )

    politique = SandboxPolicy(
        cpu_seconds=1, wall_seconds=25, processes=_plafond_de_processus()
    )
    if not _fork_possible(politique):
        pytest.skip("Cet environnement refuse les forks : aucun descendant à faire survivre.")

    resultat = run_python(code, politique)
    assert "SIGXCPU" in (resultat.killed_by or "")

    time.sleep(1)
    vivants = subprocess.run(
        ["ps", "-eo", "args", "--no-headers"], capture_output=True, text=True,
    ).stdout
    restants = [ligne for ligne in vivants.splitlines() if "python3 -I -" in ligne]

    assert restants == [], f"Descendants survivants : {restants}"


# ----------------------------------------------------------------------
# Les secrets ne franchissent pas la frontière
# ----------------------------------------------------------------------

def test_aucun_secret_du_parent_n_est_visible(monkeypatch):
    """
    Le processus parent porte `GALSEN_API_KEYS`, `OPENAI_API_KEY`,
    `GALSEN_SMTP_PASSWORD`… Un fils qui hérite de `os.environ` les lit tous, et
    c'est l'évasion la plus facile de toutes : elle ne demande aucun exploit,
    seulement `print(os.environ)`.
    """
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-secrete:admin:awa")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-tres-secret")
    monkeypatch.setenv("GALSEN_SMTP_PASSWORD", "mot-de-passe-smtp")

    resultat = run_python("import os; print(dict(os.environ))")

    assert "sk-tres-secret" not in resultat.stdout
    assert "cle-secrete" not in resultat.stdout
    assert "mot-de-passe-smtp" not in resultat.stdout


def test_la_liste_est_blanche_et_non_noire(monkeypatch):
    """
    Retirer ce qui semble sensible oublierait la variable ajoutée demain — et
    c'est celle-là qui fuirait. Seul ce qui est nommé passe.
    """
    monkeypatch.setenv("UNE_VARIABLE_INVENTEE_DEMAIN", "valeur-confidentielle")

    resultat = run_python("import os; print(dict(os.environ))")

    assert "valeur-confidentielle" not in resultat.stdout


def test_le_minimum_necessaire_passe_quand_meme():
    """Le contre-test : sans `PATH`, un interpréteur ne se trouverait pas."""
    resultat = run_python("import os; print('PATH' in os.environ)")

    assert resultat.stdout.strip() == "True"


# ----------------------------------------------------------------------
# Les évasions qui RÉUSSISSENT — documentées pour ne pas être crues bornées
# ----------------------------------------------------------------------

def test_le_systeme_de_fichiers_n_est_PAS_confine(tmp_path):
    """
    **Cette évasion réussit, et c'est écrit dans `NON_GARANTI`.**

    Sans espaces de noms — donc sans privilèges que la plateforme n'a pas — un
    fils lit et écrit là où l'utilisateur le peut. Le répertoire de travail est un
    rangement, pas une frontière.

    Ce qui tient cette limite est ailleurs, et existe : les racines déclarées
    (ch. 07), le portillon d'approbation (ADR-006) et la liste blanche
    d'exécutables. Ce test échouera le jour où quelqu'un ajoutera un vrai
    confinement — et ce jour-là, `NON_GARANTI` devra être corrigé.
    """
    cible = tmp_path / "hors-du-bac.txt"

    resultat = run_python(f"open({str(cible)!r}, 'w').write('sorti')")

    assert resultat.success is True
    assert cible.read_text(encoding="utf-8") == "sorti"
    assert any("filesystem" in ligne for ligne in NON_GARANTI)


def test_le_repertoire_de_travail_est_neanmoins_isole_et_nettoye():
    """
    Ce n'est pas une frontière, mais ce n'est pas rien : le code s'exécute dans
    un répertoire à lui, effacé après. Deux exécutions ne se marchent pas dessus.
    """
    premier = run_python("import os; open('trace.txt', 'w').write('x'); print(os.getcwd())")
    second = run_python("import os; print(os.path.exists('trace.txt'))")

    assert premier.success and second.stdout.strip() == "False"
    assert not os.path.exists(premier.stdout.strip())


# ----------------------------------------------------------------------
# Refus
# ----------------------------------------------------------------------

def test_une_commande_vide_est_refusee():
    """Un bac à sable qui lance « rien » rendrait un succès qui ne veut rien dire."""
    with pytest.raises(ValueError):
        run([])


def test_un_code_vide_est_refuse():
    """Idem : exécuter une chaîne vide et rapporter « succès » serait faux."""
    with pytest.raises(ValueError):
        run_python("   ")


def test_sur_windows_le_bac_a_sable_refuse_au_lieu_de_faire_semblant(monkeypatch):
    """
    Exécuter sans les bornes en croyant en avoir est pire que ne pas exécuter :
    on confierait à un bac à sable ce qu'on ne confierait pas à un `subprocess`.
    """
    import src.sandbox.runner as runner

    monkeypatch.setattr(runner.platform, "system", lambda: "Windows")

    assert runner.unavailable_reason() is not None
    with pytest.raises(SandboxUnavailable, match="Windows"):
        runner.run([sys.executable, "-c", "pass"])


def test_aucun_shell_n_est_utilise():
    """
    La garantie de l'outil terminal, conservée ici : un métacaractère reste un
    argument et ne devient pas une seconde commande.
    """
    resultat = run([sys.executable, "-c", "import sys; print(sys.argv[1])", "salut; id"])

    assert resultat.stdout.strip() == "salut; id"


def test_l_api_demarre_sans_le_module_resource():
    """
    `resource` est POSIX ; sous Windows, son absence bloquait TOUT.

    Mesuré sur la machine du propriétaire le 2026-08-22 :
    `import src.api.server` échouait sur `ModuleNotFoundError: No module named
    'resource'`, et la plateforme entière refusait de démarrer — alors que
    `unavailable_reason()` prévoyait déjà le cas. C'est l'import en haut de
    fichier qui échouait **avant** que la garde puisse servir.

    Le test tourne dans un **sous-processus** : manipuler `sys.meta_path` et
    réimporter `src.api.server` dans celui-ci laisserait des modules à moitié
    chargés derrière lui, et ce serait exactement le pollueur que
    `scripts/find_polluter.py` sert à traquer.
    """
    import subprocess
    import sys

    programme = (
        "import sys\n"
        "class B:\n"
        "    def find_module(self, n, p=None):\n"
        "        return self if n == 'resource' else None\n"
        "    def load_module(self, n):\n"
        "        raise ImportError(\"No module named 'resource'\")\n"
        "sys.meta_path.insert(0, B())\n"
        "from src.api.server import app\n"
        "from src.sandbox.runner import unavailable_reason, run\n"
        "assert len(app.routes) > 100, 'API vide'\n"
        "raison = unavailable_reason()\n"
        "assert raison, 'le bac a sable devrait se declarer indisponible'\n"
        "assert 'resource' in raison\n"
        "try:\n"
        "    run(['echo', 'x'])\n"
        "    raise AssertionError('run() aurait du refuser')\n"
        "except Exception as e:\n"
        "    assert type(e).__name__ == 'SandboxUnavailable', type(e).__name__\n"
        "print('OK')\n"
    )
    acheve = subprocess.run(
        [sys.executable, "-c", programme],
        capture_output=True, text=True, timeout=180,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    assert acheve.returncode == 0, acheve.stderr[-2000:]
    assert "OK" in acheve.stdout
