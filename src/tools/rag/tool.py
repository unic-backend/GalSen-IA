"""
Outil RAG (Retrieval-Augmented Generation) pour GalSen IA.

Fournit une interface pour stocker, rechercher et récupérer des connaissances
en utilisant le moteur de connaissances (Knowledge Engine).
"""

import logging
import datetime
from typing import Any, Dict, List, Optional

from src.tool.base import BaseTool
from src.integration.engine_registry import get_shared_registry
from src.knowledge_engine.types import (
    KnowledgeType,
    ContentType,
    Language,
    KnowledgeSource,
    KnowledgeItem,
    SourceCategory,
    KnowledgePriority,
    KnowledgeDomain,
    KnowledgeSensitivity,
    KnowledgeStatus,
)

logger = logging.getLogger(__name__)


class RAGTool(BaseTool):
    """
    Outil d'accès au moteur de connaissances pour le modèle RAG de GalSen IA.

    Opérations disponibles : `add` (ajouter une connaissance),
    `get` (récupérer par ID), `search` (recherche par texte),
    `retrieve_for_prompt` (RAG : récupérer pour enrichir un prompt),
    `update` (mettre à jour), `delete` (supprimer),
    `list` (lister avec filtres), `stats` (statistiques).

    Exemple:
        tool.execute("add", {"content": "Le ciel est bleu.", "knowledge_type": "fact"})
        tool.execute("get", "knowledge-id")
        tool.execute("search", "bleu", limit=5)
    """

    def __init__(self, config: dict = None):
        """
        Initialise l'outil RAG.

        Args:
            config: Configuration (actuellement inutilisée, réservée pour
                    de futures extensions).
        """
        super().__init__(config)
        self._knowledge_manager = None
        logger.debug("RAGTool initialisé.")

    def _get_knowledge_manager(self):
        """
        Retourne le gestionnaire de connaissances partagé de la plateforme.

        L'outil utilise le registre commun plutôt que d'instancier son propre
        gestionnaire : cela garantit que toutes les parties du système
        partagent la même base de connaissances.
        """
        if self._knowledge_manager is None:
            registry = get_shared_registry()
            self._knowledge_manager = registry.knowledge
        return self._knowledge_manager

    # ------------------------------------------------------------------
    # Utilitaires internes de conversion et sérialisation
    # ------------------------------------------------------------------
    def _convert_classification(self, item_dict: Dict[str, Any]) -> None:
        """
        Reconvertit domaine, sensibilité et statut en énumérations, sur place.

        Les sorties de l'outil sérialisent ces champs en chaînes ; un appelant
        qui relit une connaissance, la modifie et la renvoie doit retrouver un
        objet valide. Sans cette conversion, la connaissance repart avec des
        chaînes là où le moteur attend des énumérations, et disparaît
        silencieusement des résultats filtrés.
        """
        conversions = (
            ("domain", KnowledgeDomain, "Domaine de connaissance invalide"),
            ("sensitivity", KnowledgeSensitivity, "Sensibilité invalide"),
            ("status", KnowledgeStatus, "Statut invalide"),
        )
        for champ, enumeration, message in conversions:
            valeur = item_dict.get(champ)
            if isinstance(valeur, str):
                try:
                    item_dict[champ] = enumeration(valeur.strip().lower())
                except ValueError:
                    raise ValueError(f"{message}: {valeur}")

    def _convert_priority(self, value: Any) -> KnowledgePriority:
        """
        Convertit une priorité en KnowledgePriority.

        Accepte un enum, une chaîne ("P1".."P4") ou un entier (1..4).

        Args:
            value: La priorité à convertir.

        Returns:
            Le KnowledgePriority correspondant.

        Raises:
            ValueError: Si la valeur n'est pas une priorité valide.
        """
        if isinstance(value, KnowledgePriority):
            return value
        if isinstance(value, str):
            try:
                return KnowledgePriority[value.upper()]
            except KeyError:
                raise ValueError(
                    f"Priorité invalide: {value}. Utilisez P1, P2, P3 ou P4."
                )
        if isinstance(value, int):
            try:
                return KnowledgePriority(value)
            except ValueError:
                raise ValueError(
                    f"Priorité invalide: {value}. Utilisez P1, P2, P3 ou P4."
                )
        raise ValueError(f"Priorité invalide: {value!r}")

    def _build_source(self, src_dict: Dict[str, Any]) -> KnowledgeSource:
        """
        Construit une KnowledgeSource depuis un dictionnaire.

        Convertit les champs enum (source_category) et les dates
        (retrieved_at) vers les types appropriés.

        Args:
            src_dict: Dictionnaire décrivant la source.

        Returns:
            L'objet KnowledgeSource correspondant.
        """
        source_category = None
        if src_dict.get("source_category") is not None:
            sc = src_dict["source_category"]
            if isinstance(sc, SourceCategory):
                source_category = sc
            elif isinstance(sc, str):
                try:
                    source_category = SourceCategory[sc.upper()]
                except KeyError:
                    raise ValueError(f"Catégorie de source invalide: {sc}")
            else:
                raise ValueError(f"Catégorie de source invalide: {sc!r}")

        retrieved_at = src_dict.get("retrieved_at")
        if retrieved_at is not None and isinstance(retrieved_at, str):
            try:
                retrieved_at = datetime.datetime.fromisoformat(retrieved_at)
            except ValueError:
                raise ValueError(f"Date de récupération invalide: {retrieved_at}")

        return KnowledgeSource(
            id=src_dict.get("id", "unknown"),
            type=src_dict.get("type", "unknown"),
            location=src_dict.get("location", "unknown"),
            accessed_at=src_dict.get("accessed_at"),
            hash=src_dict.get("hash"),
            source_category=source_category,
            title=src_dict.get("title"),
            author=src_dict.get("author"),
            url=src_dict.get("url"),
            citation=src_dict.get("citation"),
            retrieved_at=retrieved_at,
        )

    def _serialize_item(self, item: KnowledgeItem, iso_dates: bool = False) -> Dict[str, Any]:
        """
        Sérialise une connaissance en dictionnaire pour les sorties de l'outil.

        Les enums sont convertis en chaînes et la priorité en entier pour une
        meilleure lisibilité JSON.

        Args:
            item: La connaissance à sérialiser.
            iso_dates: Si True, les dates sont converties en chaînes ISO 8601
                       (sinon elles restent des objets datetime).

        Returns:
            Dictionnaire représentant la connaissance.
        """
        created_at = item.created_at.isoformat() if iso_dates and item.created_at else item.created_at
        updated_at = item.updated_at.isoformat() if iso_dates and item.updated_at else item.updated_at
        accessed_at = (
            item.source.accessed_at.isoformat()
            if iso_dates and item.source.accessed_at
            else item.source.accessed_at
        )
        retrieved_at = (
            item.source.retrieved_at.isoformat()
            if iso_dates and item.source.retrieved_at
            else item.source.retrieved_at
        )
        source = item.source
        return {
            "id": item.id,
            "content": item.content,
            "summary": item.summary,
            "knowledge_type": item.knowledge_type.value
            if hasattr(item.knowledge_type, "value")
            else str(item.knowledge_type),
            "content_type": item.content_type.value
            if hasattr(item.content_type, "value")
            else str(item.content_type),
            "language": item.language.value
            if hasattr(item.language, "value")
            else str(item.language),
            # Classification et cycle de vie (VOLET 05, chapitres 02 et 03) : sans
            # eux, l'appelant reçoit un contenu sans savoir s'il est approuvé ni
            # à qui il appartient.
            "domain": item.domain.value if hasattr(item.domain, "value") else str(item.domain),
            "sensitivity": item.sensitivity.value
            if hasattr(item.sensitivity, "value")
            else str(item.sensitivity),
            "status": item.status.value if hasattr(item.status, "value") else str(item.status),
            "tags": item.tags.copy(),
            "categories": item.categories.copy(),
            "source": {
                "id": source.id,
                "type": source.type,
                "location": source.location,
                "accessed_at": accessed_at,
                "hash": source.hash,
                "source_category": source.source_category.value
                if source.source_category is not None
                else None,
                "title": source.title,
                "author": source.author,
                "url": source.url,
                "citation": source.citation,
                "retrieved_at": retrieved_at,
            },
            "confidence": item.confidence,
            "priority": item.priority.value
            if hasattr(item.priority, "value")
            else int(item.priority),
            "version": item.version,
            "created_at": created_at,
            "updated_at": updated_at,
            "metadata": item.metadata.copy(),
            "relations": item.relations.copy(),
        }

    # ------------------------------------------------------------------
    # Opérations
    # ------------------------------------------------------------------
    def _op_add(self, item_dict: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Ajoute une connaissance à la base.

        Args:
            item_dict: Dictionnaire représentant la connaissance à ajouter.
                       Les champs possibles sont ceux de KnowledgeItem :
                       content, summary, knowledge_type, content_type,
                       language, tags, categories, source, confidence,
                       priority, metadata, etc.
                       Le champ 'priority' accepte "P1".."P4" ou un entier.
                       Le champ 'source' accepte un dictionnaire avec les
                       champs de KnowledgeSource (dont source_category,
                       citation, retrieved_at, etc.).
                       Le champ 'id' est optionnel ; s'il est absent,
                       un ID sera généré automatiquement.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire contenant l'ID de la connaissance ajoutée :
                {"id": "<knowledge-id>"}
        """
        # Convertir les champs enum depuis les chaînes si nécessaires
        if "knowledge_type" in item_dict and isinstance(item_dict["knowledge_type"], str):
            try:
                item_dict["knowledge_type"] = KnowledgeType[
                    item_dict["knowledge_type"].upper()
                ]
            except KeyError:
                raise ValueError(
                    f"Type de connaissance invalide: {item_dict['knowledge_type']}"
                )
        if "content_type" in item_dict and isinstance(item_dict["content_type"], str):
            try:
                item_dict["content_type"] = ContentType[
                    item_dict["content_type"].upper()
                ]
            except KeyError:
                raise ValueError(
                    f"Type de contenu invalide: {item_dict['content_type']}"
                )
        if "language" in item_dict and isinstance(item_dict["language"], str):
            try:
                item_dict["language"] = Language[item_dict["language"].upper()]
            except KeyError:
                raise ValueError(f"Langue invalide: {item_dict['language']}")

        # Convertir la priorité depuis une chaîne ou un entier
        if "priority" in item_dict and not isinstance(item_dict["priority"], KnowledgePriority):
            item_dict["priority"] = self._convert_priority(item_dict["priority"])

        # Domaine, sensibilité et statut reviennent en chaînes des sorties de l'outil.
        self._convert_classification(item_dict)

        # Gestion de la source si fournie sous forme de dictionnaire
        if "source" in item_dict and isinstance(item_dict["source"], dict):
            item_dict["source"] = self._build_source(item_dict["source"])

        # Si la priorité n'est pas fournie mais que la source a une catégorie,
        # déduire la priorité à partir de la catégorie de source (hiérarchie P1-P4)
        if "priority" not in item_dict and isinstance(item_dict.get("source"), KnowledgeSource):
            item_dict["priority"] = KnowledgePriority.from_source_category(
                item_dict["source"].source_category
            )

        # Créer l'objet KnowledgeItem
        item = KnowledgeItem(**item_dict)

        # Sauvegarder via le gestionnaire de connaissances
        kid = self._get_knowledge_manager().add_knowledge(item)
        logger.info(f"Knowledge added via RAG tool with id: {kid}")
        return {"id": kid}

    def _op_get(self, knowledge_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Récupère une connaissance par son ID.

        Args:
            knowledge_id: L'ID de la connaissance à récupérer.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire représentant la connaissance, ou None si non trouvée.
            Les enums sont convertis en chaînes pour une meilleure lisibilité JSON.
        """
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            raise ValueError("L'ID de la connaissance doit être une chaîne non vide")

        item = self._get_knowledge_manager().get_knowledge(knowledge_id)
        if item is None:
            return None

        # Convertir en dictionnaire pour la sérialisation
        item_dict = self._serialize_item(item, iso_dates=False)
        logger.debug(f"Knowledge retrieved via RAG tool: {knowledge_id}")
        return item_dict

    def _op_search(
        self,
        query: str,
        knowledge_type: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        role: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Recherche des connaissances par texte avec filtres optionnels.

        Args:
            query: La chaîne de recherche.
            knowledge_type: Filtrer par type de connaissance (ex. "FACT").
            content_type: Filtrer par type de contenu (ex. "TEXT").
            tags: Liste de tags (tous doivent être présents).
            limit: Nombre maximum de résultats à retourner (défaut: 10).
            role: Rôle de l'appelant (VOLET 05, chapitre 07). Sans rôle, seules
                les connaissances publiques sont retournées.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Liste de dictionnaires représentant les connaissances trouvées,
            chacun contenant les champs de la connaissance ainsi qu'un
            champ '_score' : le score réel calculé par l'indexeur (proportion
            des termes de la requête présents dans le document).
        """
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La requête de recherche doit être une chaîne non vide")

        # Au niveau du gestionnaire de connaissances, nous n'avons pas de filtrage
        # par type ou tags directement dans search_knowledge ; nous allons
        # récupérer tous les résultats puis filtrer en post-traitement.
        # Le score vient de l'indexeur ; le déduire du rang produirait un
        # classement faux, que rien ne distinguerait ensuite d'un vrai.
        scored_results: List[tuple] = self._get_knowledge_manager().search_knowledge_with_scores(
            query, limit=limit * 3, role=role
        )  # récupérer davantage pour permettre le filtrage

        # Préparer les filtres
        kt_enum: Optional[KnowledgeType] = None
        if knowledge_type is not None:
            if isinstance(knowledge_type, str):
                try:
                    kt_enum = KnowledgeType[knowledge_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de connaissance invalide pour la recherche: {knowledge_type}")
            else:
                kt_enum = knowledge_type

        ct_enum: Optional[ContentType] = None
        if content_type is not None:
            if isinstance(content_type, str):
                try:
                    ct_enum = ContentType[content_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de contenu invalide pour la recherche: {content_type}")
            else:
                ct_enum = content_type

        tag_set: set = set(tags) if tags else set()

        filtered: List[tuple] = []
        for k, score in scored_results:
            if kt_enum is not None and k.knowledge_type != kt_enum:
                continue
            if ct_enum is not None and k.content_type != ct_enum:
                continue
            if tag_set and not tag_set.issubset(set(k.tags)):
                continue
            filtered.append((k, score))
            if len(filtered) >= limit:
                break

        # Convertir chaque KnowledgeItem en dictionnaire, avec le score réel
        # calculé par l'indexeur : la proportion des termes de la requête
        # présents dans le document.
        results: List[Dict[str, Any]] = []
        for k, score in filtered:
            k_dict = self._serialize_item(k, iso_dates=True)
            k_dict["_score"] = score
            results.append(k_dict)

        logger.debug(f"Search '{query}' returned {len(results)} results via RAG tool")
        return results

    def _envelopper(self, element: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ajoute à une connaissance sa forme utilisable dans une invite.

        `retrieve_for_prompt` est **le chemin conçu** pour verser du texte
        étranger dans une invite : c'est donc celui où une consigne cachée dans
        un passage atteindrait le modèle comme un ordre. L'enveloppe de
        confiance (VOLET 36, ch. A.1) l'annonce comme une donnée, avec son
        origine, et transporte les soupçons relevés.

        Le champ `content` **reste le contenu brut** : le tronquer ou le
        réécrire ferait perdre au reste de la plateforme — citations, mesures,
        stockage — le texte réel. C'est `prompt_text` qui entre dans une invite,
        et la docstring de l'opération le dit.
        """
        from src.security.trust import TrustLevel, wrap

        enveloppe = wrap(
            element.get("content", ""),
            TrustLevel.RETRIEVED,
            origin=element.get("id") or "connaissance sans identifiant",
        )
        element["prompt_text"] = enveloppe.text
        element["trust_level"] = enveloppe.level.value
        element["injection_flags"] = len(enveloppe.suspicions)
        return element

    def _op_retrieve_for_prompt(
        self,
        prompt: str,
        max_items: int = 5,
        require_reliable: bool = False,
        min_priority: Optional[str] = None,
        min_confidence: Optional[float] = None,
        role: Optional[str] = None,
        **kwargs,
    ):
        """
        Récupère des connaissances pertinentes pour enrichir un prompt (RAG).

        Par défaut, retourne une liste de connaissances (comportement
        historique). Avec require_reliable=True, applique la hiérarchie de
        fiabilité du chapitre 04 de la Constitution : seules les connaissances
        dont la priorité et la confiance sont suffisantes sont retournées,
        dans un dictionnaire détaillé. Si aucune connaissance fiable n'existe,
        GalSen IA doit préférer dire « Je ne sais pas » plutôt que de générer
        une information trompeuse.

        Args:
            prompt: Le prompt pour lequel chercher du contexte.
            max_items: Nombre maximum de connaissances à retourner (défaut: 5).
            require_reliable: Si True, filtre par fiabilité (P1-P4) et retourne
                              un dictionnaire détaillé au lieu d'une liste.
            min_priority: Priorité maximale requise ("P1".."P4") quand
                          require_reliable est True (défaut: P4).
            min_confidence: Seuil de confiance minimal (défaut: 0.5) quand
                            require_reliable est True.
            role: Rôle de l'appelant (VOLET 05, chapitre 07). Sans rôle, seules
                  les connaissances publiques entrent dans le contexte.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Liste de dictionnaires représentant les connaissances pertinentes,
            ou un dictionnaire avec les clés "items", "reliable",

            Chaque élément porte **`prompt_text`** : c'est ce champ, et lui
            seul, qui entre dans une invite. Il annonce le passage comme une
            donnée récupérée, avec son origine, et signale les tournures qui
            s'adressent à un modèle. `content` reste le texte brut, pour les
            citations et les mesures.
            "best_priority", "best_confidence" et "reason" si
            require_reliable est True.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Le prompt doit être une chaîne non vide")

        # Mode par défaut : compatibilité avec le comportement historique
        if not require_reliable:
            raw_results: List[KnowledgeItem] = self._get_knowledge_manager().retrieve_for_prompt(
                prompt, max_items=max_items, role=role
            )
            results = [
                self._envelopper(self._serialize_item(k, iso_dates=True))
                for k in raw_results
            ]
            logger.debug(f"Retrieve for prompt returned {len(results)} items via RAG tool")
            return results

        # Mode fiable : appliquer la hiérarchie de fiabilité (P1-P4)
        priority_enum = None
        if min_priority is not None:
            priority_enum = self._convert_priority(min_priority)
        reliable = self._get_knowledge_manager().retrieve_reliable(
            prompt,
            max_items=max_items,
            min_priority=priority_enum,
            min_confidence=min_confidence if min_confidence is not None else 0.5,
            role=role,
        )
        # La réponse dit sa portée (VOLET 35, ch. 05), comme elle dit déjà si la
        # récupération était sémantique ou lexicale (ADR-015). Une réponse sur le
        # Sénégal construite sans aucune source sénégalaise doit le **dire** —
        # sinon elle se lit exactement comme une réponse bien sourcée.
        from src.knowledge_engine.scoped_retrieval import apply_scope_policy, scope_notice

        politique = apply_scope_policy(reliable["items"], question=prompt, limit=max_items)
        result = {
            "items": [
                self._envelopper(self._serialize_item(k, iso_dates=True))
                for k in politique["items"]
            ],
            "reliable": reliable["reliable"],
            "best_priority": reliable["best_priority"],
            "best_confidence": reliable["best_confidence"],
            "reason": reliable["reason"],
            "scope_report": politique["scope_report"],
            "scope_notice": scope_notice(politique["scope_report"]),
        }
        logger.debug(
            f"Retrieve for prompt (reliable) returned {len(result['items'])} items via RAG tool"
        )
        return result

    def _op_update(self, item_dict: Dict[str, Any], **kwargs) -> Dict[str, bool]:
        """
        Met à jour une connaissance existante.

        Args:
            item_dict: Dictionnaire représentant la connaissance avec les
                       champs à mettre à jour (dont priority et source).
                       L'ID doit être présent.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire indiquant le succès : {"updated": true/false}
        """
        if not isinstance(item_dict, dict) or "id" not in item_dict:
            raise ValueError(
                "Pour mettre à jour, un dictionnaire avec l'ID de la connaissance est requis"
            )
        knowledge_id = item_dict["id"]
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            raise ValueError("L'ID de la connaissance doit être une chaîne non vide")

        # Convertir les champs enum depuis les chaînes si présents
        if "knowledge_type" in item_dict and isinstance(item_dict["knowledge_type"], str):
            try:
                item_dict["knowledge_type"] = KnowledgeType[
                    item_dict["knowledge_type"].upper()
                ]
            except KeyError:
                raise ValueError(
                    f"Type de connaissance invalide: {item_dict['knowledge_type']}"
                )
        if "content_type" in item_dict and isinstance(
            item_dict["content_type"], str
        ):
            try:
                item_dict["content_type"] = ContentType[
                    item_dict["content_type"].upper()
                ]
            except KeyError:
                raise ValueError(
                    f"Type de contenu invalide: {item_dict['content_type']}"
                )
        if "language" in item_dict and isinstance(item_dict["language"], str):
            try:
                item_dict["language"] = Language[item_dict["language"].upper()]
            except KeyError:
                raise ValueError(f"Langue invalide: {item_dict['language']}")

        # Convertir la priorité depuis une chaîne ou un entier
        if "priority" in item_dict and not isinstance(item_dict["priority"], KnowledgePriority):
            item_dict["priority"] = self._convert_priority(item_dict["priority"])

        # Domaine, sensibilité et statut reviennent en chaînes des sorties de l'outil.
        self._convert_classification(item_dict)

        # Gestion de la source si fournie sous forme de dictionnaire
        if "source" in item_dict and isinstance(item_dict["source"], dict):
            item_dict["source"] = self._build_source(item_dict["source"])

        # Si la priorité n'est pas fournie mais que la source a une catégorie,
        # déduire la priorité à partir de la catégorie de source (hiérarchie P1-P4)
        if "priority" not in item_dict and isinstance(item_dict.get("source"), KnowledgeSource):
            item_dict["priority"] = KnowledgePriority.from_source_category(
                item_dict["source"].source_category
            )

        # Créer l'objet KnowledgeItem (sans l'ID qui sera ajouté séparément)
        # Nous devons exclure l'ID du dict passé au constructeur car KnowledgeItem
        # attend l'ID comme champ optionnel ; mais nous voulons mettre à jour
        # l'entité existante avec le même ID.
        item_dict_no_id = {k: v for k, v in item_dict.items() if k != "id"}

        # Incrémenter la version pour que la mise à jour soit acceptée par le store
        existing = self._get_knowledge_manager().get_knowledge(knowledge_id)
        if existing is not None:
            item_dict_no_id["version"] = existing.version + 1

        item = KnowledgeItem(id=knowledge_id, **item_dict_no_id)

        updated = self._get_knowledge_manager().update_knowledge(item)
        logger.info(
            f"Knowledge update {'succeeded' if updated else 'failed'} via RAG tool: {knowledge_id}"
        )
        return {"updated": updated}

    def _op_delete(self, knowledge_id: str, **kwargs) -> Dict[str, bool]:
        """
        Supprime une connaissance par son ID.

        Args:
            knowledge_id: L'ID de la connaissance à supprimer.
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Dictionnaire indiquant le succès : {"deleted": true/false}
        """
        if not isinstance(knowledge_id, str) or not knowledge_id.strip():
            raise ValueError("L'ID de la connaissance doit être une chaîne non vide")

        deleted = self._get_knowledge_manager().delete_knowledge(knowledge_id)
        logger.info(
            f"Knowledge deletion {'succeeded' if not deleted else 'failed'} via RAG tool' if deleted else 'via RAG tool: {knowledge_id}"
        )
        # Note: la logique ci-dessus renvoie True si supprimé, donc le message est légèrement inversé pour correspondre au bool.
        # Nous allons corriger le message ci-dessous.
        if deleted:
            logger.info(f"Knowledge deleted via RAG tool: {knowledge_id}")
        else:
            logger.info(f"Knowledge deletion failed (not found) via RAG tool: {knowledge_id}")
        return {"deleted": deleted}

    def _op_list(
        self,
        knowledge_type: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Liste les connaissances avec filtrage optionnel.

        Args:
            knowledge_type: Filtrer par type de connaissance.
            content_type: Filtrer par type de contenu.
            tags: Liste de tags (tous doivent être présents).
            limit: Nombre maximum d'éléments à retourner (défaut: 100).
            offset: Offset pour la pagination (défaut: 0).
            **kwargs: Options supplémentaires (aucune actuellement).

        Returns:
            Liste de dictionnaires représentant les connaissances listées.
        """
        # Pour la liste, nous récupérons tous les éléments puis appliquons les filtres et la pagination.
        # Cela pourrait être optimisé au niveau du gestionnaire de connaissances, mais pour une première
        # implémentation, cette approche suffit.
        all_items: List[KnowledgeItem] = self._get_knowledge_manager().get_store().list_items(
            limit=10000
        )  # obtenir un nombre suffisant

        # Préparer les filtres
        kt_enum: Optional[KnowledgeType] = None
        if knowledge_type is not None:
            if isinstance(knowledge_type, str):
                try:
                    kt_enum = KnowledgeType[knowledge_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de connaissance invalide pour la liste: {knowledge_type}")
            else:
                kt_enum = knowledge_type

        ct_enum: Optional[ContentType] = None
        if content_type is not None:
            if isinstance(content_type, str):
                try:
                    ct_enum = ContentType[content_type.upper()]
                except KeyError:
                    raise ValueError(f"Type de contenu invalide pour la liste: {content_type}")
            else:
                ct_enum = content_type

        tag_set: set = set(tags) if tags else set()

        filtered: List[KnowledgeItem] = []
        for k in all_items:
            if kt_enum is not None and k.knowledge_type != kt_enum:
                continue
            if ct_enum is not None and k.content_type != ct_enum:
                continue
            if tag_set and not tag_set.issubset(set(k.tags)):
                continue
            filtered.append(k)

        # Appliquer la pagination
        paginated = filtered[offset : offset + limit]

        # Convertir en dictionnaires
        results: List[Dict[str, Any]] = []
        for k in paginated:
            k_dict = self._serialize_item(k, iso_dates=True)
            results.append(k_dict)

        logger.debug(f"List operation returned {len(results)} items via RAG tool")
        return results

    def _op_stats(self, **kwargs) -> Dict[str, Any]:
        """
        Retourne des statistiques sur le moteur de connaissances.

        Returns:
            Dictionnaire de statistiques (voir KnowledgeManagerImpl.get_stats).
        """
        stats = self._get_knowledge_manager().get_stats()
        logger.debug("Stats retrieved via RAG tool")
        return stats

    # ------------------------------------------------------------------
    # Utilitaires internes
    # ------------------------------------------------------------------
    def available_operations(self) -> List[str]:
        """Retourne la liste des opérations prises en charge."""
        return sorted(
            name[len("_op_"):]
            for name in dir(self)
            if name.startswith("_op_") and callable(getattr(self, name))
        )

    def execute(self, *args, **kwargs) -> Any:
        """
        Exécute une opération sur le moteur de connaissances.

        Args:
            *args: L'opération, puis ses arguments éventuels.
            **kwargs: Options propres à l'opération.

        Returns:
            Résultat de l'opération, dépendant de celle-ci.

        Raises:
            ValueError: Opération inconnue.
        """
        if not args:
            raise ValueError(
                "Une opération est requise (add, get, search, retrieve_for_prompt, update, delete, list, stats)"
            )

        operation = str(args[0]).lower()
        handler = getattr(self, f"_op_{operation}", None)
        if handler is None:
            raise ValueError(
                f"Opération '{operation}' inconnue. "
                f"Opérations disponibles: {', '.join(self.available_operations())}"
            )

        return handler(*args[1:], **kwargs)