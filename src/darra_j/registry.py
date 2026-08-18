"""
Keeping every official version, and never quietly replacing one.

A curriculum register has one job that a normal store does not: **it must be
unable to lose history.** When a ministry publishes the 2027 programme, the 2026
one does not become wrong — it becomes *the programme of 2026*, and a question
about that year must still return it. So this register is append-only by
construction:

- **Registering an existing version identifier with different content is
  refused.** Not merged, not overwritten — refused, naming both hashes. Silent
  replacement is the one failure that leaves no evidence it happened.
- **Publishing supersedes rather than deletes.** The previous version moves to
  `SUPERSEDED` and stays queryable. Deletion is not offered by this module at
  all: there is no method to call in a moment of confidence.
- **A version is answerable only when it is official.** The three conditions —
  canonical state, official tier, not a fixture — are checked at read time too,
  because a store that trusts what was written to it is a store that will one day
  serve a fixture as ministry policy.

Resolution follows the same rule the rest of the platform already applies:
`UNKNOWN` when nothing matches, `AMBIGUOUS` when several do. Never a pick.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from .canonical import (
    ETATS_CANONIQUES,
    CanonicalRefused,
    CurriculumStatus,
    CurriculumUnit,
    CurriculumVersion,
    may_transition,
)

#: Ce qu'une résolution peut répondre. `AMBIGUOUS` est une réponse à part
#: entière : choisir au hasard parmi plusieurs versions officielles serait la
#: pire des trois issues, parce qu'elle se lit comme une certitude.
TROUVE = "FOUND"
INCONNU = "UNKNOWN"
AMBIGU = "AMBIGUOUS"


class RegistryRefused(ValueError):
    """Une opération que le registre refuse, avec sa cause."""


class CurriculumRegistry:
    """
    Les versions officielles et leurs unités, sans perte possible.

    En mémoire, thread-safe, et **sans méthode de suppression** : le contrat de
    persistance de la plateforme (ADR-005) s'appliquera de la même façon, et
    `registry_report()` dit clairement que rien n'est encore persisté.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._versions: Dict[str, CurriculumVersion] = {}
        self._unites: Dict[str, CurriculumUnit] = {}
        #: Index par dimensions, pour la résolution déterministe du VOLET 4.
        self._par_dimensions: Dict[Tuple[str, str, str], List[str]] = {}
        self._journal: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Écrire
    # ------------------------------------------------------------------

    def register_version(self, version: CurriculumVersion) -> CurriculumVersion:
        """
        Inscrit une version, ou refuse de la remplacer.

        Args:
            version: La version à inscrire.

        Returns:
            La version inscrite, ou celle qui existait déjà si elle est
            identique — réinscrire à l'identique est sans effet, pas une erreur.

        Raises:
            RegistryRefused: Si une version du même identifiant existe avec un
                **contenu différent**. Les deux empreintes sont nommées : sans
                elles, personne ne peut dire ce qui a changé.
        """
        with self._verrou:
            existante = self._versions.get(version.version_id)
            if existante is not None:
                if existante.content_hash() == version.content_hash():
                    return existante
                raise RegistryRefused(
                    f"La version « {version.version_id} » existe déjà avec un "
                    f"contenu différent ({existante.content_hash()[:12]}… contre "
                    f"{version.content_hash()[:12]}…). Une version officielle ne "
                    "se remplace pas en silence : publiez-en une nouvelle, qui "
                    "remplacera celle-ci en la laissant lisible."
                )
            self._versions[version.version_id] = version
            self._consigner("version_registered", version.version_id,
                            statut=version.status.value)
            return version

    def advance(
        self, version_id: str, vers: CurriculumStatus, decided_by: str = "",
    ) -> CurriculumVersion:
        """
        Fait avancer une version dans sa machine d'états.

        Args:
            version_id: La version.
            vers: L'état visé.
            decided_by: Qui décide. Exigé pour publier : une publication
                anonyme ne peut être ni contestée ni confirmée.

        Returns:
            La version dans son nouvel état.

        Raises:
            RegistryRefused: Version inconnue, transition interdite, ou
                publication sans décideur nommé.
        """
        with self._verrou:
            version = self._exiger(version_id)
            permise, motif = may_transition(version.status, vers)
            if not permise:
                raise RegistryRefused(f"« {version_id} » : {motif}")

            if vers is CurriculumStatus.PUBLISHED and not str(decided_by).strip():
                raise RegistryRefused(
                    f"Publier « {version_id} » exige de nommer qui décide. Une "
                    "publication anonyme ne peut être ni contestée ni confirmée, "
                    "et l'autorité institutionnelle reste humaine."
                )

            import dataclasses
            import time

            remplacee = dataclasses.replace(
                version, status=vers,
                published_at=time.time() if vers is CurriculumStatus.PUBLISHED
                else version.published_at,
            )
            self._versions[version_id] = remplacee
            self._consigner(
                "version_advanced", version_id,
                de=version.status.value, vers=vers.value, decided_by=decided_by,
            )
            return remplacee

    def publish(
        self, version_id: str, decided_by: str, supersedes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Publie une version, en remplaçant la précédente **sans la détruire**.

        Args:
            version_id: La version à publier.
            decided_by: Qui décide.
            supersedes: La version remplacée. Déduite de l'année scolaire si
                elle n'est pas nommée.

        Returns:
            La version publiée et celle qui a été remplacée, s'il y en a une.

        Raises:
            RegistryRefused: Si la transition est interdite ou le décideur absent.
        """
        with self._verrou:
            version = self._exiger(version_id)
            ancienne_id = supersedes
            if ancienne_id is None:
                courantes = [
                    autre for autre in self._versions.values()
                    if autre.version_id != version_id
                    and autre.academic_year == version.academic_year
                    and autre.status is CurriculumStatus.PUBLISHED
                ]
                ancienne_id = courantes[0].version_id if len(courantes) == 1 else None

            publiee = self.advance(version_id, CurriculumStatus.PUBLISHED, decided_by)
            remplacee = None
            if ancienne_id:
                # `SUPERSEDED`, jamais supprimée : une question sur l'année
                # passée doit encore trouver ce que l'autorité disait alors.
                remplacee = self.advance(ancienne_id, CurriculumStatus.SUPERSEDED)

            return {
                "published": publiee.as_dict(),
                "superseded": remplacee.as_dict() if remplacee else None,
                "decided_by": decided_by,
            }

    def add_unit(self, unit: CurriculumUnit) -> CurriculumUnit:
        """
        Ajoute une unité à une version.

        Args:
            unit: L'unité.

        Returns:
            L'unité inscrite, ou l'identique déjà présente.

        Raises:
            RegistryRefused: Si la version est inconnue, déjà publiée, ou si une
                unité de même identité porte un contenu différent.
        """
        with self._verrou:
            version = self._exiger(unit.version_id)
            if version.status in ETATS_CANONIQUES:
                raise RegistryRefused(
                    f"La version « {unit.version_id} » est {version.status.value} : "
                    "on n'ajoute pas une unité à un curriculum en vigueur. Ce "
                    "serait modifier l'officiel sans que rien ne le dise."
                )

            existante = self._unites.get(unit.unit_id)
            if existante is not None:
                if existante.content_hash() == unit.content_hash():
                    return existante
                raise RegistryRefused(
                    f"L'unité « {unit.unit_id} » existe avec un contenu différent. "
                    "Même version, même niveau, même matière, même période : deux "
                    "textes officiels contradictoires sont un **conflit**, pas un "
                    "remplacement."
                )

            self._unites[unit.unit_id] = unit
            cle = (unit.version_id, unit.grade.grade_id, unit.subject.subject_id)
            self._par_dimensions.setdefault(cle, []).append(unit.unit_id)
            self._consigner("unit_added", unit.unit_id, version=unit.version_id)
            return unit

    # ------------------------------------------------------------------
    # Lire
    # ------------------------------------------------------------------

    def get_version(self, version_id: str) -> Optional[CurriculumVersion]:
        """Retourne une version, ou `None`."""
        with self._verrou:
            return self._versions.get(version_id)

    def get_unit(self, unit_id: str) -> Optional[CurriculumUnit]:
        """Retourne une unité, ou `None`."""
        with self._verrou:
            return self._unites.get(unit_id)

    def versions_for(self, academic_year: str) -> List[CurriculumVersion]:
        """Toutes les versions d'une année scolaire, quel que soit leur état."""
        with self._verrou:
            return sorted(
                (v for v in self._versions.values() if v.academic_year == academic_year),
                key=lambda v: v.version_id,
            )

    def resolve_version(
        self, academic_year: str, version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Trouve la version qui fait autorité pour une année scolaire.

        Args:
            academic_year: L'année scolaire.
            version_id: Une version explicitement demandée — une question
                historique nomme la sienne.

        Returns:
            `FOUND` avec la version, `UNKNOWN` si rien ne correspond, ou
            `AMBIGUOUS` si plusieurs versions officielles sont en vigueur pour
            la même année. **Aucune n'est choisie au hasard** : deux
            curriculums officiels simultanés sont un problème institutionnel,
            et le masquer par un tri arbitraire le rendrait invisible.
        """
        with self._verrou:
            if version_id:
                version = self._versions.get(version_id)
                if version is None:
                    return {"status": INCONNU, "version": None,
                            "reason": f"Version « {version_id} » inconnue."}
                if not version.is_official:
                    return {
                        "status": INCONNU, "version": None,
                        "reason": (
                            f"Version « {version_id} » non officielle "
                            f"(état {version.status.value}, rang "
                            f"{version.provenance.source_tier}). Elle existe, "
                            "mais elle ne fait pas autorité."
                        ),
                    }
                return {"status": TROUVE, "version": version,
                        "reason": "Version explicitement demandée."}

            candidates = [
                v for v in self.versions_for(academic_year)
                if v.status is CurriculumStatus.PUBLISHED and v.is_official
            ]
            if not candidates:
                return {
                    "status": INCONNU, "version": None,
                    "reason": (
                        f"Aucune version officielle publiée pour « {academic_year} ». "
                        "Le curriculum canonique est vide tant qu'une autorité "
                        "n'a rien fourni — et c'est l'état attendu aujourd'hui."
                    ),
                }
            if len(candidates) > 1:
                return {
                    "status": AMBIGU, "version": None,
                    "candidates": [v.version_id for v in candidates],
                    "reason": (
                        f"{len(candidates)} versions officielles en vigueur pour "
                        f"« {academic_year} ». Aucune n'est choisie : deux "
                        "curriculums officiels simultanés sont un problème "
                        "institutionnel, et en masquer un le rendrait invisible."
                    ),
                }
            return {"status": TROUVE, "version": candidates[0],
                    "reason": "Seule version officielle en vigueur."}

    def units_of(
        self, version_id: str, grade_id: str, subject_id: str,
    ) -> List[CurriculumUnit]:
        """Les unités d'une version, pour un niveau et une matière."""
        with self._verrou:
            identifiants = self._par_dimensions.get((version_id, grade_id, subject_id), [])
            return [self._unites[i] for i in identifiants if i in self._unites]

    def units_in_version(self, version_id: str) -> List[CurriculumUnit]:
        """
        Toutes les unités d'une version, triées par identifiant.

        Le tri est là pour que deux constructions du même graphe donnent le
        même résultat : un ordre qui dépend de l'ordre d'insertion rendrait les
        rapports incomparables d'une exécution à l'autre.

        Args:
            version_id: La version.

        Returns:
            Ses unités, ou une liste vide si la version n'en porte aucune.
        """
        with self._verrou:
            return sorted(
                (u for u in self._unites.values() if u.version_id == version_id),
                key=lambda unite: unite.unit_id,
            )

    def provenance_of(self, unit_id: str) -> Dict[str, Any]:
        """
        Répond à « d'où vient exactement ce fait de curriculum ? ».

        Args:
            unit_id: L'unité.

        Returns:
            La chaîne complète : unité → version → autorité → document, avec les
            empreintes. `UNKNOWN` si l'unité est inconnue — jamais une chaîne
            partielle qui se lirait comme une réponse.
        """
        with self._verrou:
            unite = self._unites.get(unit_id)
            if unite is None:
                return {"status": INCONNU, "unit_id": unit_id,
                        "reason": "Unité inconnue du registre."}
            version = self._versions.get(unite.version_id)

        return {
            "status": TROUVE,
            "unit": {
                "unit_id": unite.unit_id,
                "official_title": unite.official_title,
                "content_hash": unite.content_hash(),
            },
            "version": version.as_dict() if version else None,
            "authority": unite.provenance.authority,
            "source_document": unite.provenance.source_document,
            "source_tier": unite.provenance.source_tier,
            "document_hash": unite.provenance.document_hash,
            "publication_date": unite.provenance.publication_date,
            "effective_date": unite.provenance.effective_date,
            "extraction_method": unite.provenance.extraction_method,
            "is_official": bool(version and version.is_official),
        }

    # ------------------------------------------------------------------
    # Journal et rapport
    # ------------------------------------------------------------------

    def _consigner(self, action: str, cible: str, **details: Any) -> None:
        """Consigne une écriture du registre."""
        import time

        self._journal.append({
            "at": time.time(), "action": action, "target": cible, **details,
        })

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Les dernières écritures du registre, de la plus récente."""
        with self._verrou:
            return list(reversed(self._journal))[: max(1, int(limit))]

    def _exiger(self, version_id: str) -> CurriculumVersion:
        """Retourne une version ou refuse."""
        version = self._versions.get(version_id)
        if version is None:
            raise RegistryRefused(f"Version « {version_id} » inconnue du registre.")
        return version

    def registry_report(self) -> Dict[str, Any]:
        """
        L'état du registre, sans rien arrondir.

        Returns:
            Les décomptes, ce qui est officiel, et les règles tenues.
        """
        with self._verrou:
            versions = list(self._versions.values())
            unites = list(self._unites.values())

        par_etat: Dict[str, int] = {}
        for version in versions:
            par_etat[version.status.value] = par_etat.get(version.status.value, 0) + 1

        officielles = [v for v in versions if v.is_official]
        return {
            "versions": len(versions),
            "official_versions": len(officielles),
            "units": len(unites),
            "by_status": dict(sorted(par_etat.items())),
            "persisted": False,
            "persistence_note": (
                "Registre en mémoire. La persistance suivra le contrat existant "
                "(ADR-005, `GALSEN_STORAGE_BACKEND`) ; le dire vaut mieux que de "
                "laisser croire qu'un redémarrage conserve une version officielle."
            ),
            "rules": [
                "Réinscrire un identifiant avec un contenu différent est "
                "**refusé**, les deux empreintes nommées : le remplacement "
                "silencieux est la seule panne qui ne laisse aucune trace.",
                "Publier remplace sans détruire : la version précédente passe "
                "`SUPERSEDED` et reste interrogeable.",
                "Aucune méthode de suppression n'existe — il n'y a rien à "
                "appeler dans un moment de confiance.",
                "Publier exige de nommer qui décide : l'autorité "
                "institutionnelle reste humaine.",
                "Deux versions officielles simultanées rendent `AMBIGUOUS`, "
                "jamais un choix : en masquer une la rendrait invisible.",
                "Une version non officielle **existe** sans faire autorité : "
                "elle est lisible, elle ne répond pas.",
            ],
            "does_not": [
                "Contenir le moindre curriculum officiel aujourd'hui : "
                "ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING.",
                "Choisir entre deux textes officiels contradictoires : c'est un "
                "conflit, et il appartient à une autorité.",
            ],
        }


def unit_refusal_rules() -> List[str]:
    """Ce qu'un ajout d'unité ne peut pas faire, pour la documentation."""
    return [
        "Ajouter une unité à une version publiée : ce serait modifier "
        "l'officiel sans que rien ne le dise.",
        "Écraser une unité de même identité par un autre texte : deux textes "
        "officiels contradictoires sont un conflit, pas un remplacement.",
        "Créer une unité sans provenance : refusé dès la construction "
        "(`CanonicalRefused`).",
    ]


__all__ = [
    "AMBIGU",
    "INCONNU",
    "TROUVE",
    "CanonicalRefused",
    "CurriculumRegistry",
    "RegistryRefused",
    "unit_refusal_rules",
]
