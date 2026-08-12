"""
Capture du signal (VOLET 33, ch. 01).

C'est le seul chapitre de toute la série dont **le coût augmente chaque jour où
il n'est pas fait**. Une correction d'utilisateur non enregistrée est perdue pour
toujours ; tout le reste — l'évaluation, la recette d'entraînement, la
conversion — peut être construit plus tard sans rien perdre.

Ce que l'on garde, et pourquoi chaque champ existe :

- **l'invite et la réponse**, sans quoi la correction ne se rattache à rien ;
- **la correction ou la préférence**, qui est le signal lui-même ;
- **le modèle et la route**, parce qu'une préférence n'a de sens que rapportée à
  ce qui a produit la réponse ;
- **le sujet** (ADR-010), parce qu'une correction appartient à qui l'a écrite.

Trois règles, et elles ne sont pas négociables :

1. **Le consentement est demandé, jamais supposé.** Un retour n'entre dans le jeu
   d'entraînement que si son auteur l'a permis. Sans consentement, il reste
   utilisable pour corriger *cette* réponse et rien d'autre.
2. **Les données personnelles sont écartées à la capture**, pas à l'export.
   Filtrer plus tard signifie qu'elles ont été écrites sur le disque.
3. **L'export pour entraînement passe par le portillon** (ADR-006). Sortir le
   texte de vraies personnes vers un jeu de données est une décision humaine.
"""

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "training_feedback.sqlite"

# Motifs retirés du texte **avant écriture**. La liste est courte et ne prétend
# pas à l'exhaustivité : elle couvre ce qui apparaît réellement dans une
# conversation — un numéro, un e-mail, une carte. Ce qu'elle ne couvre pas est
# la raison pour laquelle le consentement existe aussi.
MOTIFS_PERSONNELS = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[courriel]"),
    # Numéros sénégalais : neuf chiffres commençant par 7 (mobile) ou 3 (fixe),
    # écrits « 77 123 45 67 », « 771234567 » ou « +221 77 123 45 67 ».
    # Un motif par groupes de deux chiffres ne les attrapait pas — c'est le
    # découpage 2-3-2-2 qui est employé ici, et c'est le seul qui compte.
    (re.compile(r"(?:\+221|00221)?\s?\b[37]\d(?:[ .\-]?\d){7}\b"), "[téléphone]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[numéro long]"),
)


class FeedbackKind(Enum):
    """Nature du signal recueilli."""

    CORRECTION = "correction"      # l'utilisateur a réécrit la réponse
    PREFERENCE = "preference"      # une réponse a été préférée à une autre
    RATING = "rating"              # une note, sans texte
    REPORT = "report"              # la réponse est signalée comme fausse ou nuisible


@dataclass
class Feedback:
    """Un retour utilisateur sur une réponse de la plateforme."""

    prompt: str
    response: str
    kind: FeedbackKind = FeedbackKind.RATING
    correction: Optional[str] = None
    rejected_response: Optional[str] = None
    rating: Optional[int] = None
    model_name: str = ""
    route: str = ""
    subject: str = "anonymous"
    consent_to_train: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"fb_{uuid.uuid4().hex[:12]}")
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le retour."""
        return {
            "id": self.id,
            "kind": self.kind.value,
            "prompt": self.prompt,
            "response": self.response,
            "correction": self.correction,
            "rejected_response": self.rejected_response,
            "rating": self.rating,
            "model_name": self.model_name,
            "route": self.route,
            "subject": self.subject,
            "consent_to_train": self.consent_to_train,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


def scrub(texte: Optional[str]) -> Optional[str]:
    """
    Retire les données personnelles évidentes d'un texte.

    Appliqué **à l'écriture**. Filtrer à l'export voudrait dire que le numéro de
    téléphone a été écrit sur le disque, sauvegardé, et copié hors site.
    """
    if not texte:
        return texte
    nettoye = texte
    for motif, remplacement in MOTIFS_PERSONNELS:
        nettoye = motif.sub(remplacement, nettoye)
    return nettoye


class FeedbackStore:
    """Contrat d'un magasin de retours."""

    def record(self, feedback: Feedback) -> str:
        """Enregistre un retour et retourne son identifiant."""
        raise NotImplementedError

    def list_feedback(self, **filtres) -> List[Feedback]:
        """Retourne les retours correspondant aux filtres."""
        raise NotImplementedError

    def stats(self) -> Dict[str, Any]:
        """Retourne l'état du magasin."""
        raise NotImplementedError


class SQLiteFeedbackStore(FeedbackStore):
    """
    Magasin de retours persistant.

    Exemple:
        magasin = SQLiteFeedbackStore()
        magasin.record(Feedback(prompt="...", response="...", correction="..."))
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Fichier SQLite ; `GALSEN_DATA_DIR/training_feedback.sqlite`
                par défaut.
        """
        self.db_path = db_path or default_sqlite_path(DEFAULT_FILENAME)
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._lock = threading.RLock()
        self._memoire: Optional[sqlite3.Connection] = None
        self._initialiser()
        secure_database_file(self.db_path)

    def _connexion(self) -> sqlite3.Connection:
        """Ouvre une connexion réglée comme les autres bases (ADR-005)."""
        if self.db_path == ":memory:":
            if self._memoire is None:
                self._memoire = prepare_connection(sqlite3.connect(":memory:", check_same_thread=False))
            return self._memoire
        return prepare_connection(sqlite3.connect(self.db_path))

    def _initialiser(self) -> None:
        """Crée le schéma."""
        with self._lock:
            connexion = self._connexion()
            connexion.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id                TEXT PRIMARY KEY,
                    kind              TEXT NOT NULL,
                    prompt            TEXT NOT NULL,
                    response          TEXT NOT NULL,
                    correction        TEXT,
                    rejected_response TEXT,
                    rating            INTEGER,
                    model_name        TEXT NOT NULL DEFAULT '',
                    route             TEXT NOT NULL DEFAULT '',
                    subject           TEXT NOT NULL DEFAULT 'anonymous',
                    consent_to_train  INTEGER NOT NULL DEFAULT 0,
                    metadata          TEXT NOT NULL DEFAULT '{}',
                    created_at        REAL NOT NULL
                )
                """
            )
            connexion.execute(
                "CREATE INDEX IF NOT EXISTS idx_feedback_consent "
                "ON feedback(consent_to_train, kind)"
            )
            connexion.commit()

    def record(self, feedback: Feedback) -> str:
        """
        Enregistre un retour, après nettoyage des données personnelles.

        Args:
            feedback: Le retour à conserver.

        Returns:
            L'identifiant du retour.
        """
        with self._lock:
            connexion = self._connexion()
            connexion.execute(
                "INSERT OR REPLACE INTO feedback VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    feedback.id,
                    feedback.kind.value,
                    scrub(feedback.prompt),
                    scrub(feedback.response),
                    scrub(feedback.correction),
                    scrub(feedback.rejected_response),
                    feedback.rating,
                    feedback.model_name,
                    feedback.route,
                    feedback.subject,
                    1 if feedback.consent_to_train else 0,
                    json.dumps(feedback.metadata),
                    feedback.created_at,
                ),
            )
            connexion.commit()
        return feedback.id

    def list_feedback(
        self,
        kind: Optional[FeedbackKind] = None,
        subject: Optional[str] = None,
        consent_only: bool = False,
        limit: int = 1000,
    ) -> List[Feedback]:
        """
        Retourne les retours correspondant aux filtres.

        Args:
            kind: Nature du signal.
            subject: Sujet propriétaire (ADR-010).
            consent_only: Ne rendre que ce qui peut servir à l'entraînement.
            limit: Nombre maximal de retours.
        """
        conditions, parametres = [], []
        if kind is not None:
            conditions.append("kind = ?")
            parametres.append(kind.value)
        if subject is not None:
            conditions.append("subject = ?")
            parametres.append(subject)
        if consent_only:
            conditions.append("consent_to_train = 1")

        requete = "SELECT * FROM feedback"
        if conditions:
            requete += " WHERE " + " AND ".join(conditions)
        requete += " ORDER BY created_at DESC LIMIT ?"
        parametres.append(limit)

        with self._lock:
            lignes = self._connexion().execute(requete, parametres).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    @staticmethod
    def _depuis_ligne(ligne) -> Feedback:
        """Reconstruit un retour depuis une ligne SQLite."""
        return Feedback(
            id=ligne[0],
            kind=FeedbackKind(ligne[1]),
            prompt=ligne[2],
            response=ligne[3],
            correction=ligne[4],
            rejected_response=ligne[5],
            rating=ligne[6],
            model_name=ligne[7],
            route=ligne[8],
            subject=ligne[9],
            consent_to_train=bool(ligne[10]),
            metadata=json.loads(ligne[11]),
            created_at=ligne[12],
        )

    def stats(self) -> Dict[str, Any]:
        """
        Retourne ce que la capture a réellement recueilli.

        Le nombre de paires **utilisables pour l'entraînement** est le chiffre
        qui compte : c'est lui qui dira, dans quelques mois, si un entraînement
        est justifié. Un total qui mélange consentis et non consentis ferait
        croire à un jeu de données qui n'existe pas.
        """
        with self._lock:
            connexion = self._connexion()
            total = connexion.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            consentis = connexion.execute(
                "SELECT COUNT(*) FROM feedback WHERE consent_to_train = 1"
            ).fetchone()[0]
            paires = connexion.execute(
                "SELECT COUNT(*) FROM feedback WHERE consent_to_train = 1 "
                "AND (correction IS NOT NULL OR rejected_response IS NOT NULL)"
            ).fetchone()[0]
            par_nature = dict(
                connexion.execute("SELECT kind, COUNT(*) FROM feedback GROUP BY kind").fetchall()
            )
        return {
            "total": total,
            "with_consent": consentis,
            "trainable_pairs": paires,
            "by_kind": par_nature,
            "path": self.db_path,
        }

    def export_pairs(self, approval_request_id: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Exporte les paires de préférence, pour DPO.

        Args:
            approval_request_id: Identifiant d'une approbation accordée. **Exigé**
                (ADR-006) : sortir le texte de vraies personnes vers un jeu de
                données est une décision humaine, pas un effet de bord.

        Returns:
            Les paires `{prompt, chosen, rejected}`.

        Raises:
            PermissionError: Sans identifiant d'approbation.
        """
        if not approval_request_id:
            raise PermissionError(
                "L'export du jeu d'entraînement exige une approbation humaine "
                "(ADR-006) : il fait sortir le texte de vraies personnes."
            )

        paires = []
        for retour in self.list_feedback(consent_only=True, limit=100000):
            choisi = retour.correction or retour.response
            rejete = retour.rejected_response or (retour.response if retour.correction else None)
            if not rejete or choisi == rejete:
                # Sans les deux côtés, il n'y a pas de préférence — seulement une
                # réponse. L'inclure quand même fabriquerait un signal.
                continue
            paires.append({"prompt": retour.prompt, "chosen": choisi, "rejected": rejete})
        return paires


_magasin_partage: Optional[SQLiteFeedbackStore] = None
_verrou = threading.RLock()


def shared_feedback_store() -> SQLiteFeedbackStore:
    """Retourne le magasin partagé, construit au premier appel."""
    global _magasin_partage
    with _verrou:
        if _magasin_partage is None:
            _magasin_partage = SQLiteFeedbackStore()
        return _magasin_partage


def reset_feedback_store() -> None:
    """Oublie le magasin partagé ; le prochain appel le reconstruira."""
    global _magasin_partage
    with _verrou:
        _magasin_partage = None
