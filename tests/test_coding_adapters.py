"""
Tests des trois adaptateurs de moteurs de codage (ADR-028).

Ces tests sont déterministes et **bornés** : aucun n'attend un modèle, aucun ne
sort sur le réseau, aucun ne peut se figer.

- Aider et SWE-agent sont lancés en sous-processus. Les tests substituent un
  **faux exécutable** — un script qui enregistre ses arguments et rend ce qu'on
  lui a dit de rendre. La ligne de commande réellement construite est donc
  vérifiée, ce qu'aucun bouchon en mémoire ne permettrait.
- OpenHands est joint par HTTP. Les tests le confrontent à un **vrai serveur
  HTTP local** parlant les chemins de son serveur d'agent.

Les tests marqués `live` s'adressent aux vrais programmes ; ils sont ignorés
par défaut et ne s'exécutent que sur demande explicite :

    pytest -m live tests/test_coding_adapters.py

Ce qui est vérifié en priorité : qu'un moteur absent rend un **motif
actionnable** plutôt qu'une panne, et qu'un moteur qui n'a rien fait ne soit
jamais rapporté comme ayant réussi.
"""

import json
import os
import stat
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.coding_engine.adapters import (  # noqa: E402
    AiderAdapter,
    OpenHandsAdapter,
    SweAgentAdapter,
)
from src.coding_engine.types import (  # noqa: E402
    CodingStatus,
    CodingTask,
    ModelSpec,
    UnavailabilityReason,
)

MODELE_LOCAL = ModelSpec(
    provider_id="local", model_name="qwen2.5-coder:14b",
    base_url="http://127.0.0.1:11434",
)
MODELE_COMPATIBLE = ModelSpec(
    provider_id="openai_compatible", model_name="mon-modele",
    base_url="http://mon-serveur:8000/v1", api_key_env="MA_CLE",
)


# ----------------------------------------------------------------------
# Faux exécutable
# ----------------------------------------------------------------------

def _faux_executable(dossier, nom: str, sortie: str = "", code: int = 0,
                     cree: str = "") -> str:
    """
    Écrit un exécutable qui enregistre ses arguments puis rend ce qu'on veut.

    C'est ce qui permet de vérifier la **ligne de commande réellement
    construite** : un bouchon en mémoire ne dirait rien de ce qui part vers le
    programme externe.

    Args:
        dossier: Où écrire l'exécutable et son journal.
        nom: Nom de l'exécutable.
        sortie: Ce qu'il écrit sur la sortie standard.
        code: Son code de sortie.
        cree: Fichier qu'il crée dans son dossier de travail, pour éprouver le
            constat des changements. Il doit être créé **pendant** l'exécution :
            un fichier déjà présent au relevé initial n'est pas un changement.

    Returns:
        Le chemin de l'exécutable.
    """
    chemin = dossier / nom
    journal = dossier / f"{nom}.argv.json"
    chemin.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        f"journal = {str(journal)!r}\n"
        "with open(journal, 'w', encoding='utf-8') as f:\n"
        "    json.dump({'argv': sys.argv[1:], 'env': dict(os.environ),\n"
        "               'cwd': os.getcwd()}, f)\n"
        f"cree = {cree!r}\n"
        "if cree:\n"
        "    open(cree, 'w', encoding='utf-8').write('y = 2\\n')\n"
        f"sys.stdout.write({sortie!r})\n"
        f"sys.exit({code})\n",
        encoding="utf-8",
    )
    chemin.chmod(chemin.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return str(chemin)


def _appel(dossier, nom: str) -> dict:
    """Relit ce que le faux exécutable a enregistré."""
    return json.loads((dossier / f"{nom}.argv.json").read_text(encoding="utf-8"))


@pytest.fixture
def espace(tmp_path):
    """Un espace de travail avec un fichier."""
    espace = tmp_path / "projet"
    espace.mkdir()
    (espace / "module.py").write_text("x = 1\n", encoding="utf-8")
    return espace


def _tache(espace, **extras) -> CodingTask:
    """Construit une tâche minimale sur l'espace donné."""
    defauts = {
        "instruction": "Renomme la fonction",
        "workspace": str(espace),
        "timeout_seconds": 30,
    }
    defauts.update(extras)
    return CodingTask(**defauts)


# ======================================================================
# Aider
# ======================================================================

class TestAiderDisponibilite:
    """Un moteur absent doit rendre le geste qui répare, pas une panne."""

    def test_absent_le_motif_dit_comment_l_installer(self, monkeypatch):
        """Un « non disponible » sans mode d'emploi ne fait avancer personne."""
        monkeypatch.delenv("GALSEN_AIDER_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda _nom: None)
        etat = AiderAdapter().check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.NOT_INSTALLED
        assert "pip install" in etat.detail

    def test_present_la_version_est_relevee(self, tmp_path):
        """La version sert au diagnostic quand un drapeau disparaît en amont."""
        binaire = _faux_executable(tmp_path, "aider", sortie="aider 0.86.2\n")
        etat = AiderAdapter(binary=binaire).check_availability()
        assert etat.available is True
        assert etat.version == "aider 0.86.2"

    def test_un_executable_qui_echoue_n_est_pas_disponible(self, tmp_path):
        """Installé mais cassé n'est pas installé."""
        binaire = _faux_executable(tmp_path, "aider", sortie="boum", code=3)
        etat = AiderAdapter(binary=binaire).check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.NOT_CONFIGURED


class TestAiderCommande:
    """Ce qui part vers le programme externe est vérifié, pas supposé."""

    def _executer(self, tmp_path, espace, modele=MODELE_LOCAL, **extras):
        """Lance l'adaptateur contre le faux exécutable et rend l'appel capté."""
        binaire = _faux_executable(tmp_path, "aider")
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace, **extras), modele)
        return _appel(tmp_path, "aider"), resultat

    def test_l_instruction_et_le_mode_non_interactif(self, tmp_path, espace):
        """Sans `--message` et `--yes-always`, aider attendrait une saisie."""
        appel, _ = self._executer(tmp_path, espace)
        assert "--message" in appel["argv"]
        assert appel["argv"][appel["argv"].index("--message") + 1] == "Renomme la fonction"
        assert "--yes-always" in appel["argv"]

    def test_git_reste_a_la_plateforme(self, tmp_path, espace):
        """Un commit automatique empêcherait l'appelant de relire avant d'enregistrer."""
        appel, _ = self._executer(tmp_path, espace)
        assert "--no-auto-commits" in appel["argv"]
        assert "--no-dirty-commits" in appel["argv"]

    def test_sans_reseau_aider_ne_va_pas_chercher_d_url(self, tmp_path, espace):
        """Aider suit sinon toute URL trouvée dans la consigne."""
        appel, _ = self._executer(tmp_path, espace, allow_network=False)
        assert "--no-detect-urls" in appel["argv"]

    def test_avec_reseau_le_drapeau_disparait(self, tmp_path, espace):
        """L'autorisation doit avoir un effet, sinon elle ment."""
        appel, _ = self._executer(tmp_path, espace, allow_network=True)
        assert "--no-detect-urls" not in appel["argv"]

    def test_la_verification_a_blanc_est_transmise(self, tmp_path, espace):
        """`dry_run` doit atteindre le moteur, pas rester un drapeau décoratif."""
        appel, _ = self._executer(tmp_path, espace, dry_run=True)
        assert "--dry-run" in appel["argv"]

    def test_les_fichiers_designes_sont_transmis(self, tmp_path, espace):
        """Sans eux, aider devine le contexte et travaille moins bien."""
        appel, _ = self._executer(tmp_path, espace, files=["module.py"])
        assert appel["argv"][appel["argv"].index("--file") + 1] == "module.py"

    def test_un_fichier_hors_espace_est_refuse(self, tmp_path, espace):
        """Le confinement s'applique aussi aux fichiers de contexte."""
        binaire = _faux_executable(tmp_path, "aider")
        resultat = AiderAdapter(binary=binaire).execute(
            _tache(espace, files=["../dehors.py"]), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.FAILURE
        assert not (tmp_path / "aider.argv.json").exists()

    def test_la_commande_de_test_est_transmise(self, tmp_path, espace):
        """C'est ce qui rend la capacité `test_execution` honnête."""
        appel, _ = self._executer(tmp_path, espace, metadata={"test_command": "pytest -q"})
        assert "--test-cmd" in appel["argv"]
        assert "--auto-test" in appel["argv"]

    def test_le_modele_local_devient_ollama_chat(self, tmp_path, espace):
        """Le mode d'emploi d'aider recommande `ollama_chat/` pour la discussion."""
        appel, _ = self._executer(tmp_path, espace)
        assert appel["argv"][appel["argv"].index("--model") + 1] == "ollama_chat/qwen2.5-coder:14b"
        assert appel["env"]["OLLAMA_API_BASE"] == "http://127.0.0.1:11434"

    def test_un_service_compatible_passe_par_openai(self, tmp_path, espace, monkeypatch):
        """Un seul fournisseur GalSen ouvre vLLM, Groq, OpenRouter et le reste."""
        monkeypatch.setenv("MA_CLE", "cle-secrete")
        appel, _ = self._executer(tmp_path, espace, modele=MODELE_COMPATIBLE)
        assert appel["argv"][appel["argv"].index("--model") + 1] == "openai/mon-modele"
        assert appel["argv"][appel["argv"].index("--openai-api-base") + 1] == (
            "http://mon-serveur:8000/v1"
        )

    def test_la_cle_passe_par_l_environnement_pas_par_la_ligne(self, tmp_path, espace, monkeypatch):
        """Une ligne de commande est visible de toute la machine."""
        monkeypatch.setenv("MA_CLE", "cle-secrete")
        appel, _ = self._executer(tmp_path, espace, modele=MODELE_COMPATIBLE)
        assert "cle-secrete" not in " ".join(appel["argv"])
        assert appel["env"]["OPENAI_API_KEY"] == "cle-secrete"

    def test_les_secrets_de_la_plateforme_ne_fuient_pas(self, tmp_path, espace, monkeypatch):
        """Le sous-processus hériterait de tout sans le filtre."""
        monkeypatch.setenv("GALSEN_API_KEYS", "secret:admin:moi")
        appel, _ = self._executer(tmp_path, espace)
        assert "GALSEN_API_KEYS" not in appel["env"]

    def test_le_moteur_travaille_dans_l_espace(self, tmp_path, espace):
        """Un mauvais dossier de travail ferait modifier le mauvais dépôt."""
        appel, _ = self._executer(tmp_path, espace)
        assert os.path.realpath(appel["cwd"]) == os.path.realpath(str(espace))


class TestAiderNormalisation:
    """Un moteur qui n'a rien fait ne doit jamais être rapporté comme réussi."""

    def test_sans_modele_rien_n_est_lance(self, tmp_path, espace):
        """L'adaptateur ne choisit pas de modèle de son côté."""
        binaire = _faux_executable(tmp_path, "aider")
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), None)
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert not (tmp_path / "aider.argv.json").exists()

    def test_un_modele_injoignable_n_est_pas_un_succes(self, tmp_path, espace):
        """Vérifié contre aider 0.86.2 : il sort en **code 0** dans ce cas.

        Se fier au code de sortie ferait passer une exécution où le modèle n'a
        jamais répondu pour un travail accompli. C'est la fabrication que
        `.claude/rules/verification.md` interdit nommément.
        """
        binaire = _faux_executable(
            tmp_path, "aider",
            sortie="litellm.APIConnectionError - [Errno 111] Connection refused\n",
            code=0,
        )
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert "n'a pas répondu" in resultat.summary

    @pytest.mark.parametrize("trace,attendu", [
        ("litellm.AuthenticationError: bad key", "identifiants refusés"),
        ("litellm.RateLimitError: slow down", "quota"),
        ("litellm.NotFoundError: no such model", "modèle inconnu"),
    ])
    def test_chaque_panne_de_modele_porte_son_motif(self, tmp_path, espace, trace, attendu):
        """Un motif générique laisserait l'exploitant sans piste."""
        binaire = _faux_executable(tmp_path, "aider", sortie=trace, code=0)
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert attendu in resultat.summary

    def test_une_execution_sans_changement_est_signalee(self, tmp_path, espace):
        """Réussir sans rien modifier mérite au moins un avertissement."""
        binaire = _faux_executable(tmp_path, "aider", sortie="Rien à faire.\n")
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.status is CodingStatus.SUCCESS
        assert resultat.warnings

    def test_les_fichiers_sont_constates_sur_le_disque(self, tmp_path, espace):
        """Ce que le moteur dit et ce qu'il fait sont deux choses.

        Le fichier est créé **par le faux moteur**, pendant l'exécution : le
        créer avant le lancement le ferait figurer au relevé initial, et le
        test passerait sans rien prouver.
        """
        binaire = _faux_executable(tmp_path, "aider", cree="cree_par_le_moteur.py")
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert "cree_par_le_moteur.py" in [f.path for f in resultat.files_changed]
        assert resultat.warnings == []

    def test_les_artefacts_d_aider_ne_comptent_pas(self, tmp_path, espace):
        """Son cache et son historique ne sont pas le travail demandé."""
        binaire = _faux_executable(tmp_path, "aider", cree=".aider.chat.history.md")
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.files_changed == []

    def test_un_echec_est_rapporte_comme_tel(self, tmp_path, espace):
        """Un code non nul est un échec, pas un succès silencieux."""
        binaire = _faux_executable(tmp_path, "aider", sortie="erreur fatale", code=2)
        resultat = AiderAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.status is CodingStatus.FAILURE
        assert resultat.errors

    def test_un_moteur_trop_lent_est_arrete(self, tmp_path, espace):
        """Aucune exécution ne peut immobiliser l'appelant indéfiniment."""
        binaire = tmp_path / "aider"
        binaire.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(60)\n", encoding="utf-8")
        binaire.chmod(binaire.stat().st_mode | stat.S_IEXEC)
        resultat = AiderAdapter(binary=str(binaire)).execute(
            _tache(espace, timeout_seconds=2), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.TIMEOUT
        assert resultat.execution_time_seconds < 30


# ======================================================================
# SWE-agent
# ======================================================================

class TestSweAgent:
    """Le moteur de résolution de problème, et son besoin de Docker."""

    def test_absent_le_motif_dit_comment_l_installer(self, monkeypatch):
        """Même exigence que pour aider : un motif actionnable."""
        monkeypatch.delenv("GALSEN_SWE_AGENT_BIN", raising=False)
        monkeypatch.setattr("shutil.which", lambda _nom: None)
        etat = SweAgentAdapter().check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.NOT_INSTALLED

    def test_sans_docker_l_infrastructure_manque(self, tmp_path, monkeypatch):
        """« Moteur absent » et « Docker absent » appellent des gestes différents.

        SWE-agent exécute l'agent dans un conteneur : sans Docker, l'exécution
        échouerait au démarrage, et rapporter un simple échec de moteur
        enverrait l'exploitant réinstaller ce qui est déjà installé.
        """
        binaire = _faux_executable(tmp_path, "sweagent", sortie="sweagent 1.0\n")
        monkeypatch.setattr(
            "src.coding_engine.adapters.swe_agent_adapter.shutil.which",
            lambda nom: None if nom == "docker" else binaire,
        )
        etat = SweAgentAdapter(binary=binaire).check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.MISSING_INFRASTRUCTURE
        assert "Docker" in etat.detail

    def _executer(self, tmp_path, espace, monkeypatch, modele=MODELE_LOCAL, **extras):
        """Lance l'adaptateur avec Docker simulé présent."""
        binaire = _faux_executable(tmp_path, "sweagent", sortie="sweagent 1.0\n")
        monkeypatch.setattr(
            "src.coding_engine.adapters.swe_agent_adapter.shutil.which",
            lambda nom: "/usr/bin/docker" if nom == "docker" else binaire,
        )
        resultat = SweAgentAdapter(binary=binaire).execute(_tache(espace, **extras), modele)
        return _appel(tmp_path, "sweagent"), resultat

    def test_l_enonce_et_le_depot_sont_transmis(self, tmp_path, espace, monkeypatch):
        """Ce sont les deux entrées du moteur ; sans elles il ne fait rien."""
        appel, _ = self._executer(tmp_path, espace, monkeypatch)
        argv = " ".join(appel["argv"])
        assert "run" in appel["argv"]
        assert f"--env.repo.path={os.path.realpath(str(espace))}" in argv
        assert "--problem_statement.text=Renomme la fonction" in argv

    def test_les_limites_de_cout_sont_neutralisees(self, tmp_path, espace, monkeypatch):
        """Sa documentation les impose pour un modèle auto-hébergé.

        Le calcul de coût s'appuie sur le registre litellm public, absent pour
        ces modèles : sans les trois zéros l'exécution échoue au démarrage.
        """
        appel, _ = self._executer(tmp_path, espace, monkeypatch)
        argv = " ".join(appel["argv"])
        assert "--agent.model.per_instance_cost_limit=0" in argv
        assert "--agent.model.total_cost_limit=0" in argv
        assert "--agent.model.max_input_tokens=0" in argv

    def test_le_modele_local_devient_ollama(self, tmp_path, espace, monkeypatch):
        """La convention de SWE-agent est `fournisseur/modèle`."""
        appel, _ = self._executer(tmp_path, espace, monkeypatch)
        argv = " ".join(appel["argv"])
        assert "--agent.model.name=ollama/qwen2.5-coder:14b" in argv
        assert "--agent.model.api_base=http://127.0.0.1:11434" in argv

    def test_la_cle_reelle_passe_par_l_environnement(self, tmp_path, espace, monkeypatch):
        """Une vraie clé ne doit jamais figurer dans une ligne de commande."""
        monkeypatch.setenv("MA_CLE", "cle-secrete")
        appel, _ = self._executer(tmp_path, espace, monkeypatch, modele=MODELE_COMPATIBLE)
        assert "cle-secrete" not in " ".join(appel["argv"])
        assert appel["env"]["OPENAI_API_KEY"] == "cle-secrete"

    def test_sans_cle_une_valeur_factice_est_passee(self, tmp_path, espace, monkeypatch):
        """litellm en exige une même quand le service ne la vérifie pas."""
        appel, _ = self._executer(tmp_path, espace, monkeypatch)
        assert any("--agent.model.api_key=" in argument for argument in appel["argv"])

    def test_sans_modele_rien_n_est_lance(self, tmp_path, espace, monkeypatch):
        """L'adaptateur ne choisit pas de modèle de son côté."""
        binaire = _faux_executable(tmp_path, "sweagent", sortie="sweagent 1.0\n")
        monkeypatch.setattr(
            "src.coding_engine.adapters.swe_agent_adapter.shutil.which",
            lambda nom: "/usr/bin/docker" if nom == "docker" else binaire,
        )
        resultat = SweAgentAdapter(binary=binaire).execute(_tache(espace), None)
        assert resultat.status is CodingStatus.UNAVAILABLE

    def test_un_resume_json_est_lu(self, tmp_path, espace, monkeypatch):
        """Le projet écrit des lignes JSON quand il le peut."""
        binaire = _faux_executable(
            tmp_path, "sweagent", sortie='{"summary": "Bogue corrigé dans parser.py"}\n'
        )
        monkeypatch.setattr(
            "src.coding_engine.adapters.swe_agent_adapter.shutil.which",
            lambda nom: "/usr/bin/docker" if nom == "docker" else binaire,
        )
        resultat = SweAgentAdapter(binary=binaire).execute(_tache(espace), MODELE_LOCAL)
        assert resultat.status is CodingStatus.SUCCESS
        assert resultat.summary == "Bogue corrigé dans parser.py"


# ======================================================================
# OpenHands
# ======================================================================

ETAT_SERVEUR = {"execution_status": "finished", "code_creation": 201, "detail": None}
REQUETES = []


class _ServeurAgent(BaseHTTPRequestHandler):
    """Sert les chemins du serveur d'agent OpenHands."""

    def do_GET(self):  # noqa: N802 — nom imposé par http.server
        """Santé, état de conversation, réponse finale."""
        if self.path == "/health":
            return self._json({"status": "ok"})
        if self.path.endswith("/agent_final_response"):
            return self._json({"response": "Fonctionnalité implémentée."})
        if self.path.startswith("/api/conversations/"):
            return self._json({"execution_status": ETAT_SERVEUR["execution_status"]})
        self.send_error(404)

    def do_POST(self):  # noqa: N802 — nom imposé par http.server
        """Création et lancement de conversation."""
        taille = int(self.headers.get("Content-Length", 0))
        corps = self.rfile.read(taille) if taille else b"{}"
        REQUETES.append({
            "path": self.path,
            "body": json.loads(corps or b"{}"),
            "auth": self.headers.get("X-Session-API-Key"),
        })
        if self.path == "/api/conversations":
            if ETAT_SERVEUR["code_creation"] != 201:
                self.send_response(ETAT_SERVEUR["code_creation"])
                message = json.dumps({"detail": ETAT_SERVEUR["detail"]}).encode()
                self.send_header("Content-Length", str(len(message)))
                self.end_headers()
                return self.wfile.write(message)
            return self._json({"id": "11111111-1111-1111-1111-111111111111"})
        return self._json({"success": True})

    def _json(self, charge: dict) -> None:
        """Écrit une réponse JSON."""
        corps = json.dumps(charge).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)

    def log_message(self, *_args):
        """Silence."""


@pytest.fixture
def serveur_agent():
    """Démarre un serveur parlant l'API du serveur d'agent OpenHands."""
    ETAT_SERVEUR.update({"execution_status": "finished", "code_creation": 201, "detail": None})
    REQUETES.clear()
    httpd = HTTPServer(("127.0.0.1", 0), _ServeurAgent)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()


class TestOpenHands:
    """Le moteur autonome, piloté par HTTP plutôt qu'en sous-processus."""

    def test_sans_adresse_le_motif_donne_la_commande_docker(self, monkeypatch):
        """L'exploitant doit savoir quoi lancer, pas seulement que ça manque."""
        monkeypatch.delenv("GALSEN_OPENHANDS_URL", raising=False)
        etat = OpenHandsAdapter().check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.NOT_CONFIGURED
        assert "docker run" in etat.detail

    def test_un_serveur_eteint_est_injoignable(self):
        """Port fermé : indisponible, avec l'adresse en cause."""
        etat = OpenHandsAdapter(base_url="http://127.0.0.1:1").check_availability()
        assert etat.available is False
        assert etat.reason is UnavailabilityReason.UNREACHABLE

    def test_un_serveur_present_est_disponible(self, serveur_agent):
        """La sonde suit `/health`, comme le serveur d'agent l'expose."""
        assert OpenHandsAdapter(base_url=serveur_agent).check_availability().available is True

    def test_la_traversee_complete(self, serveur_agent, espace):
        """Créer, lancer, scruter, lire la réponse finale : le déroulé réel."""
        resultat = OpenHandsAdapter(base_url=serveur_agent).execute(
            _tache(espace), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.SUCCESS
        assert resultat.summary == "Fonctionnalité implémentée."
        chemins = [r["path"] for r in REQUETES]
        assert "/api/conversations" in chemins
        assert any(chemin.endswith("/run") for chemin in chemins)

    def test_la_tache_et_le_modele_partent_bien(self, serveur_agent, espace):
        """Un serveur qui reçoit une conversation vide ne fait rien d'utile."""
        OpenHandsAdapter(base_url=serveur_agent).execute(_tache(espace), MODELE_LOCAL)
        creation = next(r for r in REQUETES if r["path"] == "/api/conversations")
        assert creation["body"]["initial_message"]["content"][0]["text"] == "Renomme la fonction"
        assert creation["body"]["agent"]["llm"]["model"] == "ollama/qwen2.5-coder:14b"
        assert creation["body"]["workspace"]["working_dir"] == os.path.realpath(str(espace))

    def test_la_cle_de_session_part_en_entete(self, serveur_agent, espace):
        """`X-Session-API-Key`, comme le serveur d'agent l'attend."""
        OpenHandsAdapter(base_url=serveur_agent, api_key="ma-session").execute(
            _tache(espace), MODELE_LOCAL
        )
        assert REQUETES[0]["auth"] == "ma-session"

    def test_un_etat_en_echec_n_est_pas_un_succes(self, serveur_agent, espace):
        """`error` et `stuck` sont terminaux, mais ce ne sont pas des réussites."""
        ETAT_SERVEUR["execution_status"] = "error"
        resultat = OpenHandsAdapter(base_url=serveur_agent).execute(
            _tache(espace), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.FAILURE

    def test_un_refus_du_serveur_remonte_son_detail(self, serveur_agent, espace):
        """Un 422 dit quel champ manque ; le perdre laisserait sans piste.

        C'est la limite connue de cet adaptateur : le schéma de création évolue
        avec les versions du serveur d'agent, et le détail du refus est la seule
        façon de s'y adapter sans deviner.
        """
        ETAT_SERVEUR["code_creation"] = 422
        ETAT_SERVEUR["detail"] = "champ « agent.tools » manquant"
        resultat = OpenHandsAdapter(base_url=serveur_agent).execute(
            _tache(espace), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.FAILURE
        assert "agent.tools" in resultat.errors[0]

    def test_une_conversation_qui_ne_finit_pas_est_bornee(self, serveur_agent, espace):
        """La boucle de scrutation ne peut pas tourner indéfiniment."""
        ETAT_SERVEUR["execution_status"] = "running"
        resultat = OpenHandsAdapter(base_url=serveur_agent).execute(
            _tache(espace, timeout_seconds=3), MODELE_LOCAL
        )
        assert resultat.status is CodingStatus.TIMEOUT
        assert resultat.execution_time_seconds < 30

    def test_sans_modele_rien_n_est_envoye(self, serveur_agent, espace):
        """L'adaptateur ne choisit pas de modèle de son côté."""
        resultat = OpenHandsAdapter(base_url=serveur_agent).execute(_tache(espace), None)
        assert resultat.status is CodingStatus.UNAVAILABLE
        assert REQUETES == []


# ======================================================================
# Tests vivants — ignorés par défaut
# ======================================================================

class TestVivants:
    """
    S'adressent aux vrais programmes. Marqués `live`, ignorés par défaut.

    Ils ne sont pas dans la suite ordinaire parce qu'ils dépendent d'une
    installation extérieure. Ils restent utiles : c'est ainsi que le défaut du
    code de sortie d'aider a été trouvé.
    """

    @pytest.mark.live
    def test_aider_reel_repond_a_la_sonde(self):
        """Exige `GALSEN_AIDER_BIN` ou `aider` dans le PATH."""
        etat = AiderAdapter().check_availability()
        if not etat.available:
            pytest.skip(etat.detail)
        assert etat.version

    @pytest.mark.live
    def test_swe_agent_reel_repond_a_la_sonde(self):
        """Exige `sweagent` et Docker."""
        etat = SweAgentAdapter().check_availability()
        if not etat.available:
            pytest.skip(etat.detail)
        assert etat.version

    @pytest.mark.live
    def test_openhands_reel_repond_a_la_sonde(self):
        """Exige un serveur d'agent joignable via `GALSEN_OPENHANDS_URL`."""
        etat = OpenHandsAdapter().check_availability()
        if not etat.available:
            pytest.skip(etat.detail)
        assert etat.available is True
