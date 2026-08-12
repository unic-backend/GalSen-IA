"""
Agent Context for GalSen IA.

The context is what an agent receives when it runs. It carries the request being
processed, the results produced by the agents that ran before, and a handle on
every engine of the platform.

Agents never instantiate an engine themselves: they go through the context, so
that all agents of a single request share the same memory, the same knowledge
base and the same documents.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from ..approval_engine.types import ApprovalRequest
from ..audit_engine.types import AuditEvent, AuditEventType, AuditStatus, generate_request_id
from ..integration.engine_registry import EngineRegistry, get_shared_registry
from .blackboard import Blackboard

# Profondeur maximale de délégation d'agent à agent. Trois niveaux suffisent à un
# travail composé ; au-delà, on a une boucle plutôt qu'une décomposition.
MAX_DELEGATION_DEPTH = 3


class AgentContext:
    """
    Contexte d'exécution transmis à chaque agent.

    Il expose deux niveaux d'accès :

    - les moteurs bruts (`context.registry.document`, ...) pour les besoins avancés ;
    - des raccourcis (`remember`, `recall`, `search_web`, ...) pour les usages
      courants, qui gèrent déjà l'indisponibilité d'un moteur.

    Les raccourcis ne lèvent jamais d'exception quand un moteur est absent : ils
    retournent une valeur vide et le consignent. Un agent ne doit pas échouer
    parce qu'un moteur optionnel manque.
    """

    def __init__(
        self,
        request: Any,
        agent_id: str = "unknown",
        registry: Optional[EngineRegistry] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        previous_results: Optional[List[Dict[str, Any]]] = None,
        options: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        blackboard: Optional["Blackboard"] = None,
        delegation_depth: int = 0,
    ):
        """
        Initialise le contexte.

        Args:
            request: Requête en cours de traitement
            agent_id: Identifiant de l'agent qui va s'exécuter
            registry: Registre des moteurs, le registre partagé par défaut
            user_id: Utilisateur à l'origine de la requête, pour isoler ses mémoires
            session_id: Session courante, générée si absente
            previous_results: Résultats des agents déjà exécutés dans cette requête
            options: Options libres transmises par l'orchestrateur
            request_id: Identifiant de la requête, généré si absent
            blackboard: État de travail partagé (VOLET 29) ; créé si absent et
                **partagé tel quel** par les contextes dérivés — une copie ferait
                deux vérités.
            delegation_depth: Profondeur de délégation atteinte. Sert à borner
                les appels d'agent à agent, qui sinon peuvent boucler.
        """
        self.request = request
        self.agent_id = agent_id
        self.registry = registry or get_shared_registry()
        self.user_id = user_id
        self.session_id = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self.previous_results = previous_results or []
        self.options = options or {}
        self.request_id = request_id or generate_request_id()
        self.started_at = time.time()
        self.blackboard = blackboard if blackboard is not None else Blackboard()
        self.delegation_depth = delegation_depth

        self._logger = logging.getLogger(f"{__name__}.{agent_id}")

    # ------------------------------------------------------------------
    # Requête et résultats précédents
    # ------------------------------------------------------------------
    def request_text(self) -> str:
        """
        Retourne la requête sous forme de texte exploitable.

        L'orchestrateur transmet parfois le résultat structuré de l'agent
        précédent : on en extrait alors la partie textuelle.
        """
        return self._extract_text(self.request)

    def previous_result(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Retourne le résultat d'un agent précédent.

        Args:
            agent_id: Identifiant de l'agent recherché

        Returns:
            Le dernier résultat produit par cet agent, ou None
        """
        for result in reversed(self.previous_results):
            if result.get("agent") == agent_id:
                return result
        return None

    def derive(self, agent_id: str) -> "AgentContext":
        """
        Crée le contexte de l'agent suivant, en conservant l'état de la requête.

        Args:
            agent_id: Identifiant de l'agent qui recevra le nouveau contexte

        Returns:
            Un contexte partageant le registre, la session et l'historique
        """
        return AgentContext(
            request=self.request,
            agent_id=agent_id,
            registry=self.registry,
            user_id=self.user_id,
            session_id=self.session_id,
            previous_results=self.previous_results,
            options=self.options,
            request_id=self.request_id,
            # Même tableau noir, pas une copie : deux instances feraient deux
            # états de travail, et l'agent dérivé ne verrait pas ce que son
            # prédécesseur vient de déposer.
            blackboard=self.blackboard,
            delegation_depth=self.delegation_depth,
        )

    # ------------------------------------------------------------------
    # Plan du planificateur
    # ------------------------------------------------------------------
    def tasks(self) -> List[Dict[str, Any]]:
        """
        Retourne les tâches décidées par le planificateur pour cette requête.

        Returns:
            La liste des tâches, vide si le planificateur n'a pas tourné.
        """
        plan = self.previous_result("planner") or {}
        resultat = plan.get("result") if isinstance(plan.get("result"), dict) else plan
        taches = resultat.get("tasks") if isinstance(resultat, dict) else None
        return taches if isinstance(taches, list) else []

    def tasks_for(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retourne les tâches assignées à un agent.

        Le planificateur assigne chaque tâche à un agent depuis longtemps, et
        **personne ne lisait cette assignation**. `coder` se contentait de
        vérifier qu'un plan existait, puis rapportait `plan_followed: true` —
        une affirmation vraie sur l'existence du plan et fausse sur son suivi.

        Args:
            agent_id: Agent concerné ; celui de ce contexte par défaut.

        Returns:
            Les tâches qui lui reviennent, dans l'ordre du plan.
        """
        cible = agent_id or self.agent_id
        return [
            tache for tache in self.tasks()
            if tache.get("assigned_agent") == cible
            or cible in (tache.get("assigned_agents") or [])
        ]

    # ------------------------------------------------------------------
    # État de travail partagé et délégation
    # ------------------------------------------------------------------
    def post(self, topic: str, value: Any, to: Optional[str] = None) -> None:
        """
        Dépose une observation sur le tableau noir partagé (VOLET 29).

        Args:
            topic: Sujet de l'observation.
            value: Contenu.
            to: Agent destinataire, si elle en vise un.
        """
        self.blackboard.post(topic, value, author=self.agent_id, to=to)

    def read_notes(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lit les observations qui concernent cet agent.

        Args:
            topic: Sujet recherché ; tous si None.

        Returns:
            Les notes adressées à cet agent ou à personne, sérialisées.
        """
        return [note.to_dict() for note in self.blackboard.read(topic, pour=self.agent_id)]

    def delegate(self, agent_id: str, task: Any = None) -> Dict[str, Any]:
        """
        Confie un travail à un autre agent, dans la même requête.

        C'est la capacité qui manquait : un agent pouvait lire ce que les
        précédents avaient produit, mais pas demander quelque chose à un autre.

        Deux garde-fous, et ils ne sont pas décoratifs : des agents qui
        s'appellent librement forment des cycles, et un cycle sans borne
        consomme toute la requête sans jamais rendre de réponse.

        - **Profondeur bornée** (`MAX_DELEGATION_DEPTH`).
        - **Pas d'auto-délégation**, ni retour vers un agent déjà dans la chaîne.

        Args:
            agent_id: Agent sollicité.
            task: Travail confié ; la requête courante par défaut.

        Returns:
            Le résultat de l'agent, ou un statut expliquant le refus. Un refus
            est une donnée : l'agent appelant doit pouvoir continuer sans.
        """
        if agent_id == self.agent_id:
            return {"status": "refused", "reason": "self_delegation",
                    "detail": f"« {agent_id} » ne peut pas se déléguer à lui-même."}

        chaine = self.options.get("delegation_chain", [])
        if agent_id in chaine:
            return {"status": "refused", "reason": "cycle",
                    "detail": f"« {agent_id} » est déjà dans la chaîne {chaine} : cycle refusé."}

        if self.delegation_depth >= MAX_DELEGATION_DEPTH:
            return {"status": "refused", "reason": "depth_exceeded",
                    "detail": f"Profondeur de délégation maximale atteinte ({MAX_DELEGATION_DEPTH})."}

        from src.router.agent_dispatcher import AgentDispatcher

        sous_contexte = self.derive(agent_id)
        sous_contexte.delegation_depth = self.delegation_depth + 1
        sous_contexte.options = {
            **self.options,
            "delegation_chain": [*chaine, self.agent_id],
            "delegated_by": self.agent_id,
        }

        try:
            resultat = AgentDispatcher().dispatch_by_id(
                agent_id, task if task is not None else self.request, sous_contexte
            )
        except Exception as erreur:
            # Une délégation qui échoue ne doit pas emporter l'agent appelant :
            # il doit pouvoir rapporter qu'il n'a pas obtenu l'aide demandée.
            self._logger.warning("Délégation à « %s » impossible : %s", agent_id, erreur)
            return {"status": "error", "agent": agent_id, "error": str(erreur)}

        self.post("delegation", {"agent": agent_id, "status": resultat.get("status")})
        return resultat

    # ------------------------------------------------------------------
    # Moteur de mémoire
    # ------------------------------------------------------------------
    def remember(
        self,
        content: Any,
        memory_type: str = "agent_shared",
        tags: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Enregistre une information en mémoire.

        Args:
            content: Contenu à mémoriser
            memory_type: Type de mémoire (`short_term`, `long_term`, `agent_shared`, ...)
            tags: Étiquettes de catégorisation

        Returns:
            L'identifiant de la mémoire créée, ou None si le moteur est absent
        """
        memory = self.registry.try_get("memory")
        if memory is None:
            self._logger.debug("Moteur de mémoire indisponible, mémorisation ignorée")
            return None

        try:
            from ..memory_engine.types import MemoryItem, MemoryType

            item = MemoryItem(
                content=content,
                memory_type=self._to_memory_type(MemoryType, memory_type),
                user_id=self.user_id,
                session_id=self.session_id,
                agent_id=self.agent_id,
                tags=tags or [],
            )
            return memory.save_memory(item)
        except Exception as error:
            self._logger.warning(f"Mémorisation impossible: {error}")
            return None

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Recherche dans la mémoire de la session courante.

        Args:
            query: Termes recherchés
            limit: Nombre maximum de souvenirs retournés

        Returns:
            Liste de souvenirs, du plus pertinent au moins pertinent
        """
        memory = self.registry.try_get("memory")
        if memory is None:
            return []

        try:
            results = memory.search_memory(query=query, session_id=self.session_id, limit=limit)
            return [
                {
                    "id": item.id,
                    "content": item.content,
                    "agent_id": item.agent_id,
                    "tags": item.tags,
                    "score": score,
                }
                for item, score in results
            ]
        except Exception as error:
            self._logger.warning(f"Recherche en mémoire impossible: {error}")
            return []

    # ------------------------------------------------------------------
    # Moteur de connaissances
    # ------------------------------------------------------------------
    def search_knowledge(self, query: str, limit: int = 5,
                         role: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Interroge la base de connaissances.

        Args:
            query: Termes recherchés
            limit: Nombre maximum de connaissances retournées
            role: Rôle de l'appelant (VOLET 05, chapitre 07). Sans rôle, un agent
                ne lit que les connaissances publiques.

        Returns:
            Liste de connaissances pertinentes
        """
        knowledge = self.registry.try_get("knowledge")
        if knowledge is None:
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "search_knowledge",
                status=AuditStatus.UNAVAILABLE,
                metadata={"query": query[:500], "reason": "Moteur de connaissances indisponible"},
            )
            return []

        try:
            # `role` n'est transmis que s'il est demandé : un moteur de
            # connaissances antérieur au chapitre 07 n'accepte pas ce paramètre,
            # et un agent ne doit pas échouer parce qu'un composant est plus ancien
            # que lui. Sans rôle, la lecture reste publique de toute façon.
            items = (knowledge.search_knowledge(query, limit=limit, role=role) if role
                     else knowledge.search_knowledge(query, limit=limit))
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "search_knowledge",
                status=AuditStatus.SUCCESS,
                confidence=max((item.confidence for item in items), default=0.0),
                knowledge_sources=list(items),
                metadata={"query": query[:500], "results_count": len(items)},
            )
            return [
                {
                    "id": item.id,
                    "content": item.content,
                    "confidence": item.confidence,
                    "tags": item.tags,
                    # Un agent qui cite une connaissance doit pouvoir dire d'où
                    # elle vient et si elle est approuvée (chapitre 08, étape 4).
                    # None quand le moteur ne porte pas l'information : mieux vaut
                    # « inconnu » qu'un domaine ou un statut supposé.
                    "domain": getattr(getattr(item, "domain", None), "value", None),
                    "status": getattr(getattr(item, "status", None), "value", None),
                }
                for item in items
            ]
        except Exception as error:
            self._logger.warning(f"Recherche de connaissances impossible: {error}")
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "search_knowledge",
                status=AuditStatus.FAILURE,
                detail=str(error),
                metadata={"query": query[:500]},
            )
            return []

    def add_knowledge(self, content: str, tags: Optional[List[str]] = None,
                      confidence: float = 0.5) -> Optional[str]:
        """
        Ajoute une connaissance à la base.

        Args:
            content: Contenu de la connaissance
            tags: Étiquettes de catégorisation
            confidence: Niveau de confiance entre 0.0 et 1.0

        Returns:
            L'identifiant de la connaissance créée, ou None si le moteur est absent
        """
        knowledge = self.registry.try_get("knowledge")
        if knowledge is None:
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "add_knowledge",
                status=AuditStatus.UNAVAILABLE,
                metadata={"content_preview": content[:200], "reason": "Moteur de connaissances indisponible"},
            )
            return None

        try:
            from ..knowledge_engine.types import KnowledgeItem, KnowledgeSource

            item = KnowledgeItem(
                content=content,
                tags=tags or [],
                confidence=confidence,
                source=KnowledgeSource(id=self.agent_id, type="agent", location=self.agent_id),
            )
            item_id = knowledge.add_knowledge(item)
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "add_knowledge",
                status=AuditStatus.SUCCESS if item_id else AuditStatus.FAILURE,
                confidence=confidence,
                knowledge_sources=[item],
                metadata={"knowledge_id": item_id, "content_preview": content[:200]},
            )
            return item_id
        except Exception as error:
            self._logger.warning(f"Ajout de connaissance impossible: {error}")
            self.record_audit(
                AuditEventType.KNOWLEDGE,
                "add_knowledge",
                status=AuditStatus.FAILURE,
                detail=str(error),
                metadata={"content_preview": content[:200]},
            )
            return None

    # ------------------------------------------------------------------
    # Moteur documentaire
    # ------------------------------------------------------------------
    def load_document(self, path: str) -> Optional[Any]:
        """
        Charge un document depuis un fichier.

        Args:
            path: Chemin du fichier

        Returns:
            Le `DocumentItem` chargé, ou None en cas d'échec
        """
        document_engine = self.registry.try_get("document")
        if document_engine is None:
            return None

        try:
            return document_engine.load_document(path)
        except Exception as error:
            self._logger.warning(f"Chargement du document '{path}' impossible: {error}")
            return None

    def analyze_document(self, path: str) -> Dict[str, Any]:
        """
        Charge un document et en produit une analyse complète.

        Args:
            path: Chemin du fichier

        Returns:
            Résumé, métadonnées, tableaux et validation du document.
            Dictionnaire vide si le document n'a pas pu être traité.
        """
        document_engine = self.registry.try_get("document")
        if document_engine is None:
            return {}

        try:
            document = document_engine.load_document(path)
            document_engine.index_document(document.document_id)
            metadata = document_engine.extract_metadata(document.document_id)
            is_valid, errors = document_engine.validate_document(document.document_id)

            return {
                "document_id": document.document_id,
                "title": document.title,
                "type": document.document_type.value,
                "summary": document_engine.summarize_document(document.document_id),
                "word_count": metadata.word_count,
                "language": metadata.language,
                "tables": document_engine.extract_tables(document.document_id),
                "valid": is_valid,
                "validation_errors": errors,
            }
        except Exception as error:
            self._logger.warning(f"Analyse du document '{path}' impossible: {error}")
            return {}

    # ------------------------------------------------------------------
    # Moteur visuel
    # ------------------------------------------------------------------
    def analyze_image(self, path: str, **kwargs) -> Dict[str, Any]:
        """
        Analyse une image.

        Args:
            path: Chemin du fichier image
            **kwargs: Options transmises au moteur visuel

        Returns:
            Résultat de l'analyse, dictionnaire vide en cas d'échec
        """
        vision = self.registry.try_get("vision")
        if vision is None:
            return {}

        try:
            image_item = vision.load_image(path)
            return vision.analyze_image(image_item, **kwargs)
        except Exception as error:
            self._logger.warning(f"Analyse de l'image '{path}' impossible: {error}")
            return {}

    # ------------------------------------------------------------------
    # Moteur d'outils
    # ------------------------------------------------------------------
    def use_tool(self, tool_id: str, *args, **kwargs) -> Dict[str, Any]:
        """
        Exécute un outil du moteur d'outils.

        Args:
            tool_id: Identifiant de l'outil
            *args: Arguments positionnels de l'outil
            **kwargs: Arguments nommés de l'outil

        Returns:
            Dictionnaire `{"status", "tool", "result"}` ou `{"status": "error", "error"}`.
            L'échec d'un outil est une donnée, pas une exception : un agent doit
            pouvoir continuer sans lui.
        """
        tool_engine = self.registry.try_get("tool")
        if tool_engine is None:
            self.record_audit(
                AuditEventType.TOOL,
                f"tool:{tool_id}",
                status=AuditStatus.UNAVAILABLE,
                detail="Moteur d'outils indisponible",
                metadata={"arguments": self._serialize_args(args, kwargs)},
            )
            return {"status": "error", "tool": tool_id, "error": "Moteur d'outils indisponible"}

        if not tool_engine.is_tool_enabled(tool_id):
            self.record_audit(
                AuditEventType.TOOL,
                f"tool:{tool_id}",
                status=AuditStatus.SKIPPED,
                detail=f"Outil '{tool_id}' désactivé ou inconnu",
                metadata={"arguments": self._serialize_args(args, kwargs)},
            )
            return {"status": "error", "tool": tool_id, "error": f"Outil '{tool_id}' désactivé ou inconnu"}

        started = time.time()
        try:
            result = tool_engine.execute_tool(tool_id, *args, **kwargs)
            self.record_audit(
                AuditEventType.TOOL,
                f"tool:{tool_id}",
                status=AuditStatus.SUCCESS,
                execution_time_seconds=time.time() - started,
                metadata={"arguments": self._serialize_args(args, kwargs)},
            )
            return {"status": "success", "tool": tool_id, "result": result}
        except Exception as error:
            self._logger.warning(f"Exécution de l'outil '{tool_id}' impossible: {error}")
            self.record_audit(
                AuditEventType.TOOL,
                f"tool:{tool_id}",
                status=AuditStatus.FAILURE,
                execution_time_seconds=time.time() - started,
                detail=str(error),
                metadata={"arguments": self._serialize_args(args, kwargs)},
            )
            return {"status": "error", "tool": tool_id, "error": str(error)}

    def search_web(self, query: str, max_results: int = 5, search_type: str = "web") -> List[Dict[str, Any]]:
        """
        Effectue une recherche web via le moteur d'outils.

        Args:
            query: Requête de recherche
            max_results: Nombre maximum de résultats
            search_type: `web`, `news`, `images` ou `videos`

        Returns:
            Liste de résultats, vide si la recherche a échoué
        """
        outcome = self.use_tool("web_search", query, max_results=max_results, search_type=search_type)
        if outcome.get("status") != "success":
            return []

        results = outcome.get("result") or []
        return results if isinstance(results, list) else []

    # ------------------------------------------------------------------
    # Moteur de modèles
    # ------------------------------------------------------------------
    def generate(self, prompt: str, task_requirements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Demande une génération de texte au moteur de modèles.

        Args:
            prompt: Invite envoyée au modèle
            task_requirements: Contraintes de sélection du modèle

        Returns:
            Dictionnaire `{"status", "text", "model_id"}`. Le statut vaut
            `unavailable` quand aucun modèle n'est enregistré : l'appelant doit
            alors se rabattre sur un traitement déterministe plutôt que de
            présenter une réponse inventée.
        """
        model_engine = self.registry.try_get("model")
        if model_engine is None:
            self.record_audit(
                AuditEventType.GENERATION,
                "generate",
                status=AuditStatus.UNAVAILABLE,
                metadata={"prompt_preview": self._clip(prompt, 200), "reason": "Moteur de modèles indisponible"},
            )
            return {"status": "unavailable", "text": "", "reason": "Moteur de modèles indisponible"}

        requirements = task_requirements or {}
        started = time.time()
        model_id: Optional[str] = None
        try:
            model_item = model_engine.select_model_for_task(requirements)
            if model_item is None:
                self.record_audit(
                    AuditEventType.GENERATION,
                    "generate",
                    status=AuditStatus.UNAVAILABLE,
                    metadata={"prompt_preview": self._clip(prompt, 200), "reason": "Aucun modèle enregistré ne correspond à la tâche"},
                )
                return {
                    "status": "unavailable",
                    "text": "",
                    "reason": "Aucun modèle enregistré ne correspond à la tâche",
                }

            model_id = model_item.model_id
            text = self._run_async(model_engine.generate_text(model_item, prompt))
            self.record_audit(
                AuditEventType.GENERATION,
                "generate",
                status=AuditStatus.SUCCESS,
                model_id=model_id,
                execution_time_seconds=time.time() - started,
                metadata={"prompt_preview": self._clip(prompt, 200), "output_length": len(text)},
            )
            return {"status": "success", "text": text, "model_id": model_id}
        except Exception as error:
            # Un fournisseur indisponible est un état attendu, pas une panne :
            # l'agent doit pouvoir le distinguer d'une vraie erreur pour
            # retomber sur un traitement déterministe
            if type(error).__name__ == "ProviderUnavailableError":
                self.record_audit(
                    AuditEventType.GENERATION,
                    "generate",
                    status=AuditStatus.UNAVAILABLE,
                    model_id=model_id,
                    execution_time_seconds=time.time() - started,
                    detail=str(error),
                    metadata={"prompt_preview": self._clip(prompt, 200)},
                )
                return {"status": "unavailable", "text": "", "reason": str(error)}

            self._logger.warning(f"Génération de texte impossible: {error}")
            self.record_audit(
                AuditEventType.GENERATION,
                "generate",
                status=AuditStatus.FAILURE,
                model_id=model_id,
                execution_time_seconds=time.time() - started,
                detail=str(error),
                metadata={"prompt_preview": self._clip(prompt, 200)},
            )
            return {"status": "error", "text": "", "reason": str(error)}

    # ------------------------------------------------------------------
    # Moteur d'audit
    # ------------------------------------------------------------------
    @property
    def audit(self) -> Optional[Any]:
        """
        Retourne le moteur d'audit du registre, ou None s'il est absent.

        L'accès au moteur ne lève jamais d'exception : une indisponibilité est
        simplement signalée pour que la consignation reste facultative.
        """
        try:
            return self.registry.try_get("audit")
        except Exception as error:
            self._logger.warning(f"Accès au moteur d'audit impossible: {error}")
            return None

    def record_audit(
        self,
        event_type: Any,
        action: str,
        status: Any = "success",
        confidence: Optional[float] = None,
        knowledge_sources: Optional[List[Any]] = None,
        model_id: Optional[str] = None,
        execution_time_seconds: Optional[float] = None,
        detail: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Consigne un événement d'audit pour l'action courante.

        La consignation est facultative : son échec ou l'absence du moteur
        d'audit ne modifie jamais le déroulement du traitement.

        Args:
            event_type: Type d'événement (chaîne ou `AuditEventType`)
            action: Nom de l'action consignée
            status: Statut d'exécution (chaîne ou `AuditStatus`)
            confidence: Niveau de confiance de la réponse (0.0 à 1.0)
            knowledge_sources: Sources de connaissance mobilisées
            model_id: Modèle utilisé pour produire la réponse
            execution_time_seconds: Durée d'exécution de l'action
            detail: Message de détail ou d'erreur
            metadata: Métadonnées libres supplémentaires

        Returns:
            L'identifiant de l'événement créé, ou None en cas d'échec
        """
        audit = self.audit
        if audit is None:
            return None

        try:
            event = AuditEvent(
                event_type=self._normalize_event_type(event_type),
                action=action,
                agent_id=self.agent_id,
                request_id=self.request_id,
                user_request=self._clip(self.request_text(), 2000),
                model_id=model_id,
                confidence=confidence,
                knowledge_sources=self._normalize_sources(knowledge_sources),
                status=self._normalize_status(status),
                execution_time_seconds=execution_time_seconds,
                detail=detail,
                metadata=dict(metadata or {}),
            )
            return audit.record(event)
        except Exception as error:
            self._logger.warning(f"Consignation de l'audit impossible: {error}")
            return None

    # ------------------------------------------------------------------
    # Moteur d'approbation humaine (ADR-006)
    # ------------------------------------------------------------------
    @property
    def approval(self) -> Optional[Any]:
        """
        Retourne le moteur d'approbation du registre, ou None s'il est absent.

        L'accès au moteur ne lève jamais d'exception : une indisponibilité est
        simplement signalée pour que le portillon reste facultatif.
        """
        try:
            return self.registry.try_get("approval")
        except Exception as error:
            self._logger.warning(f"Accès au moteur d'approbation impossible: {error}")
            return None

    def submit_approval(
        self,
        action: str,
        description: Optional[str] = None,
        confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Soumet une action au portillon d'approbation humaine.

        La demande est créée dans l'état `pending` puis consignée dans l'audit
        avec le statut `requires_approval`, afin que la soumission soit
        traçable. Le portillon est facultatif : son indisponibilité retourne
        None sans lever d'exception.

        Args:
            action: Nom de l'action à faire valider
            description: Explication destinée à l'opérateur humain
            confidence: Niveau de confiance de l'agent dans l'action
            metadata: Métadonnées libres portées par la demande

        Returns:
            L'identifiant de la demande, ou None en cas d'échec
        """
        approval = self.approval
        if approval is None:
            self._logger.warning("Moteur d'approbation indisponible, soumission ignorée")
            return None

        try:
            request = ApprovalRequest(
                agent_id=self.agent_id,
                request_id=self.request_id,
                action=action,
                description=description,
                confidence=confidence,
                metadata=dict(metadata or {}),
            )
            request_id = approval.submit(request)
            if request_id is None:
                self.record_audit(
                    AuditEventType.REQUEST,
                    f"approval:{action}",
                    status=AuditStatus.FAILURE,
                    detail="Le moteur d'approbation a refusé la soumission",
                    metadata={"action": action},
                )
                return None
            self.record_audit(
                AuditEventType.REQUEST,
                f"approval:{action}",
                status=AuditStatus.REQUIRES_APPROVAL,
                confidence=confidence,
                metadata={"approval_request_id": request_id},
            )
            return request_id
        except Exception as error:
            self._logger.warning(f"Soumission d'approbation impossible: {error}")
            return None

    def approve_approval(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """
        Approuve une demande d'approbation en attente.

        La décision et son auteur sont consignés dans l'audit pour la
        traçabilité (ADR-006).
        """
        return self._decide_approval("approve", request_id, reason, decided_by)

    def reject_approval(
        self,
        request_id: str,
        reason: Optional[str] = None,
        decided_by: Optional[str] = None,
    ) -> bool:
        """
        Refuse une demande d'approbation en attente.

        La décision et son auteur sont consignés dans l'audit pour la
        traçabilité (ADR-006).
        """
        return self._decide_approval("reject", request_id, reason, decided_by)

    def _decide_approval(
        self,
        decision: str,
        request_id: str,
        reason: Optional[str],
        decided_by: Optional[str],
    ) -> bool:
        """
        Applique une décision humaine à une demande d'approbation.

        La décision est consignée dans l'audit, avec son motif et son auteur,
        quel que soit le résultat. Ne lève jamais d'exception.
        """
        approval = self.approval
        if approval is None:
            return False

        try:
            if decision == "approve":
                decided = approval.approve(request_id, reason=reason, decided_by=decided_by)
            else:
                decided = approval.reject(request_id, reason=reason, decided_by=decided_by)
            self.record_audit(
                AuditEventType.REQUEST,
                f"approval:{decision}:{request_id}",
                status=AuditStatus.SUCCESS if decided else AuditStatus.FAILURE,
                detail=reason,
                metadata={"decided_by": decided_by},
            )
            return decided
        except Exception as error:
            self._logger.warning(f"Décision d'approbation impossible: {error}")
            return False

    @staticmethod
    def _normalize_event_type(value: Any) -> AuditEventType:
        """Convertit une valeur en `AuditEventType`, sans jamais lever d'exception."""
        if isinstance(value, AuditEventType):
            return value
        if isinstance(value, str):
            try:
                return AuditEventType(value)
            except ValueError:
                pass
            try:
                return AuditEventType[value.upper()]
            except KeyError:
                pass
        return AuditEventType.REQUEST

    @staticmethod
    def _normalize_status(value: Any) -> AuditStatus:
        """Convertit une valeur en `AuditStatus`, sans jamais lever d'exception."""
        if isinstance(value, AuditStatus):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized == "error":
                return AuditStatus.FAILURE
            try:
                return AuditStatus(normalized)
            except ValueError:
                pass
            try:
                return AuditStatus[normalized.upper()]
            except KeyError:
                pass
        return AuditStatus.SUCCESS

    @classmethod
    def _normalize_sources(cls, sources: Optional[List[Any]]) -> List[Dict[str, Any]]:
        """Sérialise une liste de sources de connaissance en dictionnaires légers."""
        if not sources:
            return []
        result = []
        for source in sources:
            if not source:
                continue
            serialized = cls._source_to_dict(source)
            if serialized:
                result.append(serialized)
        return result

    @classmethod
    def _source_to_dict(cls, source: Any) -> Dict[str, Any]:
        """
        Convertit une source de connaissance en dictionnaire.

        Accepte un dictionnaire, un objet avec `to_dict()` (dont les
        `KnowledgeSourceRef`), ou un objet plat (`KnowledgeItem` /
        `KnowledgeSource`) dont les attributs sont collectés.
        """
        if isinstance(source, dict):
            return {key: value for key, value in source.items() if value is not None}
        to_dict = getattr(source, "to_dict", None)
        if callable(to_dict):
            payload = to_dict()
            if isinstance(payload, dict):
                return {key: value for key, value in payload.items() if value is not None}
        result: Dict[str, Any] = {}
        # Une KnowledgeItem transporte sa source dans `.source` : on la collecte d'abord
        nested = getattr(source, "source", None)
        if nested is not None:
            result.update(cls._source_to_dict(nested))
        for key in ("id", "title", "author", "url", "citation", "confidence"):
            value = getattr(source, key, None)
            if value is not None:
                result[key] = value
        priority = getattr(source, "priority", None)
        if priority is not None:
            result["priority"] = priority.value if hasattr(priority, "value") else str(priority)
        return result

    @staticmethod
    def _clip(text: str, limit: int = 200) -> str:
        """Tronque un texte à une longueur maximale, en signalant la coupure."""
        if text is None:
            return ""
        value = str(text)
        if len(value) <= limit:
            return value
        return value[:limit] + "..."

    @staticmethod
    def _serialize_args(args: tuple, kwargs: dict) -> str:
        """
        Sérialise des arguments d'outil pour les métadonnées d'audit.

        Les valeurs sensibles (mots de passe, jetons, clés API, ...) sont
        remplacées par ``***`` afin de ne jamais consigner un secret.
        """
        parts = []
        for value in list(args)[:5]:
            parts.append(AgentContext._clip(str(value), 200))
        for key, value in kwargs.items():
            key_lower = key.lower()
            if any(term in key_lower for term in AgentContext._SENSITIVE_ARG_NAMES):
                parts.append(f"{key}=***")
            else:
                parts.append(f"{key}={AgentContext._clip(str(value), 200)}")
        return AgentContext._clip(", ".join(parts), 1000)

    # Noms d'arguments jugés sensibles : leur valeur n'est jamais consignée
    _SENSITIVE_ARG_NAMES = ("password", "token", "secret", "api_key", "apikey", "key", "authorization", "auth")

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def _run_async(self, coroutine) -> Any:
        """
        Exécute une coroutine depuis du code synchrone.

        Les agents s'exécutent dans les threads du Router Engine, où aucune
        boucle d'événements ne tourne : `asyncio.run` convient. Si une boucle
        existe déjà, la coroutine est exécutée dans un thread dédié pour ne pas
        entrer en conflit avec elle.
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(asyncio.run, coroutine).result()

    @staticmethod
    def _to_memory_type(memory_type_enum, value: str):
        """Convertit un nom de type de mémoire en énumération, avec repli sûr."""
        try:
            return memory_type_enum(value)
        except ValueError:
            return memory_type_enum.AGENT_SHARED

    @classmethod
    def _extract_text(cls, value: Any) -> str:
        """Extrait le texte utile d'une entrée qui peut être un résultat d'agent."""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # Un résultat d'agent transporte son texte dans l'une de ces clés
            for key in ("text", "summary", "result", "content"):
                if key in value:
                    return cls._extract_text(value[key])
            return str(value)
        if isinstance(value, list):
            return ' '.join(cls._extract_text(element) for element in value)
        return str(value) if value is not None else ""
