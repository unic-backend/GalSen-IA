"""
Des travaux créatifs sur la file qui existe déjà (C16, §53, §55).

## Ce que §53 demande, et qui est déjà là

*« Reuse the existing job system if one already exists. »* Il en existe un :
`RenderQueue` (`src/media/queue/jobs.py`) — dépôt, priorités déclarées, avancée
par unités comptées, tentatives bornées, reprise, annulation, réservations,
rapport. Il reprend `RunStatus` du routeur de workflows, donc il ne porte pas
non plus un vocabulaire d'états à lui.

Ce module n'en écrit donc **pas un second**. Il ajoute ce que la file ne peut
pas connaître : quel fournisseur a servi, avec quelle version, **et quelles
références ont conditionné le résultat**.

## Pourquoi le lien vers les références est structurel

ADR-025 promet qu'une personne peut retirer sa référence. Cette promesse ne
tient que si l'on sait quels artefacts elle a conditionnés — sinon « supprimez
ma photo » supprime une ligne dans une table et laisse la vidéo en ligne.

`CreativeJob.references` n'est donc pas de la traçabilité de confort : c'est ce
qui rend la révocation possible. Un travail qui déclare avoir utilisé des
références et n'en nomme aucune est **refusé**, parce qu'il produirait un
artefact que personne ne pourra rattacher.

## Ce que ce module ne fait pas

Il n'exécute rien, ne réserve pas de GPU (`src/creative/resources.py` mesure,
`RenderQueue.reservations` déclare), et n'invente aucune progression : le total
d'unités reste `None` quand il est inconnu, jamais `0`, parce qu'un travail à
`0/0` paraît terminé.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..media.queue.jobs import PRIORITE_NORMALE, RenderQueue
from ..router.workflow_checkpoint import RunStatus

#: Ce qu'un travail créatif produit. Déclaré, pour qu'un travail ne puisse pas
#: annoncer un genre que rien ne sait relire.
GENRES = ("video", "image", "audio", "analysis")


class CreativeJobRefused(ValueError):
    """Un travail créatif impossible à déposer tel qu'il est demandé."""


@dataclass(frozen=True)
class Provenance:
    """
    De quoi un artefact est issu (§55).

    Attributes:
        provider_id: Le fournisseur qui a produit.
        model: Le modèle, quand il est nommé.
        version: La version du fournisseur ou du modèle.
        parameters: Les paramètres, tels quels.
        seed: La graine, quand il y en a une. `None` quand le fournisseur n'en
            expose pas — et non `0`, qui serait une graine.
        references: Les références qui ont conditionné le résultat.
        inputs_sha256: L'empreinte des entrées.
        at: Quand.
    """

    provider_id: str
    model: str = ""
    version: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    seed: Optional[int] = None
    references: Tuple[str, ...] = ()
    inputs_sha256: str = ""
    at: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "provider_id": self.provider_id, "model": self.model or None,
            "version": self.version or None, "parameters": dict(self.parameters),
            "seed": self.seed, "references": list(self.references),
            "inputs_sha256": self.inputs_sha256 or None, "at": self.at,
        }


def fingerprint(*parts: str) -> str:
    """
    L'empreinte SHA-256 d'un jeu d'entrées.

    Args:
        *parts: Les morceaux à empreindre, dans l'ordre.

    Returns:
        L'empreinte hexadécimale. L'ordre compte et n'est pas trié : deux jeux
        d'entrées dans un ordre différent sont deux jeux différents pour un
        générateur.
    """
    empreinte = hashlib.sha256()
    for part in parts:
        empreinte.update(str(part).encode("utf-8"))
        empreinte.update(b"\x00")  # séparateur : « ab »+« c » ≠ « a »+« bc »
    return empreinte.hexdigest()


@dataclass
class CreativeJob:
    """
    Ce que la file ne peut pas savoir d'un travail créatif.

    Attributes:
        job_id: L'identité **du travail de la file**, pas une seconde.
        user: Qui l'a demandé.
        task: La tâche créative.
        kind: Ce qui est produit, parmi `GENRES`.
        provenance: D'où sortira l'artefact.
        artifacts: Ce qui a été écrit.
        errors: Ce qui a échoué, tel quel.
        logs: Les traces utiles.
        cost_metadata: Ce que le travail a coûté, quand c'est mesuré.
    """

    job_id: str
    user: str
    task: str
    kind: str
    provenance: Provenance
    artifacts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    logs: List[str] = field(default_factory=list)
    cost_metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "job_id": self.job_id, "user": self.user, "task": self.task,
            "kind": self.kind, "provenance": self.provenance.as_dict(),
            "artifacts": list(self.artifacts), "errors": list(self.errors),
            "logs": list(self.logs), "cost_metadata": dict(self.cost_metadata),
        }


class CreativeJobBook:
    """
    Le registre des travaux créatifs, adossé à `RenderQueue`.

    Il ne remplace pas la file : il l'utilise et note à côté ce qu'elle n'a pas
    vocation à porter. L'état, la progression, les tentatives et l'annulation
    restent chez elle — les redoubler ici créerait deux vérités sur l'avancement
    d'un même travail, et c'est celle qui se désynchronise qu'on lirait.
    """

    def __init__(self, queue: Optional[RenderQueue] = None) -> None:
        """Ouvre un registre, sur la file donnée ou sur une file neuve."""
        self.queue = queue or RenderQueue()
        self._travaux: Dict[str, CreativeJob] = {}

    def submit(
        self, user: str, task: str, provider_id: str, kind: str = "video",
        references: Tuple[str, ...] = (), uses_references: bool = False,
        total_units: Optional[int] = None, priority: int = PRIORITE_NORMALE,
        **provenance: Any,
    ) -> CreativeJob:
        """
        Dépose un travail créatif sur la file existante.

        Args:
            user: Qui demande. Jamais vide — un artefact sans demandeur ne peut
                être ni facturé, ni retiré, ni réclamé.
            task: La tâche créative.
            provider_id: Le fournisseur retenu par le routeur.
            kind: Ce qui est produit, parmi `GENRES`.
            references: Les références qui conditionnent le résultat.
            uses_references: Si le travail se sert de références. Déclaré
                séparément pour que « aucune » et « je n'ai pas rempli le
                champ » ne se confondent pas.
            total_units: Les unités à traiter, si le total est connu.
            priority: La priorité, parmi celles que la file déclare.
            **provenance: Les autres champs de `Provenance`.

        Returns:
            Le travail créatif, dont l'identité **est** celle de la file.

        Raises:
            CreativeJobRefused: Demandeur absent, genre non déclaré, ou travail
                déclarant utiliser des références sans en nommer aucune — ce
                dernier cas produirait un artefact que la révocation d'ADR-025
                ne pourrait jamais atteindre.
        """
        if not str(user or "").strip():
            raise CreativeJobRefused(
                "Travail sans demandeur. L'artefact produit ne pourrait être "
                "ni réclamé, ni retiré, ni imputé."
            )
        if kind not in GENRES:
            raise CreativeJobRefused(
                f"Genre « {kind} » non déclaré. Déclarés : {list(GENRES)}."
            )
        if uses_references and not references:
            raise CreativeJobRefused(
                "Le travail déclare utiliser des références sans en nommer "
                "aucune. L'artefact serait impossible à rattacher, et « retirez "
                "ma photo » ne pourrait plus l'atteindre (ADR-025)."
            )

        depot = self.queue.submit(
            project_id=provenance.pop("project_id", ""),
            kind=task, priority=priority, total_units=total_units,
            reserved=provenance.pop("reserved", None) or {},
        )
        travail = CreativeJob(
            job_id=depot.job_id, user=user, task=task, kind=kind,
            provenance=Provenance(
                provider_id=provider_id, references=tuple(references),
                at=time.time(), **provenance,
            ),
        )
        self._travaux[travail.job_id] = travail
        return travail

    def get(self, job_id: str) -> Optional[CreativeJob]:
        """Le volet créatif d'un travail."""
        return self._travaux.get(job_id)

    def status_of(self, job_id: str) -> RunStatus:
        """
        L'état du travail, **lu depuis la file**.

        Raises:
            CreativeJobRefused: Travail inconnu.
        """
        depot = self.queue.get(job_id)
        if depot is None:
            raise CreativeJobRefused(f"Travail « {job_id} » inconnu de la file.")
        return depot.status

    def record_artifact(
        self, job_id: str, path: str, sha256: str = "",
    ) -> CreativeJob:
        """
        Note un artefact produit et scelle son empreinte d'entrées.

        Raises:
            CreativeJobRefused: Travail inconnu.
        """
        travail = self._travaux.get(job_id)
        if travail is None:
            raise CreativeJobRefused(f"Travail « {job_id} » inconnu.")
        travail.artifacts.append(path)
        if sha256:
            travail.provenance = Provenance(
                **{**travail.provenance.as_dict(),
                   "parameters": dict(travail.provenance.parameters),
                   "references": travail.provenance.references,
                   "inputs_sha256": sha256}
            )
        return travail

    def jobs_using(self, reference_id: str) -> List[str]:
        """
        Les travaux qu'une référence a conditionnés.

        Args:
            reference_id: La référence retirée.

        Returns:
            Leurs identités. C'est ce que la révocation d'ADR-025 doit
            parcourir ; sans cette liste, « supprimez ma photo » ne toucherait
            que la ligne de la référence et laisserait les artefacts en place.
        """
        return sorted(
            identifiant for identifiant, travail in self._travaux.items()
            if reference_id in travail.provenance.references
        )

    def report(self) -> Dict[str, Any]:
        """
        L'état des travaux créatifs, l'avancement venant de la file.

        Returns:
            Les comptes, et le rappel que l'état n'est pas tenu ici.
        """
        etats: Dict[str, int] = {}
        for identifiant in self._travaux:
            depot = self.queue.get(identifiant)
            nom = depot.status.value if depot else "unknown"
            etats[nom] = etats.get(nom, 0) + 1

        avec_references = [t.job_id for t in self._travaux.values()
                           if t.provenance.references]
        return {
            "total": len(self._travaux),
            "by_status": etats,
            "with_references": avec_references,
            "queue": self.queue.report(),
            "note": (
                "L'état, la progression et les tentatives viennent de "
                "`RenderQueue` (§53) : les redoubler ici créerait deux vérités "
                "sur un même travail, et c'est celle qui se désynchronise "
                "qu'on finirait par lire."
            ),
        }
