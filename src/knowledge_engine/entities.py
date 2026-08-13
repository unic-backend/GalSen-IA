"""
Entités et relations, avec leur provenance (VOLET 36, chapitre E).

## Pourquoi le graphe existant ne suffisait pas — mesuré

`InMemoryKnowledgeGraph` stocke `nœud = identifiant de connaissance` et
`arête = (cible, relation)`. Il ne peut donc représenter :

- une entité qui n'est **pas** un passage de connaissance — une personne, une
  loi, un lieu ;
- une propriété sur une entité — un code ISO, un secteur, un autre nom ;
- **la provenance, la date ou la confiance d'une relation.**

Le troisième point est le plus lourd : une relation sans source est une
affirmation que personne ne peut contester. « Cette loi abroge celle-là » a
autant besoin d'une source que le texte des deux lois.

La structure du graphe reste réutilisable ; le modèle de données ne l'est pas.
Les entités doivent exister comme objets à part entière.

## La règle qui ne se négocie pas

**Aucune entité, aucune relation sans source.** Le magasin refuse — il ne
signale pas, il ne marque pas « à vérifier », il refuse. Une entité extraite
d'un texte par un modèle et rangée sans source serait de la connaissance par
inférence, exactement ce que cette architecture existe pour empêcher.
L'extraction **propose** ; un humain ou un document sourcé confirme.

## Pas de base graphe, et le déclencheur est écrit

Deux tables et des index répondent à toutes les questions que l'ontologie
implique : voisins, parcours typé de profondeur 1 à 3, filtrage par portée et
par sujet. `DECLENCHEUR_BASE_GRAPHE` porte les seuils à partir desquels la
question se repose — pour qu'elle ne devienne pas une affaire de goût.
"""

import hashlib
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .scope import KnowledgeScope, KnowledgeSubject, parse_subject

#: Profondeur de parcours maximale. Au-delà, ce n'est plus un voisinage : c'est
#: une requête qui appelle une base graphe, et le déclencheur ci-dessous le dit.
PROFONDEUR_MAXIMALE = 3

#: Ce qui justifierait d'adopter une base graphe. Écrit ici pour que la décision
#: repose sur une mesure et non sur une impression, le jour où elle se posera.
DECLENCHEUR_BASE_GRAPHE = (
    "un parcours nécessaire dépasse la profondeur 3",
    "le nombre d'entités dépasse ~100 000",
    "une requête mesurée dépasse 200 ms en SQLite",
)


class EntityType(Enum):
    """
    Les types d'entités, fermés au départ.

    Fermés pour la même raison que `KnowledgeSubject` : un type que personne ne
    peut nommer ne reçoit ni propriétaire, ni règle de rapprochement, ni
    registre de sources. En ajouter un est une modification de ce fichier, donc
    une décision relue.
    """

    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    EVENT = "event"
    DATE = "date"
    INSTITUTION = "institution"
    DOCUMENT = "document"
    LAW = "law"
    CULTURAL_PRACTICE = "cultural_practice"
    LANGUAGE = "language"
    HISTORICAL_PERIOD = "historical_period"
    ACADEMIC_WORK = "academic_work"
    HERITAGE_SITE = "heritage_site"


class EntityRefused(ValueError):
    """Une entité ou une relation a été proposée sans ce qui la rend vérifiable."""


def parse_entity_type(valeur: Any) -> EntityType:
    """
    Lit un type d'entité depuis sa forme textuelle.

    Un type inconnu est refusé : il n'existe pas de `UNSPECIFIED` ici, parce
    qu'une entité dont on ignore la nature ne peut être rapprochée d'aucune
    autre — elle ferait un doublon silencieux à la première réécriture.
    """
    if isinstance(valeur, EntityType):
        return valeur
    texte = str(valeur or "").strip().lower()
    try:
        return EntityType(texte)
    except ValueError:
        connus = ", ".join(t.value for t in EntityType)
        raise EntityRefused(f"Type d'entité « {valeur} » inconnu. Types déclarés : {connus}.")


def _sources_valides(sources: Iterable[Any], quoi: str) -> Tuple[str, ...]:
    """
    Nettoie une liste de sources, et refuse si elle est vide.

    C'est le seul endroit où la règle est appliquée : la répéter dans les deux
    constructeurs donnerait deux versions qui finiraient par diverger.
    """
    retenues = tuple(
        str(source).strip() for source in (sources or ()) if str(source).strip()
    )
    if not retenues:
        raise EntityRefused(
            f"{quoi} sans source : elle serait une affirmation que personne ne peut "
            "vérifier ni contester. Une extraction propose, un document confirme."
        )
    return retenues


def _identifiant(prefixe: str, *parties: str) -> str:
    """Construit un identifiant stable et déterministe."""
    empreinte = hashlib.sha256("|".join(parties).encode("utf-8")).hexdigest()[:16]
    return f"{prefixe}_{empreinte}"


@dataclass
class Entity:
    """
    Une entité du monde, pas un passage de texte.

    Attributes:
        label: Nom principal.
        type: Nature de l'entité.
        sources: D'où on la tient. **Jamais vide.**
        aliases: Autres noms — orthographes, translittérations.
        scope: D'où cette entité vaut (ADR-019).
        subject: De quoi elle relève (ADR-019).
        confidence: Confiance **rapportée par la source**. `None` quand la
            source n'en déclare pas — un 0.5 par défaut serait un chiffre
            inventé, et il serait lu comme une mesure.
        properties: Propriétés libres (code ISO, secteur, dates…).
    """

    label: str
    type: EntityType = EntityType.ORGANIZATION
    sources: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()
    scope: str = "global"
    subject: KnowledgeSubject = KnowledgeSubject.UNSPECIFIED
    confidence: Optional[float] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    entity_id: str = ""
    version: int = 1
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Valide l'entité et calcule son identifiant."""
        self.label = str(self.label or "").strip()
        if not self.label:
            raise EntityRefused("Une entité sans nom ne peut être ni citée ni retrouvée.")
        self.type = parse_entity_type(self.type)
        self.subject = parse_subject(self.subject)
        self.scope = str(KnowledgeScope.parse(self.scope))
        self.sources = _sources_valides(self.sources, "Entité")
        self.aliases = tuple(
            str(alias).strip() for alias in self.aliases if str(alias).strip()
        )
        if not self.entity_id:
            # L'identifiant tient au type, au nom normalisé et à la portée : la
            # même institution ingérée deux fois se met à jour au lieu de créer
            # un doublon que rien ne rapprocherait ensuite.
            self.entity_id = _identifiant(
                "ent", self.type.value, self.label.strip().lower(), self.scope
            )

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'entité."""
        return {
            "entity_id": self.entity_id,
            "type": self.type.value,
            "label": self.label,
            "aliases": list(self.aliases),
            "scope": self.scope,
            "subject": self.subject.value,
            "sources": list(self.sources),
            "confidence": self.confidence,
            "properties": dict(self.properties),
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, donnees: Dict[str, Any]) -> "Entity":
        """Reconstruit une entité depuis sa forme sérialisée."""
        return cls(
            label=donnees["label"],
            type=donnees.get("type", EntityType.ORGANIZATION),
            sources=tuple(donnees.get("sources", ())),
            aliases=tuple(donnees.get("aliases", ())),
            scope=donnees.get("scope", "global"),
            subject=donnees.get("subject", KnowledgeSubject.UNSPECIFIED),
            confidence=donnees.get("confidence"),
            properties=dict(donnees.get("properties", {})),
            entity_id=donnees.get("entity_id", ""),
            version=int(donnees.get("version", 1)),
            created_at=float(donnees.get("created_at", time.time())),
            updated_at=float(donnees.get("updated_at", time.time())),
        )


@dataclass
class Relation:
    """
    Un lien entre deux entités, avec sa propre provenance.

    C'est ce que le graphe existant ne sait pas porter. Une relation a des
    sources **distinctes** de celles de ses extrémités : savoir qui est le
    ministre et savoir qu'il dirige tel ministère ne viennent pas forcément du
    même document.

    Attributes:
        valid_from / valid_to: Une relation cesse d'être vraie. Un ministre
            quitte son poste, une loi est abrogée. Sans ces bornes, une base de
            relations devient fausse en vieillissant, sans que rien ne le dise.
    """

    source_id: str
    target_id: str
    relation: str
    sources: Tuple[str, ...] = ()
    confidence: Optional[float] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    relation_id: str = ""
    version: int = 1
    created_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        """Valide la relation et calcule son identifiant."""
        self.source_id = str(self.source_id or "").strip()
        self.target_id = str(self.target_id or "").strip()
        self.relation = str(self.relation or "").strip().lower()
        if not self.source_id or not self.target_id:
            raise EntityRefused("Une relation sans ses deux extrémités ne relie rien.")
        if not self.relation:
            raise EntityRefused(
                "Une relation sans nom serait un lien dont personne ne sait ce "
                "qu'il affirme."
            )
        self.sources = _sources_valides(self.sources, "Relation")
        if not self.relation_id:
            self.relation_id = _identifiant(
                "rel", self.source_id, self.relation, self.target_id,
                self.valid_from or "",
            )

    def is_valid_at(self, date: str) -> bool:
        """
        Indique si la relation vaut à cette date (`AAAA-MM-JJ`).

        Une borne absente veut dire « non déclarée », pas « depuis toujours » :
        la relation est alors considérée valide de ce côté, et c'est la
        déclaration qui manque, pas la validité.
        """
        if self.valid_from and date < self.valid_from:
            return False
        if self.valid_to and date > self.valid_to:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la relation."""
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "sources": list(self.sources),
            "confidence": self.confidence,
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
            "version": self.version,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, donnees: Dict[str, Any]) -> "Relation":
        """Reconstruit une relation depuis sa forme sérialisée."""
        return cls(
            source_id=donnees["source_id"],
            target_id=donnees["target_id"],
            relation=donnees["relation"],
            sources=tuple(donnees.get("sources", ())),
            confidence=donnees.get("confidence"),
            valid_from=donnees.get("valid_from"),
            valid_to=donnees.get("valid_to"),
            relation_id=donnees.get("relation_id", ""),
            version=int(donnees.get("version", 1)),
            created_at=float(donnees.get("created_at", time.time())),
        )


class InMemoryEntityStore:
    """
    Magasin d'entités et de relations, en mémoire.

    Même interface que son équivalent SQLite : c'est le magasin qui change avec
    `GALSEN_STORAGE_BACKEND`, jamais l'appelant.
    """

    def __init__(self) -> None:
        """Initialise un magasin vide."""
        self._entities: Dict[str, Entity] = {}
        self._relations: Dict[str, Relation] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Entités
    # ------------------------------------------------------------------
    def save_entity(self, entity: Entity) -> str:
        """
        Enregistre une entité, ou met à jour celle qui porte le même identifiant.

        Réenregistrer la même entité **ne duplique pas** : les sources sont
        réunies et la version augmente. Deux fiches pour la même institution
        seraient deux vérités que plus rien ne rapprocherait.
        """
        with self._lock:
            existante = self._entities.get(entity.entity_id)
            if existante is not None:
                sources = tuple(dict.fromkeys(existante.sources + entity.sources))
                alias = tuple(dict.fromkeys(existante.aliases + entity.aliases))
                entity.sources = sources
                entity.aliases = alias
                entity.version = existante.version + 1
                entity.created_at = existante.created_at
                entity.updated_at = time.time()
            self._entities[entity.entity_id] = entity
            return entity.entity_id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Retourne une entité, ou None."""
        with self._lock:
            return self._entities.get(entity_id)

    def find_entities(
        self,
        type: Any = None,
        scope: Any = None,
        subject: Any = None,
        label: str = "",
        limit: int = 100,
    ) -> List[Entity]:
        """
        Cherche des entités par type, portée, sujet ou nom.

        Le nom est comparé au principal **et aux alias** : une entité qu'on ne
        retrouve que sous son orthographe officielle est introuvable pour qui ne
        la connaît pas.
        """
        with self._lock:
            resultats = []
            recherche = label.strip().lower()
            type_voulu = parse_entity_type(type) if type is not None else None
            portee_voulue = str(KnowledgeScope.parse(scope)) if scope is not None else None
            sujet_voulu = parse_subject(subject) if subject is not None else None

            for entite in self._entities.values():
                if type_voulu is not None and entite.type is not type_voulu:
                    continue
                if portee_voulue is not None and entite.scope != portee_voulue:
                    continue
                if sujet_voulu is not None and entite.subject is not sujet_voulu:
                    continue
                if recherche:
                    noms = [entite.label.lower()] + [a.lower() for a in entite.aliases]
                    if not any(recherche in nom for nom in noms):
                        continue
                resultats.append(entite)
                if len(resultats) >= limit:
                    break
            return resultats

    def delete_entity(self, entity_id: str) -> bool:
        """Supprime une entité et les relations qui la touchent."""
        with self._lock:
            if entity_id not in self._entities:
                return False
            del self._entities[entity_id]
            for identifiant, relation in list(self._relations.items()):
                if entity_id in (relation.source_id, relation.target_id):
                    del self._relations[identifiant]
            return True

    # ------------------------------------------------------------------
    # Relations
    # ------------------------------------------------------------------
    def save_relation(self, relation: Relation) -> str:
        """
        Enregistre une relation entre deux entités **existantes**.

        Raises:
            EntityRefused: Si une extrémité n'existe pas. Une relation vers une
                entité absente est un lien pendant : il se lit comme un fait et
                ne mène nulle part.
        """
        with self._lock:
            for identifiant in (relation.source_id, relation.target_id):
                if identifiant not in self._entities:
                    raise EntityRefused(
                        f"Relation vers une entité inconnue « {identifiant} » : "
                        "enregistrer l'entité avant la relation."
                    )
            self._relations[relation.relation_id] = relation
            return relation.relation_id

    def relations_of(
        self, entity_id: str, direction: str = "both", relation: str = ""
    ) -> List[Relation]:
        """
        Retourne les relations d'une entité.

        Args:
            direction: `out`, `in` ou `both`.
            relation: Filtre sur le nom de la relation.
        """
        with self._lock:
            trouvees = []
            for lien in self._relations.values():
                if relation and lien.relation != relation.strip().lower():
                    continue
                sortante = lien.source_id == entity_id
                entrante = lien.target_id == entity_id
                if direction == "out" and not sortante:
                    continue
                if direction == "in" and not entrante:
                    continue
                if direction == "both" and not (sortante or entrante):
                    continue
                trouvees.append(lien)
            return trouvees

    def neighbours(
        self, entity_id: str, depth: int = 1, relation: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Parcourt le voisinage d'une entité.

        Args:
            entity_id: Point de départ.
            depth: Profondeur, bornée à `PROFONDEUR_MAXIMALE`.
            relation: Ne suit que ce type de lien, si donné.

        Returns:
            Les entités atteintes, chacune avec sa distance et le chemin de
            relations parcouru. Le chemin est rendu parce qu'un voisin de
            profondeur 2 sans son chemin est une affirmation sans raisonnement.

        Raises:
            EntityRefused: Si la profondeur demandée dépasse le maximum — c'est
                le déclencheur écrit de `DECLENCHEUR_BASE_GRAPHE`, pas une
                limite arbitraire.
        """
        if depth > PROFONDEUR_MAXIMALE:
            raise EntityRefused(
                f"Profondeur {depth} demandée, maximum {PROFONDEUR_MAXIMALE}. "
                "Au-delà, la question appelle une base graphe : "
                + " ; ".join(DECLENCHEUR_BASE_GRAPHE)
            )

        with self._lock:
            atteints: Dict[str, Dict[str, Any]] = {}
            frontiere: List[Tuple[str, List[str]]] = [(entity_id, [])]
            for distance in range(1, max(depth, 0) + 1):
                suivante: List[Tuple[str, List[str]]] = []
                for courant, chemin in frontiere:
                    for lien in self.relations_of(courant, relation=relation):
                        voisin = lien.target_id if lien.source_id == courant else lien.source_id
                        if voisin == entity_id or voisin in atteints:
                            continue
                        entite = self._entities.get(voisin)
                        if entite is None:
                            continue
                        chemin_voisin = chemin + [lien.relation]
                        atteints[voisin] = {
                            "entity": entite.to_dict(),
                            "depth": distance,
                            "path": chemin_voisin,
                        }
                        suivante.append((voisin, chemin_voisin))
                frontiere = suivante
                if not frontiere:
                    break
            return list(atteints.values())

    # ------------------------------------------------------------------
    # Mesure
    # ------------------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        """
        Décrit ce que le magasin contient réellement.

        `entities_without_source` vaut 0 par construction — le champ reste
        publié : le jour où un chemin d'écriture contournerait le refus, c'est
        ici que ça se verrait.
        """
        with self._lock:
            par_type: Dict[str, int] = {}
            par_portee: Dict[str, int] = {}
            for entite in self._entities.values():
                par_type[entite.type.value] = par_type.get(entite.type.value, 0) + 1
                par_portee[entite.scope] = par_portee.get(entite.scope, 0) + 1
            return {
                "entities": len(self._entities),
                "relations": len(self._relations),
                "by_type": dict(sorted(par_type.items())),
                "by_scope": dict(sorted(par_portee.items())),
                "entities_without_source": sum(
                    1 for entite in self._entities.values() if not entite.sources
                ),
                "relations_without_source": sum(
                    1 for lien in self._relations.values() if not lien.sources
                ),
                "max_depth": PROFONDEUR_MAXIMALE,
                "graph_database_trigger": list(DECLENCHEUR_BASE_GRAPHE),
                "backend": "in-memory",
            }


def entity_store() -> Any:
    """
    Retourne le magasin d'entités choisi par la configuration (ADR-005).

    `GALSEN_STORAGE_BACKEND=sqlite` persiste, `in-memory` — le défaut — ne
    persiste pas. Le point de décision reste `src/storage/paths.py` : le
    réécrire ici en ferait une deuxième règle qui finirait par diverger.
    """
    from src.storage.paths import sqlite_enabled

    if sqlite_enabled():
        from src.storage.sqlite_entity_store import SQLiteEntityStore

        return SQLiteEntityStore()
    return InMemoryEntityStore()
