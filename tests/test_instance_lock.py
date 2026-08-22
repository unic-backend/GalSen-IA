"""
Une seule instance faisant autorité (chantier 3 — ADR-013).

Trois faits sont vérifiés ici, et ce sont les TESTs 3, 4 et 5 du plan de mise en
ligne :

- **TEST 5** — une deuxième instance sur le même répertoire de données refuse de
  démarrer. C'est la garantie centrale : les révocations de clés et les compteurs
  de quota vivent dans la mémoire du processus, donc *deux* processus, c'est deux
  vérités, et la plus permissive gagne.
- **TEST 4** — une clé révoquée est rejetée à la requête suivante.
- **TEST 3** — les incréments de quota restent cohérents sous concurrence.
"""

import os
import subprocess
import sys
import threading
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api import instance_lock  # noqa: E402
from src.api.rate_limiter import InMemoryRateLimiter, RateLimitConfig  # noqa: E402
from src.api.rbac import RBACManager, hash_api_key  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def repertoire(tmp_path, monkeypatch):
    """Répertoire de données isolé, verrou relâché à la sortie."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv(instance_lock.ALLOW_MULTI_INSTANCE_VARIABLE, raising=False)
    # Le verrou est un état de module : deux tests ne doivent pas se le passer.
    instance_lock.release()
    yield tmp_path
    instance_lock.release()


# ----------------------------------------------------------------------
# TEST 5 — la deuxième instance
# ----------------------------------------------------------------------

class TestVerrouDInstance:
    """Le verrou est la seule protection qui ne dépend pas de la vigilance."""

    def test_le_verrou_est_pris_et_nomme_son_detenteur(self, repertoire):
        """Prendre le verrou doit laisser une trace lisible par un humain."""
        etat = instance_lock.acquire()

        assert etat["held"] is True
        detenteur = instance_lock.read_holder()
        assert detenteur["pid"] == os.getpid()
        assert detenteur["instance"]

    def test_une_seconde_instance_refuse_de_demarrer(self, repertoire):
        """
        TEST 5 — le fait qui justifie tout le chantier.

        Le verrou est vérifié depuis un **autre processus** : `flock` est attaché
        à la description de fichier, donc un second appel dans le même processus
        ne prouverait rien.
        """
        instance_lock.acquire()

        programme = (
            "import sys; sys.path.insert(0, %r);"
            "from src.api import instance_lock;"
            "instance_lock.acquire()" % RACINE
        )
        resultat = subprocess.run(
            [sys.executable, "-c", programme],
            capture_output=True, text=True, timeout=60,
            env={**os.environ, "GALSEN_DATA_DIR": str(repertoire)},
        )

        assert resultat.returncode != 0, "la deuxième instance a démarré"
        assert "InstanceAlreadyRunning" in resultat.stderr
        # Le refus doit nommer l'occupant : « impossible de démarrer » sans dire
        # qui tient la place n'est pas actionnable.
        assert instance_lock.instance_id() in resultat.stderr

    def test_l_application_elle_meme_refuse_de_demarrer(self, repertoire):
        """
        TEST 5, bout en bout : ce n'est pas le module qui doit refuser, c'est
        l'application.

        Le verrou est pris ici, puis un processus fils démarre le cycle de vie
        complet de l'API sur le même répertoire de données. Il doit échouer.
        """
        instance_lock.acquire()

        programme = (
            "import sys; sys.path.insert(0, %r);"
            "from fastapi.testclient import TestClient;"
            "from src.api.server import app;"
            "TestClient(app).__enter__()" % RACINE
        )
        resultat = subprocess.run(
            [sys.executable, "-c", programme],
            capture_output=True, text=True, timeout=180,
            env={**os.environ, "GALSEN_DATA_DIR": str(repertoire)},
        )

        assert resultat.returncode != 0, "l'API a démarré à côté d'une instance vivante"
        assert "InstanceAlreadyRunning" in resultat.stderr

    def test_le_verrou_est_repris_apres_un_arret_brutal(self, repertoire):
        """
        Un fichier laissé par un processus mort ne doit pas bloquer le démarrage.

        C'est la raison du choix de `flock` : le noyau le relâche à la mort du
        processus, quelle qu'en soit la manière, donc il n'y a pas de verrou
        périmé à deviner.
        """
        programme = (
            "import sys, os; sys.path.insert(0, %r);"
            "from src.api import instance_lock;"
            "instance_lock.acquire();"
            "os._exit(0)" % RACINE
        )
        subprocess.run(
            [sys.executable, "-c", programme], check=True, timeout=60,
            env={**os.environ, "GALSEN_DATA_DIR": str(repertoire)},
        )
        # Le fichier est bien resté : l'arrêt était brutal.
        assert (repertoire / instance_lock.LOCK_FILENAME).exists()

        assert instance_lock.acquire()["held"] is True

    def test_le_mode_multi_instance_leve_le_verrou(self, repertoire, monkeypatch):
        """Le retour arrière doit exister, et être explicite."""
        monkeypatch.setenv(instance_lock.ALLOW_MULTI_INSTANCE_VARIABLE, "true")

        etat = instance_lock.acquire()

        assert etat["held"] is False
        assert etat["multi_instance_allowed"] is True
        assert not (repertoire / instance_lock.LOCK_FILENAME).exists()

    def test_reprendre_le_verrou_dans_le_meme_processus_est_sans_effet(self, repertoire):
        """
        Une instance ne peut pas être deux.

        Sans cette idempotence, un second `flock` depuis le même processus
        échouerait — `flock` traite deux descripteurs du même fichier comme deux
        prétendants, même dans un seul processus.
        """
        premier = instance_lock.acquire()

        assert instance_lock.acquire() == premier

    def test_relacher_retire_le_fichier(self, repertoire):
        """
        Un fichier laissé derrière ferait croire à `scripts/backup.py` qu'une
        instance tourne, et bloquerait la restauration.
        """
        instance_lock.acquire()
        instance_lock.release()

        assert not (repertoire / instance_lock.LOCK_FILENAME).exists()
        assert instance_lock.is_running() is False

    def test_un_fichier_orphelin_ne_bloque_pas_la_restauration(self, repertoire):
        """
        `is_running()` interroge le verrou, pas la présence du fichier : sinon un
        arrêt brutal interdirait pour toujours la manœuvre qui répare l'incident.
        """
        (repertoire / instance_lock.LOCK_FILENAME).write_text('{"instance": "morte"}')

        assert instance_lock.is_running() is False

    def test_l_etat_ne_divulgue_pas_le_verrou_dans_la_sante(self, repertoire):
        """
        `/health` n'est pas authentifiée : le chemin du verrou et le PID de
        l'occupant n'y ont pas leur place.
        """
        from src.api.scaling import scaling_report

        instance_lock.acquire()
        expose = scaling_report()["instance_lock"]

        assert set(expose) == {"held", "multi_instance_allowed", "enforced"}
        assert expose["held"] is True


# ----------------------------------------------------------------------
# TEST 4 — la clé révoquée
# ----------------------------------------------------------------------

class TestRevocation:
    """Une clé révoquée doit être rejetée, et le rester."""

    def test_une_cle_revoquee_est_refusee(self, monkeypatch):
        """TEST 4 — l'effet est immédiat, sans redémarrage."""
        monkeypatch.setenv("GALSEN_API_KEYS", "cle-compromise:admin")
        gestionnaire = RBACManager()
        empreinte = hash_api_key("cle-compromise")[:12]

        assert gestionnaire.authenticate("cle-compromise") is not None
        assert gestionnaire.revoke(empreinte) is True

        with pytest.raises(PermissionError):
            gestionnaire.authenticate("cle-compromise")

    def test_la_revocation_ne_survit_pas_au_redemarrage(self, monkeypatch):
        """
        Le trou qui reste, mesuré plutôt qu'affirmé.

        La liste de révocation vit dans la mémoire du processus : un
        redémarrage rend la clé compromise valide à nouveau. C'est pourquoi
        `/auth/keys/{empreinte}/revoke` répond `persistent: false` et renvoie
        l'opérateur à `GALSEN_API_KEYS`. Ce test échouera le jour où les
        révocations seront persistées — et ce sera le signal d'aller corriger
        cette réponse, `scaling.py` et ADR-013 ensemble.
        """
        monkeypatch.setenv("GALSEN_API_KEYS", "cle-compromise:admin")
        gestionnaire = RBACManager()
        gestionnaire.revoke(hash_api_key("cle-compromise")[:12])

        # Un redémarrage, c'est un gestionnaire neuf sur le même environnement.
        apres_redemarrage = RBACManager()

        assert apres_redemarrage.authenticate("cle-compromise") is not None


# ----------------------------------------------------------------------
# TEST 3 — les compteurs de quota
# ----------------------------------------------------------------------

class TestQuotasSousConcurrence:
    """Les incréments doivent être cohérents, y compris sous charge parallèle."""

    def test_aucun_jeton_n_est_perdu_ni_invente(self):
        """
        TEST 3 — cent requêtes concurrentes sur un seau de quarante jetons.

        Le compteur est protégé par un verrou dans le processus. S'il ne l'était
        pas, deux fils pourraient lire le même solde et le décrémenter chacun :
        le total accordé dépasserait le budget, silencieusement.
        """
        limiteur = InMemoryRateLimiter(
            RateLimitConfig(authenticated_rpm=40, unauthenticated_rpm=40, burst_multiplier=1.0)
        )
        acceptees = []
        barriere = threading.Barrier(20)

        def appeler():
            # Toutes les tâches partent au même instant : sans cela, elles
            # s'exécuteraient l'une après l'autre et ne prouveraient rien.
            barriere.wait()
            for _ in range(5):
                autorise, _info = limiteur.is_allowed("client-unique", True)
                if autorise:
                    acceptees.append(1)

        fils = [threading.Thread(target=appeler) for _ in range(20)]
        for f in fils:
            f.start()
        for f in fils:
            f.join()

        # Le seau contient exactement 40 jetons et ne se remplit pas de façon
        # mesurable en quelques millisecondes : ni plus, ni beaucoup moins.
        assert 40 <= sum(acceptees) <= 41, f"jetons accordés : {sum(acceptees)}"

    def test_deux_clients_ne_partagent_pas_leur_budget(self):
        """Un client bruyant ne doit pas consommer le quota d'un autre."""
        limiteur = InMemoryRateLimiter(
            RateLimitConfig(authenticated_rpm=5, unauthenticated_rpm=5, burst_multiplier=1.0)
        )

        for _ in range(5):
            limiteur.is_allowed("bruyant", True)

        assert limiteur.is_allowed("bruyant", True)[0] is False
        assert limiteur.is_allowed("discret", True)[0] is True


def test_le_repli_windows_utilise_un_verrou_du_noyau(tmp_path, monkeypatch):
    """
    Sous Windows, un arrêt brutal rendait tout redémarrage impossible.

    Mesuré sur la machine du propriétaire le 2026-08-22 : `fcntl` n'existe pas
    sous Windows, le repli testait `os.path.exists(chemin)`, et fermer la
    fenêtre du serveur laissait le fichier derrière lui. **GalSen IA ne
    redémarrait plus jamais** sans suppression manuelle du verrou.

    Le commentaire d'origine assumait « un faux positif coûte une suppression
    manuelle ». Sous Windows ce n'était pas un cas limite : c'était le chemin
    normal après chaque fermeture de fenêtre.

    `msvcrt.locking` est l'équivalent de `flock` — le noyau le relâche à la mort
    du processus. Ce test vérifie que le repli « existence du fichier » n'est
    plus emprunté quand `msvcrt` est disponible.
    """
    import src.api.instance_lock as verrou

    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(verrou, "fcntl", None)

    faux = types.SimpleNamespace(
        LK_NBLCK=1, LK_UNLCK=0, appels=[],
    )
    faux.locking = lambda fd, mode, taille: faux.appels.append(mode)
    monkeypatch.setattr(verrou, "msvcrt", faux)
    monkeypatch.setattr(verrou, "_descripteur", None)
    monkeypatch.setattr(verrou, "_chemin_detenu", None)

    # Un fichier de verrou traîne, comme après une fermeture brutale.
    chemin = verrou.lock_path()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fichier:
        fichier.write('{"instance": "morte", "pid": 999999}')

    # Avant la correction, ceci levait InstanceAlreadyRunning.
    verrou.acquire()
    assert faux.appels == [faux.LK_NBLCK], "le verrou du noyau n'a pas été pris"
    verrou.release()


def test_sans_fcntl_ni_msvcrt_le_repli_prudent_reste(tmp_path, monkeypatch):
    """
    Le repli « existence du fichier » n'est pas supprimé, il est relégué.

    Sur un système sans aucun verrou du noyau, refuser reste le bon choix : un
    faux négatif coûte deux instances sur les mêmes données, ce qu'ADR-013
    interdit.
    """
    import src.api.instance_lock as verrou

    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(verrou, "fcntl", None)
    monkeypatch.setattr(verrou, "msvcrt", None)
    monkeypatch.setattr(verrou, "_descripteur", None)
    monkeypatch.setattr(verrou, "_chemin_detenu", None)

    chemin = verrou.lock_path()
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as fichier:
        fichier.write("{}")

    with pytest.raises(verrou.InstanceAlreadyRunning):
        verrou.acquire()
