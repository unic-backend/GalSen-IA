"""
Adaptateur OpenHands : implémentation autonome de bout en bout (ADR-028).

OpenHands est sous MIT. Son interface (`OpenHands/OpenHands`) est aujourd'hui une
application TypeScript ; le moteur qui travaille réellement est le **serveur
d'agent** (`ghcr.io/openhands/agent-server`), un service Python exposant une API
REST. C'est ce service que cet adaptateur pilote.

D'où la forme de l'intégration, et elle est différente des deux autres :
OpenHands n'est ni importé ni lancé en sous-processus, il est **joint par HTTP**.
L'exploitant lance le conteneur ; GalSen IA lui parle. Aucune dépendance Python
n'est ajoutée, et le conteneur fournit au passage l'isolation que
`workspace.py` ne peut pas donner à un sous-processus local.

Chemins employés, relevés dans le code du serveur d'agent :

    GET  /health                                     état du service
    POST /api/conversations                          créer une conversation
    POST /api/conversations/{id}/run                 lancer l'exécution
    GET  /api/conversations/{id}                     lire `execution_status`
    GET  /api/conversations/{id}/agent_final_response réponse finale de l'agent

L'authentification, quand elle est active, passe par l'en-tête
`X-Session-API-Key`.

Configuration :

    GALSEN_OPENHANDS_URL       http://localhost:8010 par exemple (obligatoire)
    GALSEN_OPENHANDS_API_KEY   clé de session, si le serveur en exige une

**Limite connue** : le corps de création de conversation dépend du schéma du
serveur d'agent, qui évolue avec ses versions. L'adaptateur envoie le corps
minimal documenté et **remonte tel quel** le détail d'un refus 422, plutôt que
de prétendre avoir réussi. C'est écrit dans ADR-028, section *Limites connues*.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from src.coding_engine.interfaces import CodingEngineAdapter
from src.coding_engine.types import (
    CodingCapability,
    CodingStatus,
    CodingTask,
    CodingTaskResult,
    EngineAvailability,
    ModelSpec,
    UnavailabilityReason,
)
from src.coding_engine.workspace import (
    WorkspaceError,
    diff_snapshots,
    git_changes,
    resolve_workspace,
    snapshot,
)

VARIABLE_URL = "GALSEN_OPENHANDS_URL"
VARIABLE_CLE = "GALSEN_OPENHANDS_API_KEY"

DELAI_SONDE_SECONDES = 5
DELAI_APPEL_SECONDES = 60
INTERVALLE_SCRUTATION_SECONDES = 2.0

# États terminaux du serveur d'agent : au-delà, il n'y a plus rien à attendre.
ETATS_TERMINAUX = frozenset({"finished", "error", "stuck"})
ETATS_EN_ECHEC = frozenset({"error", "stuck"})


class OpenHandsAdapter(CodingEngineAdapter):
    """Pilote un serveur d'agent OpenHands par son API REST."""

    engine_id = "openhands"
    display_name = "OpenHands"
    primary_capability = CodingCapability.AUTONOMOUS_IMPLEMENTATION
    capabilities = [
        CodingCapability.AUTONOMOUS_IMPLEMENTATION,
        CodingCapability.REPOSITORY_EXPLORATION,
        CodingCapability.SHELL_EXECUTION,
        CodingCapability.TEST_EXECUTION,
        CodingCapability.TARGETED_EDIT,
        CodingCapability.ISSUE_RESOLUTION,
    ]

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialise l'adaptateur.

        Args:
            base_url: Adresse du serveur d'agent. Lue dans l'environnement sinon.
            api_key: Clé de session éventuelle.
        """
        self._base_url = (base_url or os.environ.get(VARIABLE_URL, "")).strip().rstrip("/")
        self._api_key = api_key if api_key is not None else os.environ.get(VARIABLE_CLE)

    # ------------------------------------------------------------------
    # Disponibilité
    # ------------------------------------------------------------------

    def check_availability(self) -> EngineAvailability:
        """
        Vérifie qu'un serveur d'agent répond à l'adresse déclarée.

        Returns:
            L'état du moteur, avec la commande Docker s'il n'est pas lancé.
        """
        if not self._base_url:
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.NOT_CONFIGURED,
                detail="Aucune adresse déclarée. Lancez le serveur d'agent "
                       "(`docker run -p 8010:8000 ghcr.io/openhands/agent-server:"
                       f"latest-python`) puis renseignez {VARIABLE_URL}.",
                capabilities=self.capabilities,
            )
        try:
            self._appeler("GET", "/health", delai=DELAI_SONDE_SECONDES)
        except _HttpError as erreur:
            return EngineAvailability(
                engine_id=self.engine_id, available=False,
                reason=UnavailabilityReason.UNREACHABLE,
                detail=f"{self._base_url} ne répond pas : {erreur}",
                capabilities=self.capabilities,
            )
        return EngineAvailability(
            engine_id=self.engine_id, available=True, capabilities=self.capabilities
        )

    # ------------------------------------------------------------------
    # Exécution
    # ------------------------------------------------------------------

    def execute(self, task: CodingTask, model: Optional[ModelSpec]) -> CodingTaskResult:
        """
        Confie une implémentation complète au serveur d'agent.

        Le déroulé suit l'API du serveur : créer la conversation, la lancer,
        puis scruter son état jusqu'à un état terminal ou l'expiration du délai.

        Args:
            task: La tâche à réaliser.
            model: Le modèle imposé par la plateforme.

        Returns:
            Le résultat normalisé.
        """
        debut = time.time()
        etat = self.check_availability()
        if not etat.available:
            return CodingTaskResult.unavailable(self.engine_id, task.id, etat.detail)
        if model is None:
            return CodingTaskResult.unavailable(
                self.engine_id, task.id,
                "Aucun modèle disponible. OpenHands ne choisit pas de modèle de "
                "lui-même : configurez un fournisseur GalSen IA.",
            )

        try:
            espace = resolve_workspace(task.workspace)
        except WorkspaceError as erreur:
            return CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id=self.engine_id, task_id=task.id,
                summary=str(erreur), errors=[str(erreur)],
                execution_time_seconds=time.time() - debut,
            )

        avant = snapshot(espace)
        try:
            conversation = self._creer_conversation(task, model, espace)
            identifiant = conversation.get("id")
            if not identifiant:
                raise _HttpError("le serveur n'a pas rendu d'identifiant de conversation")
            self._appeler("POST", f"/api/conversations/{identifiant}/run")
            statut_final, detail = self._attendre(identifiant, task, debut)
            reponse = self._reponse_finale(identifiant)
        except _HttpError as erreur:
            return CodingTaskResult(
                status=CodingStatus.FAILURE, engine_id=self.engine_id, task_id=task.id,
                summary=f"Le serveur OpenHands a refusé la tâche : {erreur}",
                errors=[str(erreur)], execution_time_seconds=time.time() - debut,
                model=model, files_changed=self._changements(espace, avant),
            )

        return CodingTaskResult(
            status=statut_final,
            engine_id=self.engine_id,
            task_id=task.id,
            summary=(reponse or detail or "OpenHands a terminé.")[:1000],
            files_changed=self._changements(espace, avant),
            errors=[detail] if statut_final is not CodingStatus.SUCCESS and detail else [],
            execution_time_seconds=time.time() - debut,
            model=model,
            raw_metadata={"conversation_id": str(identifiant), "execution_status": detail},
        )

    # ------------------------------------------------------------------
    # Dialogue avec le serveur
    # ------------------------------------------------------------------

    def _creer_conversation(self, task: CodingTask, model: ModelSpec, espace) -> Dict[str, Any]:
        """
        Crée une conversation portant la tâche.

        Le corps suit l'exemple publié par le serveur d'agent : un agent avec sa
        configuration de modèle, un espace de travail, et le message initial.
        """
        llm: Dict[str, Any] = {
            "usage_id": "galsen-coding-engine",
            "model": _traduire_modele(model),
        }
        if model.base_url:
            llm["base_url"] = model.base_url
        if model.api_key_env and os.environ.get(model.api_key_env):
            llm["api_key"] = os.environ[model.api_key_env]

        charge = {
            "agent": {"llm": llm},
            "workspace": {"working_dir": str(espace)},
            "initial_message": {
                "role": "user",
                "content": [{"text": task.instruction}],
            },
        }
        charge.update(task.metadata.get("openhands_overrides", {}))
        return self._appeler("POST", "/api/conversations", charge)

    def _attendre(self, identifiant: str, task: CodingTask, debut: float) -> tuple:
        """
        Scrute l'état de la conversation jusqu'à un état terminal.

        La borne est celle de la tâche : la boucle ne peut pas tourner
        indéfiniment, même si le serveur ne répond plus jamais.

        Returns:
            Le couple (statut GalSen, dernier état rapporté par le serveur).
        """
        dernier = ""
        while time.time() - debut < task.timeout_seconds:
            try:
                conversation = self._appeler("GET", f"/api/conversations/{identifiant}")
            except _HttpError as erreur:
                return CodingStatus.FAILURE, str(erreur)

            dernier = str(conversation.get("execution_status", "")).lower()
            if dernier in ETATS_TERMINAUX:
                return (
                    CodingStatus.FAILURE if dernier in ETATS_EN_ECHEC
                    else CodingStatus.SUCCESS
                ), dernier
            time.sleep(INTERVALLE_SCRUTATION_SECONDES)

        # Le délai est écoulé : on interrompt la conversation pour ne pas
        # laisser un agent travailler dans le vide, puis on le dit.
        try:
            self._appeler("POST", f"/api/conversations/{identifiant}/pause")
        except _HttpError:
            pass
        return CodingStatus.TIMEOUT, dernier or "timeout"

    def _reponse_finale(self, identifiant: str) -> str:
        """Lit la réponse finale de l'agent, si elle existe."""
        try:
            charge = self._appeler(
                "GET", f"/api/conversations/{identifiant}/agent_final_response"
            )
        except _HttpError:
            return ""
        return str(charge.get("response", ""))

    def _changements(self, espace, avant: Dict) -> list:
        """Constate les fichiers touchés dans l'espace de travail."""
        changements = git_changes(espace)
        return changements if changements is not None else diff_snapshots(avant, snapshot(espace))

    def _appeler(
        self,
        methode: str,
        chemin: str,
        charge: Optional[Dict[str, Any]] = None,
        delai: int = DELAI_APPEL_SECONDES,
    ) -> Dict[str, Any]:
        """
        Exécute un appel HTTP vers le serveur d'agent.

        Args:
            methode: Verbe HTTP.
            chemin: Chemin, à partir de la racine du serveur.
            charge: Corps JSON éventuel.
            delai: Borne de l'appel, en secondes.

        Returns:
            Le corps de réponse, ou un dictionnaire vide s'il est absent.

        Raises:
            _HttpError: Refus du serveur, service injoignable, ou JSON illisible.
                Le détail du serveur est conservé : un 422 dit précisément quel
                champ manque, et le perdre laisserait l'exploitant sans piste.
        """
        entetes = {"Content-Type": "application/json"}
        if self._api_key:
            entetes["X-Session-API-Key"] = self._api_key

        requete = urllib.request.Request(
            f"{self._base_url}{chemin}",
            data=json.dumps(charge).encode("utf-8") if charge is not None else None,
            headers=entetes,
            method=methode,
        )
        try:
            with urllib.request.urlopen(requete, timeout=delai) as reponse:
                corps = reponse.read().decode("utf-8")
        except urllib.error.HTTPError as erreur:
            detail = erreur.read().decode("utf-8", errors="replace")[:600]
            raise _HttpError(f"HTTP {erreur.code} sur {chemin} — {detail}") from erreur
        except (urllib.error.URLError, OSError) as erreur:
            raise _HttpError(f"{chemin} injoignable : {erreur}") from erreur

        if not corps.strip():
            return {}
        try:
            charge_lue = json.loads(corps)
        except json.JSONDecodeError as erreur:
            raise _HttpError(f"réponse illisible sur {chemin} : {erreur}") from erreur
        return charge_lue if isinstance(charge_lue, dict) else {"data": charge_lue}


class _HttpError(RuntimeError):
    """Échec de dialogue avec le serveur d'agent OpenHands."""


def _traduire_modele(model: ModelSpec) -> str:
    """
    Traduit un `ModelSpec` GalSen dans la convention d'OpenHands.

    Le serveur d'agent attend `fournisseur/modèle`, comme litellm. Aucun modèle
    par défaut n'est choisi ici : c'est la plateforme qui décide.
    """
    if "/" in model.model_name:
        return model.model_name
    if model.provider_id == "local":
        return f"ollama/{model.model_name}"
    if model.provider_id == "openai_compatible":
        return f"openai/{model.model_name}"
    return f"{model.provider_id}/{model.model_name}"
