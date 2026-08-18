"""
Where references live, and why they do not get their own memory system.

Directive §13 asks for a `ReferenceMemory` and adds the constraint that decides
the design: it *must integrate with existing GalSen IA memory systems rather
than creating an isolated competing memory architecture.* This repository has
the receipts for why — a second vocabulary for one idea drifts, and it has paid
for that four times.

So this is a **register with a write-through**, not a store. References live
here; every act on them — created, granted, revoked — is also written into
`src/memory_engine/` as a `MemoryItem` when a manager is supplied. Without one,
the register still works and the report says `integrated: False` rather than
implying a persistence it does not have.

The operation that justifies the whole module is `for_subject()`. A person asks
"delete everything you hold about me". Answering requires knowing which
references depict them and what descends from each — and that question is
unanswerable unless something indexes it deliberately. `revoke_for_subject()`
then walks those references, revokes each, and returns the derived artefacts it
named. It does **not** delete them: it makes the revocation and its reach
visible, so that whoever holds the artefacts can act and be checked.

A reference is `PRIVATE` unless someone explicitly said otherwise (§58). Nothing
migrates to a shared pool by default; the same separation the knowledge base
already holds between private and global.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from .consent import ACTIF, REVOQUE
from .entity import ReferenceEntity

#: La confidentialité d'une référence. `PRIVATE` est le défaut, et le rester
#: est une décision : une référence qui devient partagée sans que personne le
#: décide est exactement le glissement que §58 interdit.
PRIVEE = "PRIVATE"
PARTAGEE = "SHARED"
CONFIDENTIALITES = (PRIVEE, PARTAGEE)


class ReferenceMemoryRefused(ValueError):
    """Une opération de mémoire de références impossible, avec sa raison."""


class ReferenceMemory:
    """
    Le registre des références, adossé à la mémoire de la plateforme.

    Args:
        memory_manager: Le gestionnaire de mémoire de la plateforme. Optionnel :
            sans lui le registre fonctionne et **dit** qu'il n'est pas intégré,
            plutôt que de laisser croire à une persistance inexistante.
    """

    def __init__(self, memory_manager: Any = None) -> None:
        self._verrou = threading.RLock()
        self._references: Dict[str, ReferenceEntity] = {}
        self._confidentialite: Dict[str, str] = {}
        self._memoire = memory_manager
        self._ecritures: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Écriture traversante
    # ------------------------------------------------------------------

    def _ecrire(self, reference: ReferenceEntity, action: str,
                detail: str) -> None:
        """
        Consigne un acte dans la mémoire de la plateforme.

        L'échec d'écriture est **consigné, jamais propagé** : perdre la trace
        d'un acte est grave, mais faire échouer une révocation parce que le
        journal est indisponible le serait davantage.
        """
        entree = {"reference_id": reference.reference_id, "action": action,
                  "detail": detail, "written": False}
        if self._memoire is not None:
            try:
                from ...memory_engine.types import MemoryItem, MemoryType

                item = MemoryItem(
                    id=f"ref-{reference.reference_id}-{action}-{len(self._ecritures)}",
                    content=f"[reference:{reference.reference_id}] {action} — {detail}",
                    memory_type=MemoryType.LONG_TERM,
                    user_id=reference.created_by or None,
                    tags={"kind": "creative_reference", "action": action},
                )
                self._memoire.save_memory(item)
                entree["written"] = True
            except Exception as erreur:
                entree["error"] = f"{type(erreur).__name__}: {erreur}"
        self._ecritures.append(entree)

    @property
    def integrated(self) -> bool:
        """Vrai quand un gestionnaire de mémoire est effectivement branché."""
        return self._memoire is not None

    # ------------------------------------------------------------------
    # Cycle de vie
    # ------------------------------------------------------------------

    def add(self, reference: ReferenceEntity,
            privacy: str = PRIVEE) -> ReferenceEntity:
        """
        Inscrit une référence.

        Args:
            reference: La référence.
            privacy: `PRIVATE` par défaut. Rien ne devient partagé tout seul.

        Raises:
            ReferenceMemoryRefused: Sur une identité déjà prise, ou une
                confidentialité non déclarée.
        """
        if privacy not in CONFIDENTIALITES:
            raise ReferenceMemoryRefused(
                f"Confidentialité « {privacy} » non déclarée. Déclarées : "
                f"{list(CONFIDENTIALITES)}."
            )
        with self._verrou:
            if reference.reference_id in self._references:
                raise ReferenceMemoryRefused(
                    f"« {reference.reference_id} » est déjà inscrite. "
                    "L'écraser ferait disparaître un consentement sans que "
                    "personne le voie."
                )
            self._references[reference.reference_id] = reference
            self._confidentialite[reference.reference_id] = privacy
        self._ecrire(reference, "registered", f"privacy={privacy}")
        return reference

    def get(self, reference_id: str) -> Optional[ReferenceEntity]:
        """Une référence par son identité."""
        with self._verrou:
            return self._references.get(reference_id)

    def privacy_of(self, reference_id: str) -> str:
        """La confidentialité d'une référence."""
        with self._verrou:
            if reference_id not in self._confidentialite:
                raise ReferenceMemoryRefused(
                    f"Référence « {reference_id} » inconnue.")
            return self._confidentialite[reference_id]

    def share(self, reference_id: str, by: str) -> Dict[str, Any]:
        """
        Fait passer une référence en partagé — si son consentement le permet.

        Args:
            reference_id: La référence.
            by: Qui décide du partage.

        Returns:
            La décision et sa raison.

        Raises:
            ReferenceMemoryRefused: Si le consentement ne prévoit pas le
                partage. `may_share` est faux par défaut : partager sans lui
                serait élargir une portée que personne n'a élargie.
        """
        with self._verrou:
            reference = self._references.get(reference_id)
            if reference is None:
                raise ReferenceMemoryRefused(
                    f"Référence « {reference_id} » inconnue.")
            consentement = reference.consent
            if consentement is None or not consentement.may_share:
                raise ReferenceMemoryRefused(
                    f"« {reference_id} » ne peut pas être partagée : "
                    + ("aucun consentement n'existe."
                       if consentement is None else
                       "le consentement ne prévoit pas le partage "
                       "(`may_share` est faux). Partager quand même "
                       "élargirait une portée que personne n'a élargie.")
                )
            self._confidentialite[reference_id] = PARTAGEE
        self._ecrire(reference, "shared", f"by={by}")
        return {"reference_id": reference_id, "privacy": PARTAGEE,
                "shared_by": by}

    # ------------------------------------------------------------------
    # La question qui rend la suppression tenable
    # ------------------------------------------------------------------

    def for_subject(self, subject: str) -> List[ReferenceEntity]:
        """
        Toutes les références qui représentent cette personne.

        Args:
            subject: Le sujet, tel que le consentement le nomme.

        Returns:
            Les références concernées, révoquées comprises. Les omettre
            laisserait croire qu'une révocation a fait disparaître le sujet du
            registre, alors qu'elle a fait l'inverse : elle l'y a inscrit.
        """
        with self._verrou:
            return [r for r in self._references.values()
                    if r.consent is not None and r.consent.subject == subject]

    def revoke_for_subject(
        self, subject: str, by: str, reason: str = "",
        derived: Optional[Dict[str, Tuple[str, ...]]] = None,
    ) -> Dict[str, Any]:
        """
        Retire le consentement sur toutes les références d'une personne.

        Args:
            subject: Le sujet concerné.
            by: Qui retire.
            reason: Pourquoi.
            derived: Par référence, les artefacts connus qui en descendent.

        Returns:
            Ce qui a été révoqué et ce que la révocation **atteint**. Rien
            n'est supprimé ici : la propagation nomme les artefacts pour que
            celui qui les détient puisse agir et être contrôlé. Une suppression
            silencieuse serait invérifiable, et une promesse invérifiable faite
            sur l'image de quelqu'un n'en est pas une.
        """
        descendants = derived or {}
        revoquees, atteints = [], []
        for reference in self.for_subject(subject):
            if reference.state == REVOQUE:
                continue
            enfants = tuple(descendants.get(reference.reference_id, ()))
            reference.revoke(by=by, reason=reason, derived=enfants)
            self._ecrire(reference, "revoked",
                         f"by={by}; derived={len(enfants)}")
            revoquees.append(reference.reference_id)
            atteints.extend(enfants)

        return {
            "subject": subject,
            "revoked": revoquees,
            "derived_reached": sorted(set(atteints)),
            "deleted": [],
            "note": (
                "Aucun fichier n'est supprimé ici. La révocation est "
                "enregistrée et sa portée est **nommée** : une suppression "
                "silencieuse ne serait pas vérifiable, et la personne n'aurait "
                "aucun moyen de savoir si sa demande a été honorée."
            ),
        }

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def usable_for(self, use: str, at_scope: str = "PROJECT") -> List[str]:
        """Les références réellement employables pour cet usage."""
        with self._verrou:
            references = list(self._references.values())
        return [r.reference_id for r in references
                if r.usable(use, at_scope)["allowed"]]

    def report(self) -> Dict[str, Any]:
        """L'état du registre, absences comprises."""
        with self._verrou:
            references = list(self._references.values())
            confidentialite = dict(self._confidentialite)

        sans_consentement = [r.reference_id for r in references
                             if r.consent is None]
        return {
            "count": len(references),
            "by_state": {
                etat: [r.reference_id for r in references if r.state == etat]
                for etat in (ACTIF, REVOQUE, "EXPIRED")
            },
            "by_privacy": {
                niveau: [i for i, p in confidentialite.items() if p == niveau]
                for niveau in CONFIDENTIALITES
            },
            "without_consent": sans_consentement,
            "integrated": self.integrated,
            "writes": len(self._ecritures),
            "writes_failed": [e for e in self._ecritures if not e["written"]],
            "note": (
                "`without_consent` est la liste qui compte : ces références "
                "sont inscrites et **inutilisables**. "
                + ("La mémoire de la plateforme est branchée."
                   if self.integrated else
                   "Aucun gestionnaire de mémoire n'est branché : rien n'est "
                   "persisté, et le dire vaut mieux que le laisser supposer.")
            ),
        }


def reference_memory_report() -> Dict[str, Any]:
    """
    Ce que la mémoire de références garantit, et ce qu'elle refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "privacy_levels": list(CONFIDENTIALITES),
        "rules": [
            "Le registre **s'adosse** à la mémoire de la plateforme : une "
            "seconde architecture de mémoire finirait par diverger de la "
            "première.",
            "`PRIVATE` est le défaut. Rien ne devient partagé sans un "
            "consentement qui le prévoit (`may_share`).",
            "`for_subject()` existe pour qu'une personne puisse demander ce "
            "qu'on détient d'elle — sans cet index, la question n'a pas de "
            "réponse.",
            "Une révocation **nomme** ce qu'elle atteint et ne supprime rien "
            "en silence : une suppression invérifiable n'est pas une promesse.",
            "Une référence révoquée reste au registre : la révocation l'y "
            "inscrit, elle ne l'en retire pas.",
            "Un échec d'écriture dans le journal est consigné, jamais propagé : "
            "une révocation ne doit pas échouer parce que le journal est "
            "indisponible.",
        ],
        "does_not": [
            "Créer un magasin de mémoire concurrent.",
            "Partager une référence sans consentement explicite.",
            "Supprimer des fichiers en silence.",
            "Retirer une référence révoquée du registre.",
        ],
    }
