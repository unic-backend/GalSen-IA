"""
Réutiliser un calcul sans jamais faire passer un vieux pour un neuf (C16, §54).

## La phrase de §54 qui gouverne ce module

*« Never return stale artifacts as current without metadata. »* Elle n'interdit
pas de rendre une entrée périmée — elle interdit de la rendre **sans le dire**.
La nuance est tout : un cache qui refuse de servir du périmé est inutile le jour
où le fournisseur est indisponible ; un cache qui en sert sans le signaler
transforme une vidéo d'avant-hier en résultat du jour.

Ici, toute lecture rend l'entrée **et sa fraîcheur**. Il n'existe pas de méthode
qui rende la valeur seule : la métadonnée ne peut donc pas être « oubliée » par
un appelant pressé, parce qu'il faudrait l'écarter explicitement.

## L'invalidation est un acte, pas une échéance

§54 : *« Cache invalidation must be explicit. »* Une durée de vie fait
disparaître une entrée toute seule ; ce module n'en efface aucune au temps. Une
entrée vieillit et le dit — `FRESH` ou `STALE` selon le seuil que l'appelant a
posé — et seule `invalidate()` la retire.

La différence se voit le jour d'un incident : avec une expiration automatique,
l'entrée qui aurait sauvé l'exécution a déjà disparu.

## Ce qui change une clé change le résultat

Une clé porte l'empreinte des entrées **et** l'identité du producteur : le même
prompt servi par un autre fournisseur, ou une autre version du même, n'est pas
le même artefact. Les confondre rendrait le résultat d'un modèle en se
réclamant d'un autre — et la provenance enregistrée serait fausse.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .jobs import fingerprint

#: La fraîcheur d'une entrée. Trois valeurs : `UNKNOWN` couvre l'entrée dont
#: l'âge ne peut pas être jugé faute de seuil déclaré — et ne pas savoir n'est
#: pas être frais.
FRAIS = "FRESH"
PERIME = "STALE"
INDETERMINE = "UNKNOWN"
FRAICHEURS = (FRAIS, PERIME, INDETERMINE)


class CacheRefused(ValueError):
    """Une opération de cache impossible, avec sa raison."""


@dataclass(frozen=True)
class CacheEntry:
    """
    Une valeur mise de côté, et ce qui permet de la juger.

    Attributes:
        key: La clé, qui porte déjà entrées et producteur.
        value: Ce qui a été calculé.
        provider_id: Qui l'a produit.
        provider_version: Avec quelle version.
        stored_at: Quand, en temps epoch.
        inputs_sha256: L'empreinte des entrées.
    """

    key: str
    value: Any
    provider_id: str = ""
    provider_version: str = ""
    stored_at: float = 0.0
    inputs_sha256: str = ""

    def age_seconds(self, now: Optional[float] = None) -> float:
        """L'âge de l'entrée."""
        return round((now or time.time()) - self.stored_at, 3)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans la valeur."""
        return {
            "key": self.key, "provider_id": self.provider_id or None,
            "provider_version": self.provider_version or None,
            "stored_at": self.stored_at, "age_seconds": self.age_seconds(),
            "inputs_sha256": self.inputs_sha256 or None,
        }


def cache_key(
    kind: str, provider_id: str, provider_version: str = "", *inputs: str,
) -> str:
    """
    Construit une clé qui distingue ce qui doit l'être.

    Args:
        kind: Ce qui est mis en cache — `reference_analysis`, `audio_analysis`,
            `shot`, `embedding`…
        provider_id: Le producteur.
        provider_version: Sa version.
        *inputs: Les entrées, dans l'ordre.

    Returns:
        La clé. Le producteur et sa version **en font partie** : le même prompt
        servi par un autre modèle n'est pas le même artefact, et les confondre
        rendrait le résultat de l'un en se réclamant de l'autre.

    Raises:
        CacheRefused: Genre ou producteur absent — une clé anonyme collisionne
            avec tout.
    """
    if not str(kind or "").strip() or not str(provider_id or "").strip():
        raise CacheRefused(
            "Une clé de cache sans genre ni producteur collisionnerait avec "
            "n'importe quoi, et rendrait un artefact pour un autre."
        )
    return f"{kind}:{provider_id}:{provider_version or 'unversioned'}:" \
           f"{fingerprint(*inputs)}"


class CreativeCache:
    """
    Un cache dont toute lecture porte la fraîcheur de ce qu'elle rend.

    Il n'y a pas de `get()` qui rende la valeur seule. C'est délibéré : une
    telle méthode serait celle que tout le monde appellerait, et la métadonnée
    que §54 exige disparaîtrait du code appelant sans que personne l'ait décidé.
    """

    def __init__(self, stale_after_seconds: Optional[float] = None) -> None:
        """
        Ouvre un cache.

        Args:
            stale_after_seconds: L'âge au-delà duquel une entrée est `STALE`.
                `None` veut dire qu'aucun seuil n'a été posé — la fraîcheur est
                alors `UNKNOWN`, et **non** `FRESH` : ne pas savoir juger l'âge
                n'est pas le juger bon.
        """
        if stale_after_seconds is not None and stale_after_seconds <= 0:
            raise CacheRefused(
                "Un seuil nul ou négatif rendrait tout périmé dès l'écriture."
            )
        self.stale_after_seconds = stale_after_seconds
        self._entrees: Dict[str, CacheEntry] = {}
        self._invalidations: List[Dict[str, Any]] = []

    def put(
        self, key: str, value: Any, provider_id: str = "",
        provider_version: str = "", inputs_sha256: str = "",
    ) -> CacheEntry:
        """Range une valeur, en notant qui l'a produite et quand."""
        entree = CacheEntry(
            key=key, value=value, provider_id=provider_id,
            provider_version=provider_version, stored_at=time.time(),
            inputs_sha256=inputs_sha256,
        )
        self._entrees[key] = entree
        return entree

    def lookup(
        self, key: str, now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Cherche une entrée et rend **toujours** sa fraîcheur avec elle.

        Args:
            key: La clé cherchée.
            now: L'instant du jugement, pour les tests.

        Returns:
            `hit`, la valeur, la fraîcheur et l'âge. Une entrée périmée est
            rendue — §54 n'interdit pas de servir du périmé, il interdit de le
            servir **sans le dire**. Refuser tout net rendrait le cache inutile
            le jour où le fournisseur est indisponible, ce qui est justement le
            jour où il sert.
        """
        entree = self._entrees.get(key)
        if entree is None:
            return {"hit": False, "key": key, "freshness": None, "value": None}

        age = entree.age_seconds(now)
        if self.stale_after_seconds is None:
            fraicheur = INDETERMINE
            raison = (
                "Aucun seuil de péremption déclaré : l'âge de l'entrée ne peut "
                "pas être jugé. Ne pas savoir n'est pas être frais."
            )
        elif age > self.stale_after_seconds:
            fraicheur = PERIME
            raison = (
                f"Écrite il y a {age} s, seuil {self.stale_after_seconds} s. "
                "L'entrée est rendue quand même, et c'est à l'appelant de "
                "décider s'il s'en sert."
            )
        else:
            fraicheur = FRAIS
            raison = ""

        return {
            "hit": True, "key": key, "value": entree.value,
            "freshness": fraicheur, "age_seconds": age,
            "reason": raison, "metadata": entree.as_dict(),
        }

    def invalidate(self, key: str, by: str, reason: str) -> Dict[str, Any]:
        """
        Retire une entrée, explicitement.

        Args:
            key: L'entrée à retirer.
            by: Qui la retire.
            reason: Pourquoi. Une invalidation sans motif ne se relit pas, et
                c'est la première chose qu'on cherche après un incident.

        Raises:
            CacheRefused: Entrée absente, auteur ou motif manquant.
        """
        if key not in self._entrees:
            raise CacheRefused(
                f"Entrée « {key} » absente : l'invalider masquerait une erreur "
                "de clé chez l'appelant."
            )
        if not str(by or "").strip() or not str(reason or "").strip():
            raise CacheRefused(
                "Une invalidation sans auteur ni motif ne se relit pas — et "
                "c'est la première chose qu'on cherche après un incident."
            )
        del self._entrees[key]
        trace = {"key": key, "by": by, "reason": reason, "at": time.time()}
        self._invalidations.append(trace)
        return trace

    def invalidate_provider(
        self, provider_id: str, by: str, reason: str,
    ) -> List[str]:
        """
        Retire tout ce qu'un fournisseur a produit.

        Le cas d'usage réel : un fournisseur change de version, ou sa licence
        se révèle incompatible. Garder ses artefacts les ferait resservir sous
        une provenance devenue fausse.
        """
        cles = [cle for cle, entree in self._entrees.items()
                if entree.provider_id == provider_id]
        for cle in cles:
            self.invalidate(cle, by=by, reason=reason)
        return cles

    def report(self) -> Dict[str, Any]:
        """
        L'état du cache et les règles qu'il tient.

        Returns:
            Les comptes par fraîcheur, l'historique des invalidations, et le
            rappel qu'aucune entrée ne disparaît toute seule.
        """
        comptes: Dict[str, int] = {}
        for cle in self._entrees:
            fraicheur = self.lookup(cle)["freshness"]
            comptes[fraicheur] = comptes.get(fraicheur, 0) + 1

        return {
            "entries": len(self._entrees),
            "by_freshness": comptes,
            "stale_after_seconds": self.stale_after_seconds,
            "invalidations": list(self._invalidations),
            "rules": [
                "Toute lecture rend la fraîcheur avec la valeur : il n'existe "
                "pas de méthode qui rende la valeur seule, pour que la "
                "métadonnée de §54 ne puisse pas être oubliée.",
                "Une entrée périmée est **rendue**, marquée `STALE` : refuser "
                "tout net rendrait le cache inutile le jour où le fournisseur "
                "est indisponible, qui est le jour où il sert.",
                "Sans seuil déclaré, la fraîcheur est `UNKNOWN`, pas `FRESH` — "
                "ne pas savoir juger l'âge n'est pas le juger bon.",
                "Aucune entrée ne disparaît au temps : seule `invalidate()` "
                "retire, avec un auteur et un motif.",
                "Le producteur et sa version font partie de la clé : le même "
                "prompt servi par un autre modèle n'est pas le même artefact.",
            ],
        }
