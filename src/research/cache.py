"""
Réutiliser une recherche sans faire passer une vieille pour une neuve
(R08, STEP 11).

## Ce module ne réécrit pas un cache

STEP 11 : *« réutiliser l'architecture de cache existante si elle existe »*.
Elle existe, et elle fait déjà exactement ce que STEP 11 demande —
`src/creative/cache.py` (C16, §54) :

- **aucune lecture ne rend la valeur seule** : la fraîcheur voyage avec elle,
  donc un appelant pressé ne peut pas « oublier » la métadonnée ;
- **l'invalidation est un acte, pas une échéance** : rien n'expire tout seul,
  parce que le jour d'un incident, l'entrée qui aurait sauvé l'exécution aurait
  déjà disparu ;
- **la clé porte le producteur et sa version** : le même prompt servi par un
  autre fournisseur n'est pas le même résultat.

Ce module apporte donc **la clé propre à la recherche**, et rien d'autre. Le
mécanisme reste celui de `CreativeCache`.

## Ce que la clé de recherche doit distinguer

Quatre choses, et en oublier une rend le résultat d'une requête pour une autre :

1. **le genre** — un résultat de recherche n'est pas une page récupérée ;
2. **le fournisseur et sa version** — déjà porté par `cache_key` ;
3. **la requête ou l'URL**, telle qu'écrite ;
4. **la capacité** — `web_search` et `academic_search` sur les mêmes mots ne
   ramènent pas la même chose.

## Ce que ce module refuse

**Il ne pose aucun seuil de péremption par défaut.** Sans seuil, une lecture
rend `UNKNOWN` — *ne pas savoir n'est pas être frais*. Poser une valeur
plausible ferait juger la fraîcheur d'une recherche par un chiffre que personne
n'a mesuré ; c'est à l'appelant de dire au bout de combien de temps **sa**
question vieillit. Une actualité vieillit en minutes, une définition en années.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..creative.cache import CreativeCache, cache_key
from .sources import ResearchSource

#: Les genres mis en cache. Un genre inconnu est refusé pour être **ajouté
#: ici** : deux genres confondus rendraient une page pour une liste de
#: résultats.
GENRES = ("search_results", "fetched_page", "normalized_source", "metadata")


class ResearchCacheRefused(ValueError):
    """Une entrée de cache impossible telle quelle."""


def research_key(kind: str, provider_id: str, capability: str,
                 subject: str, provider_version: str = "") -> str:
    """
    Construit une clé de cache de recherche.

    Args:
        kind: Le genre, parmi `GENRES`.
        provider_id: Le fournisseur qui a produit le résultat.
        capability: La capacité employée — deux capacités sur les mêmes mots ne
            ramènent pas la même chose.
        subject: La requête ou l'URL, telle qu'écrite.
        provider_version: La version du fournisseur.

    Returns:
        La clé.

    Raises:
        ResearchCacheRefused: Genre inconnu, capacité ou sujet absent.
    """
    if kind not in GENRES:
        raise ResearchCacheRefused(
            f"Genre « {kind} » non déclaré. Déclarés : {list(GENRES)}."
        )
    if not str(capability or "").strip():
        raise ResearchCacheRefused(
            "Une clé sans capacité confondrait une recherche web et une "
            "recherche académique sur les mêmes mots."
        )
    if not str(subject or "").strip():
        raise ResearchCacheRefused(
            "Une clé sans requête ni URL ne distingue rien."
        )
    return cache_key(kind, provider_id, provider_version, capability, subject)


class ResearchCache:
    """
    Le cache de recherche — une clé propre, un mécanisme emprunté.

    Attributes:
        stale_after_seconds: Le seuil de péremption. `None` = **non déclaré**,
            et toute lecture rend alors `UNKNOWN`.
    """

    def __init__(self, stale_after_seconds: Optional[float] = None) -> None:
        """
        Args:
            stale_after_seconds: Au bout de combien de temps une entrée est
                jugée périmée. `None` par défaut : aucun chiffre plausible n'est
                posé à la place de l'appelant.
        """
        self._cache = CreativeCache(stale_after_seconds=stale_after_seconds)

    @property
    def stale_after_seconds(self) -> Optional[float]:
        """Le seuil déclaré, ou `None`."""
        return self._cache.stale_after_seconds

    def put_results(self, provider_id: str, capability: str, query: str,
                    results: Any, provider_version: str = "",
                    content_hash: str = "") -> Dict[str, Any]:
        """
        Range des résultats de recherche.

        Args:
            provider_id: Le fournisseur.
            capability: La capacité employée.
            query: La requête, telle qu'écrite.
            results: Ce qui a été rapporté.
            provider_version: La version du fournisseur.
            content_hash: L'empreinte, quand elle est connue.

        Returns:
            La métadonnée de l'entrée rangée.
        """
        cle = research_key("search_results", provider_id, capability, query,
                           provider_version)
        entree = self._cache.put(cle, results, provider_id=provider_id,
                                 provider_version=provider_version,
                                 inputs_sha256=content_hash)
        return entree.as_dict()

    def put_source(self, source: ResearchSource, content: Any = None
                   ) -> Dict[str, Any]:
        """
        Range une source normalisée, sous sa propre URL.

        Args:
            source: La source normalisée.
            content: Le contenu associé, quand il y en a un.

        Returns:
            La métadonnée de l'entrée rangée.

        Note:
            L'empreinte rangée est **celle de la source**, pas une nouvelle :
            deux empreintes du même contenu finiraient par diverger.
        """
        cle = research_key("normalized_source", source.provider,
                           source.source_type, source.source_url,
                           source.provider_version)
        entree = self._cache.put(cle, content if content is not None else
                                 source.as_dict(),
                                 provider_id=source.provider,
                                 provider_version=source.provider_version,
                                 inputs_sha256=source.content_hash)
        return entree.as_dict()

    def lookup(self, kind: str, provider_id: str, capability: str,
               subject: str, provider_version: str = "",
               now: Optional[float] = None) -> Dict[str, Any]:
        """
        Cherche une entrée et rend **toujours** sa fraîcheur avec elle.

        Args:
            kind: Le genre cherché.
            provider_id: Le fournisseur.
            capability: La capacité.
            subject: La requête ou l'URL.
            provider_version: La version du fournisseur.
            now: L'instant du jugement, pour les tests.

        Returns:
            `hit`, la valeur, la fraîcheur, l'âge et la métadonnée. Il n'existe
            **pas** de méthode qui rende la valeur seule.
        """
        cle = research_key(kind, provider_id, capability, subject,
                           provider_version)
        return self._cache.lookup(cle, now=now)

    def invalidate(self, kind: str, provider_id: str, capability: str,
                   subject: str, by: str, reason: str,
                   provider_version: str = "") -> Dict[str, Any]:
        """
        Retire une entrée, explicitement, en disant qui et pourquoi.

        Args:
            kind: Le genre.
            provider_id: Le fournisseur.
            capability: La capacité.
            subject: La requête ou l'URL.
            by: Qui invalide.
            reason: Pourquoi.
            provider_version: La version du fournisseur.

        Returns:
            Le compte rendu du retrait.
        """
        cle = research_key(kind, provider_id, capability, subject,
                           provider_version)
        return self._cache.invalidate(cle, by=by, reason=reason)

    def invalidate_provider(self, provider_id: str, by: str,
                            reason: str) -> Dict[str, Any]:
        """
        Retire tout ce qu'un fournisseur a produit.

        Args:
            provider_id: Le fournisseur.
            by: Qui invalide.
            reason: Pourquoi — par exemple, une version qui change.

        Returns:
            Le compte rendu du retrait.
        """
        return self._cache.invalidate_provider(provider_id, by=by,
                                               reason=reason)

    def report(self) -> Dict[str, Any]:
        """
        L'état du cache, plus ce que la couche recherche y ajoute.

        Returns:
            Le rapport du cache emprunté, enrichi des genres et des règles.
        """
        rapport = dict(self._cache.report())
        rapport["kinds"] = list(GENRES)
        rapport["mechanism"] = "creative.cache.CreativeCache"
        rapport["rules"] = [
            "Aucune lecture ne rend la valeur sans sa fraîcheur.",
            "Aucun seuil de péremption par défaut : sans seuil, la fraîcheur "
            "est UNKNOWN, et ne pas savoir n'est pas être frais.",
            "L'invalidation est un acte, jamais une échéance.",
            "La clé porte le genre, le fournisseur, sa version, la capacité et "
            "la requête : en oublier une rendrait un résultat pour un autre.",
            "Le mécanisme est emprunté, pas réécrit.",
        ]
        return rapport
