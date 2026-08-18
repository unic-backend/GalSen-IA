"""
Where a production survives the process that made it — ADR-005, not a new rule.

The storage decision was already taken and already has exactly one place that
makes it: `src/storage/paths.py`. Eight managers used to re-read the backend
environment variable themselves, and the repository paid four times for the
divergence that followed. So this store asks that module — `sqlite_enabled()`,
`storage_backend()` — and adds no second switch.

(`tests/test_persistence_deployment.py` enforces that by grepping for the
literal call, so this file must not even quote it in prose. A guard that cannot
be fooled by a docstring is worth more than a docstring that reads well.)

What it does add is the consequence of §18's rule at the persistence layer.
`MediaProject` cannot destroy a version in memory; a store that can destroy one
on disk would give the whole guarantee back. So:

- **There is no delete method**, here either.
- **A save is append-only in effect**: writing a project rewrites its rows from
  the in-memory object, which itself never loses a version. A version that
  existed at save N still exists at save N+1.
- **A round trip is lossless or it fails.** Saving then loading must return the
  same versions with the same content hashes. A store that silently drops a
  field would let a production come back subtly different from the one that was
  approved — the failure mode this whole module exists to prevent, arriving
  through the back door.

The in-memory backend is not a stub: it is what the platform runs by default
(`in-memory`), and it holds the same contract. `sqlite` persists.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from typing import Any, Dict, List, Optional

from ...storage.paths import (
    default_sqlite_path,
    prepare_connection,
    secure_database_file,
    sqlite_enabled,
    storage_backend,
)
from .project import (
    Artifact,
    Correction,
    MediaProject,
    ProjectVersion,
    VersionStatus,
)

#: Le fichier SQLite du moteur média, dans le répertoire de données déclaré.
FICHIER = "media_projects.sqlite"


class ProjectStoreError(RuntimeError):
    """Un enregistrement ou une relecture qui ne peut pas être honoré."""


# ----------------------------------------------------------------------
# Sérialisation
# ----------------------------------------------------------------------

def to_record(project: MediaProject) -> Dict[str, Any]:
    """
    Réduit une production à ce qu'un magasin doit conserver.

    Args:
        project: La production.

    Returns:
        Toutes ses versions, ses corrections et son journal. Rien n'est élagué :
        un magasin qui ne garderait que la version courante rendrait la règle
        « ne jamais détruire » fausse dès le premier redémarrage.
    """
    return {
        "project_id": project.project_id,
        "objective": project.objective,
        "created_at": project.created_at,
        "created_by": project.created_by,
        "versions": [v.as_dict() for v in project.versions],
        "corrections": [
            {"at": c.at, "by": c.by, "target": c.target, "before": c.before,
             "after": c.after, "note": c.note}
            for c in project.corrections
        ],
    }


def from_record(record: Dict[str, Any]) -> MediaProject:
    """
    Reconstruit une production depuis un enregistrement.

    Args:
        record: L'enregistrement rendu par `to_record`.

    Returns:
        La production, **avec toutes ses versions**, dans leur ordre et leur
        état d'origine.

    Raises:
        ProjectStoreError: Si l'enregistrement ne porte aucune version. Une
            production sans version est un objet que rien ne peut afficher, et
            en fabriquer une masquerait la perte.
    """
    versions = record.get("versions") or []
    if not versions:
        raise ProjectStoreError(
            f"Aucune version dans l'enregistrement « "
            f"{record.get('project_id', '?')} ». En fabriquer une masquerait "
            "la perte au lieu de la signaler."
        )

    projet = MediaProject(
        objective=record["objective"],
        project_id=record["project_id"],
        created_by=record.get("created_by", ""),
    )
    projet.created_at = record.get("created_at", projet.created_at)

    # La version créée par le constructeur est remplacée par celles qui ont été
    # conservées : les garder toutes est le point de ce magasin.
    projet._versions = [_version_depuis(entree) for entree in versions]
    projet._corrections = [
        Correction(**entree) for entree in record.get("corrections", [])
    ]
    return projet


def _version_depuis(entree: Dict[str, Any]) -> ProjectVersion:
    """Reconstruit une version, artefacts compris."""
    artefacts = tuple(
        Artifact(
            artifact_id=a["artifact_id"], kind=a["kind"], path=a.get("path", ""),
            origin=a["origin"], source=a.get("source", ""),
            licence=a.get("licence", ""), sha256=a.get("sha256", ""),
            produced_by=a.get("produced_by", ""),
        )
        for a in entree.get("artifacts", [])
    )
    return ProjectVersion(
        version_id=entree["version_id"],
        number=entree["number"],
        status=VersionStatus(entree["status"]),
        objective=entree.get("objective", ""),
        script=entree.get("script", ""),
        scenes=tuple(entree.get("scenes", ())),
        timeline=tuple(entree.get("timeline", ())),
        artifacts=artefacts,
        models=dict(entree.get("models", {})),
        prompts=dict(entree.get("prompts", {})),
        quality_checks=tuple(entree.get("quality_checks", ())),
        outputs=tuple(entree.get("outputs", ())),
        created_at=entree.get("created_at", 0.0),
        created_by=entree.get("created_by", ""),
        derived_from=entree.get("derived_from", ""),
    )


# ----------------------------------------------------------------------
# Les magasins
# ----------------------------------------------------------------------

class InMemoryProjectStore:
    """
    Le magasin par défaut de la plateforme (`in-memory`).

    Ce n'est pas un bouchon : c'est ce que tourne une installation qui n'a pas
    demandé `sqlite`, et il tient le même contrat — dont l'absence de
    suppression.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._projets: Dict[str, Dict[str, Any]] = {}

    @property
    def backend(self) -> str:
        """Le nom du magasin."""
        return "in-memory"

    def save(self, project: MediaProject) -> str:
        """Enregistre une production, versions comprises."""
        with self._verrou:
            self._projets[project.project_id] = to_record(project)
        return project.project_id

    def load(self, project_id: str) -> Optional[MediaProject]:
        """Relit une production, ou `None` si elle est inconnue."""
        with self._verrou:
            enregistrement = self._projets.get(project_id)
        return from_record(enregistrement) if enregistrement else None

    def list_projects(self) -> List[str]:
        """Les identités connues, triées."""
        with self._verrou:
            return sorted(self._projets)


class SQLiteProjectStore:
    """
    Le magasin persistant, sur le chemin déclaré par ADR-005.

    Aucune suppression n'est exposée. Le schéma garde l'enregistrement complet
    en JSON plutôt qu'éclaté en colonnes : une version porte des scènes, une
    timeline et des artefacts de formes variées, et les aplatir aujourd'hui
    imposerait une migration à chaque volet suivant.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._chemin = db_path or default_sqlite_path(FICHIER)
        self._verrou = threading.RLock()
        dossier = os.path.dirname(self._chemin)
        if dossier:
            os.makedirs(dossier, exist_ok=True)
        self._preparer()

    @property
    def backend(self) -> str:
        """Le nom du magasin."""
        return "sqlite"

    @property
    def path(self) -> str:
        """Le fichier employé."""
        return self._chemin

    def _connexion(self) -> sqlite3.Connection:
        """Une connexion préparée selon les réglages de la plateforme."""
        return prepare_connection(sqlite3.connect(self._chemin))

    def _preparer(self) -> None:
        """Crée le schéma s'il manque."""
        with self._verrou, self._connexion() as connexion:
            connexion.execute(
                "CREATE TABLE IF NOT EXISTS media_projects ("
                " project_id TEXT PRIMARY KEY,"
                " objective TEXT NOT NULL,"
                " created_at REAL NOT NULL,"
                " version_count INTEGER NOT NULL,"
                " record TEXT NOT NULL)"
            )
        secure_database_file(self._chemin)

    def save(self, project: MediaProject) -> str:
        """
        Enregistre une production.

        La réécriture est intégrale et vient d'un objet qui ne perd jamais de
        version : le nombre de versions ne peut donc que croître. Le compte est
        stocké à part pour qu'une perte se voie dans une simple requête.
        """
        enregistrement = to_record(project)
        with self._verrou, self._connexion() as connexion:
            connexion.execute(
                "INSERT INTO media_projects"
                " (project_id, objective, created_at, version_count, record)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(project_id) DO UPDATE SET"
                " objective=excluded.objective,"
                " version_count=excluded.version_count,"
                " record=excluded.record",
                (project.project_id, project.objective, project.created_at,
                 len(enregistrement["versions"]),
                 json.dumps(enregistrement, ensure_ascii=False)),
            )
        return project.project_id

    def load(self, project_id: str) -> Optional[MediaProject]:
        """Relit une production, ou `None` si elle est inconnue."""
        with self._verrou, self._connexion() as connexion:
            ligne = connexion.execute(
                "SELECT record FROM media_projects WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if ligne is None:
            return None
        return from_record(json.loads(ligne[0]))

    def list_projects(self) -> List[str]:
        """Les identités connues, triées."""
        with self._verrou, self._connexion() as connexion:
            lignes = connexion.execute(
                "SELECT project_id FROM media_projects ORDER BY project_id",
            ).fetchall()
        return [ligne[0] for ligne in lignes]


def project_store(db_path: Optional[str] = None) -> Any:
    """
    Le magasin choisi par la configuration (ADR-005).

    Args:
        db_path: Un fichier SQLite explicite, pour les tests.

    Returns:
        `SQLiteProjectStore` quand `GALSEN_STORAGE_BACKEND=sqlite`, sinon
        `InMemoryProjectStore`. La décision vient de `src/storage/paths.py` —
        la réécrire ici ferait un neuvième endroit où la même règle peut
        diverger.
    """
    if db_path is not None or sqlite_enabled():
        return SQLiteProjectStore(db_path)
    return InMemoryProjectStore()


def store_report() -> Dict[str, Any]:
    """
    Ce que le magasin garantit, et ce qu'il refuse.

    Returns:
        Le magasin actif et les règles tenues.
    """
    return {
        "backend": storage_backend(),
        "sqlite_file": FICHIER,
        "rules": [
            "La décision du magasin vient d'ADR-005 (`src/storage/paths.py`) : "
            "aucun second interrupteur n'est créé ici.",
            "Aucune suppression n'est exposée. Un magasin qui pourrait détruire "
            "une version sur disque rendrait toute la garantie mémoire vaine.",
            "Un aller-retour est **sans perte** : mêmes versions, mêmes "
            "empreintes de contenu. Une production qui revient subtilement "
            "différente de celle qui a été approuvée est exactement l'échec que "
            "ce module empêche.",
            "Un enregistrement sans version est **refusé** : en fabriquer une "
            "masquerait la perte au lieu de la signaler.",
            "`in-memory` n'est pas un bouchon : c'est le défaut de la "
            "plateforme, et il tient le même contrat.",
        ],
        "does_not": [
            "Supprimer une production ou une version.",
            "Ne conserver que la version courante.",
            "Décider du magasin autrement que par `GALSEN_STORAGE_BACKEND`.",
        ],
    }
