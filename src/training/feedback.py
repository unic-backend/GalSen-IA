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

## Ce que la règle 3 ne faisait pas, et qu'elle fait maintenant

`export_pairs` exigeait un identifiant d'approbation et se contentait de le
trouver non vide. `export_pairs("oui")` passait. Personne ne demandait au moteur
d'approbation si cette demande existait, si elle avait été **accordée**, ni
surtout **ce qu'elle approuvait**.

C'est la seconde moitié qui compte. Même une vraie approbation accordée disait
« exporter le jeu d'entraînement » — un *acte*. Or le jeu grossit chaque jour :
une approbation obtenue sur douze paires autorisait douze mille paires le mois
suivant, dont personne n'avait lu une ligne. Approuver un acte n'est pas
approuver un contenu, et c'est le contenu qui sort.

D'où l'**empreinte** : `request_export_approval()` calcule ce que l'export
contiendrait *maintenant*, l'inscrit dans la demande, et `export_pairs()`
recalcule au moment de sortir. Si le contenu a bougé, l'approbation ne le couvre
plus — elle n'est pas périmée, elle porte sur autre chose. Le refus dit ce qui a
changé, et la marche à suivre est d'en redemander une, pas de contourner.
"""

import hashlib
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

from src.approval_engine.types import ApprovalRequest, ApprovalStatus
from src.storage.paths import default_sqlite_path, prepare_connection, secure_database_file

DEFAULT_FILENAME = "training_feedback.sqlite"

# Motifs retirés du texte **avant écriture**. La liste est courte et ne prétend
# pas à l'exhaustivité : elle couvre ce qui apparaît réellement dans une
# conversation — un numéro, un e-mail, une carte. Ce qu'elle ne couvre pas est
# la raison pour laquelle le consentement existe aussi.
#: La clé sous laquelle une demande d'approbation porte l'empreinte du contenu
#: qu'elle couvre. Nommée, parce qu'elle est lue d'un côté et écrite de l'autre.
CLE_EMPREINTE = "dataset_fingerprint"

#: Le nombre de paires approuvées, à côté de l'empreinte. Il ne sert pas à
#: décider — l'empreinte le fait — mais à écrire un refus lisible.
CLE_NOMBRE = "dataset_pair_count"

#: L'action portée par la demande. Elle apparaît telle quelle dans la file
#: d'approbation, donc elle dit ce qui sort, pas « export ».
ACTION_EXPORT = "training_dataset_export"

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

    def _paires_courantes(self) -> List[Dict[str, str]]:
        """
        Les paires que l'export contiendrait maintenant.

        Returns:
            Les paires `{prompt, chosen, rejected}`, dans l'ordre du magasin.
            Un retour dont il manque un côté est écarté : sans les deux, il n'y
            a pas de préférence — seulement une réponse, et l'inclure quand même
            fabriquerait un signal.
        """
        paires = []
        for retour in self.list_feedback(consent_only=True, limit=100000):
            choisi = retour.correction or retour.response
            rejete = retour.rejected_response or (retour.response if retour.correction else None)
            if not rejete or choisi == rejete:
                continue
            paires.append({"prompt": retour.prompt, "chosen": choisi, "rejected": rejete})
        return paires

    def export_fingerprint(self) -> Dict[str, Any]:
        """
        Ce que l'export contiendrait maintenant, résumé de façon comparable.

        Returns:
            L'empreinte et le nombre de paires. L'empreinte couvre le **texte**,
            pas seulement le compte : remplacer une paire par une autre laisse
            le compte identique et change ce qui sort.
        """
        paires = self._paires_courantes()
        return {
            "fingerprint": dataset_fingerprint(paires),
            "pair_count": len(paires),
        }

    def export_pairs(
        self,
        approval_request_id: Optional[str] = None,
        approvals: Any = None,
    ) -> List[Dict[str, str]]:
        """
        Exporte les paires de préférence, pour DPO.

        Args:
            approval_request_id: Identifiant d'une approbation **accordée et
                portant l'empreinte de ce contenu**. Ouvrir la demande passe par
                `request_export_approval()`.
            approvals: Le moteur d'approbation. Par défaut celui de la
                plateforme ; injectable pour les tests.

        Returns:
            Les paires `{prompt, chosen, rejected}`.

        Raises:
            PermissionError: Identifiant absent, demande introuvable, non
                accordée, sans empreinte, ou empreinte qui ne correspond plus au
                contenu. Chacun de ces refus empêche le même geste : sortir vers
                un jeu de données du texte que personne n'a lu ni accepté.
        """
        if not approval_request_id:
            raise PermissionError(
                "L'export du jeu d'entraînement exige une approbation humaine "
                "(ADR-006) : il fait sortir le texte de vraies personnes. "
                "Ouvrez-la avec `request_export_approval()`."
            )

        portillon = approvals if approvals is not None else _portillon()
        if portillon is None:
            raise PermissionError(
                "Le moteur d'approbation est indisponible : l'export ne peut pas "
                "être vérifié. Un identifiant non vérifiable n'est pas une "
                "approbation, et l'absence de vérificateur n'accorde rien."
            )

        demande = portillon.get(approval_request_id)
        if demande is None:
            raise PermissionError(
                f"La demande d'approbation « {approval_request_id} » n'existe "
                "pas. Une chaîne de caractères n'est pas une approbation."
            )

        statut = getattr(demande, "status", None)
        if statut != ApprovalStatus.APPROVED.value:
            raise PermissionError(
                f"La demande « {approval_request_id} » est « {statut} », pas "
                f"« {ApprovalStatus.APPROVED.value} ». Une demande ouverte n'est "
                "pas une décision."
            )

        metadonnees = getattr(demande, "metadata", None) or {}
        attendue = metadonnees.get(CLE_EMPREINTE)
        if not attendue:
            raise PermissionError(
                f"La demande « {approval_request_id} » ne porte aucune empreinte "
                f"de contenu ({CLE_EMPREINTE}). Elle approuve un acte, pas ce "
                "qui sort — et c'est ce qui sort qui contient le texte de vraies "
                "personnes."
            )

        courant = self.export_fingerprint()
        if courant["fingerprint"] != attendue:
            approuvees = metadonnees.get(CLE_NOMBRE)
            raise PermissionError(
                f"Le contenu a changé depuis l'approbation « {approval_request_id} » : "
                f"{approuvees} paire(s) approuvée(s), {courant['pair_count']} "
                "maintenant, ou un texte modifié à nombre égal. Cette approbation "
                "porte sur un autre jeu de données. Redemandez-en une : approuver "
                "un acte n'est pas approuver un contenu."
            )

        return self._paires_courantes()


def dataset_fingerprint(pairs: List[Dict[str, str]]) -> str:
    """
    Résume un jeu de paires de façon comparable.

    Args:
        pairs: Les paires `{prompt, chosen, rejected}`.

    Returns:
        Un condensé SHA-256 du **texte**, dans l'ordre. Compter les paires
        n'aurait pas suffi : remplacer une paire par une autre laisse le compte
        identique et change entièrement ce qui sort. Un jeu vide a lui aussi son
        empreinte — approuver un export vide reste une décision, et la
        distinguer de « pas d'empreinte » évite qu'une demande sans contenu
        passe pour une demande sans borne.
    """
    condenseur = hashlib.sha256()
    for paire in pairs:
        for champ in ("prompt", "chosen", "rejected"):
            valeur = paire.get(champ, "")
            condenseur.update(str(valeur).encode("utf-8"))
            # Séparateur hors du texte : sans lui, « ab » + « c » et « a » +
            # « bc » donneraient la même empreinte.
            condenseur.update(b"\x1f")
        condenseur.update(b"\x1e")
    return condenseur.hexdigest()


def _portillon() -> Any:
    """
    Le moteur d'approbation de la plateforme, ou `None` s'il est absent.

    L'import est local : `src/training/` n'a aucune raison de dépendre du
    registre d'intégration au chargement, et un cycle d'imports coûterait plus
    cher que cette ligne.
    """
    try:
        from src.integration.registry import get_shared_registry
        return get_shared_registry().try_get("approval")
    except Exception:  # noqa: BLE001 — un registre absent n'est pas une panne ici
        return None


def request_export_approval(
    store: "SQLiteFeedbackStore",
    requested_by: str,
    approvals: Any = None,
) -> ApprovalRequest:
    """
    Ouvre une demande d'approbation portant sur le contenu à exporter.

    Args:
        store: Le magasin dont on veut exporter les paires.
        requested_by: Qui demande. Nommé, parce qu'un audit relira la demande.
        approvals: Le moteur d'approbation ; par défaut celui de la plateforme.

    Returns:
        La demande, en attente, portant l'empreinte du contenu **tel qu'il est
        maintenant** et le nombre de paires. C'est cette empreinte que
        `export_pairs()` recalculera : une approbation obtenue sur douze paires
        n'en autorise pas douze mille.

    Raises:
        PermissionError: Demandeur absent, ou moteur d'approbation indisponible.
    """
    nom = str(requested_by or "").strip()
    if not nom:
        raise PermissionError(
            "Demande d'export sans demandeur. Un audit doit pouvoir relire qui "
            "a voulu sortir ce texte."
        )

    portillon = approvals if approvals is not None else _portillon()
    if portillon is None:
        raise PermissionError(
            "Le moteur d'approbation est indisponible : aucune demande ne peut "
            "être ouverte, et un export ne se fait pas sans elle."
        )

    empreinte = store.export_fingerprint()
    demande = ApprovalRequest(
        agent_id="training",
        request_id=None,
        action=ACTION_EXPORT,
        description=(
            f"Exporter {empreinte['pair_count']} paire(s) de préférence vers un "
            "jeu de données d'entraînement. Ce texte a été écrit par de vraies "
            "personnes ; l'approbation porte sur ce contenu précis, et devient "
            "caduque s'il change."
        ),
        metadata={
            CLE_EMPREINTE: empreinte["fingerprint"],
            CLE_NOMBRE: empreinte["pair_count"],
            "requested_by": nom,
            "store_path": store.db_path,
        },
    )
    portillon.submit(demande)
    return demande


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
