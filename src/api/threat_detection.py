"""
Détection de menaces (VOLET 11, chapitre 05).

La plateforme **comptait** les échecs d'authentification sans rien en conclure :
douze tentatives consécutives avec douze clés différentes — un bourrage
d'identifiants manifeste — produisaient un compteur à 12 et aucun signal.
Compter n'est pas détecter.

Ce module fait la chose la plus simple qui soit honnête : une **fenêtre
glissante d'échecs par source**, avec un seuil déclaré. Il ne fait ni analyse
comportementale, ni corrélation de renseignement, ni apprentissage — le
chapitre les nomme, et prétendre les fournir avec un compteur serait la
fabrication que `.claude/rules/verification.md` interdit. Ce qui n'est pas fait
est déclaré dans `UNAVAILABLE_METHODS`.

Vie privée : une source est identifiée par son adresse IP, déjà connue du
limiteur de débit, et **jamais par une clé** — pas même son empreinte. Un
journal de menaces qui nomme des clés devient lui-même une cible.
"""

import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

# Fenêtre d'observation et seuil, configurables. Les valeurs par défaut sont
# larges à dessein : une détection qui crie au loup est une détection désactivée
# dans la semaine.
WINDOW_SECONDS_ENV = "GALSEN_THREAT_WINDOW_SECONDS"
THRESHOLD_ENV = "GALSEN_THREAT_FAILURE_THRESHOLD"
DEFAULT_WINDOW_SECONDS = 300
DEFAULT_THRESHOLD = 10

# Nombre maximal de sources suivies. Au-delà, la plus ancienne sort : un
# détecteur dont la mémoire suit le trafic devient lui-même le déni de service.
MAX_TRACKED_SOURCES = 1000

# Méthodes que le chapitre 05 nomme et que ce module ne fournit pas.
UNAVAILABLE_METHODS: Dict[str, str] = {
    "behavioral_analytics": (
        "exige un profil d'usage normal par utilisateur ; la plateforme n'a ni "
        "utilisateurs déclarés ni historique conservé (ADR-009)"
    ),
    "threat_intelligence_correlation": (
        "exige un flux externe d'indicateurs ; aucun n'est configuré et aucun "
        "appel sortant n'est fait pour ce contrôle"
    ),
    "machine_assisted_analysis": (
        "exige un fournisseur de modèle, qui n'est pas configuré (critère C1)"
    ),
}


def window_seconds() -> int:
    """Durée de la fenêtre d'observation, lue dans l'environnement."""
    return _env_int(WINDOW_SECONDS_ENV, DEFAULT_WINDOW_SECONDS)


def failure_threshold() -> int:
    """Nombre d'échecs dans la fenêtre à partir duquel une source est signalée."""
    return _env_int(THRESHOLD_ENV, DEFAULT_THRESHOLD)


def _env_int(nom: str, defaut: int) -> int:
    """Lit un entier positif dans l'environnement, avec repli sur le défaut."""
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        valeur = int(brut)
    except ValueError:
        return defaut
    return valeur if valeur > 0 else defaut


def severity_for(failures: int, threshold: int) -> str:
    """
    Classe la sévérité d'une source (chapitre 05, étape 4).

    Trois niveaux seulement, chacun défini par un multiple du seuil : une échelle
    plus fine suggérerait une précision que compter des échecs ne donne pas.
    """
    if failures >= threshold * 5:
        return "critical"
    if failures >= threshold * 2:
        return "high"
    return "medium"


class ThreatDetector:
    """Suit les échecs d'authentification par source sur une fenêtre glissante."""

    def __init__(self, max_sources: int = MAX_TRACKED_SOURCES):
        self._failures: Dict[str, Deque[float]] = {}
        # Dernier succès par source : il nuance une menace sans la faire taire.
        self._successes: Dict[str, float] = {}
        self._ordre: Deque[str] = deque()
        self._max_sources = max_sources
        self._lock = threading.RLock()

    def record_failure(self, source: Optional[str], now: Optional[float] = None) -> None:
        """
        Enregistre un échec d'authentification pour une source.

        Une source inconnue est comptée sous `unknown` plutôt qu'ignorée :
        perdre les échecs dont on ne connaît pas l'origine reviendrait à ne pas
        voir l'attaque la plus discrète.
        """
        instant = now if now is not None else time.time()
        cle = source or "unknown"
        with self._lock:
            if cle not in self._failures:
                self._failures[cle] = deque()
                self._ordre.append(cle)
                self._evincer_si_necessaire()
            self._failures[cle].append(instant)
            self._purger(cle, instant)

    def record_success(self, source: Optional[str], now: Optional[float] = None) -> None:
        """
        Note qu'une source s'est authentifiée avec succès — sans effacer ses échecs.

        L'effacement était la première version, et il était contournable de deux
        façons mesurées : un attaquant qui finit par trouver une clé valide
        effaçait la trace de ses tentatives, et l'opérateur qui consultait
        `/security/threats` depuis la même adresse effaçait ce qu'il venait
        observer.

        Le succès est donc conservé **à côté** des échecs : la menace reste
        visible, et `succeeded_in_window` dit qu'il s'agit peut-être d'un humain
        qui s'est trompé — la réduction de faux positifs que le chapitre demande,
        sans le contournement.
        """
        instant = now if now is not None else time.time()
        with self._lock:
            self._successes[source or "unknown"] = instant

    def active_threats(self, threshold: Optional[int] = None,
                       now: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Retourne les sources dont les échecs dépassent le seuil dans la fenêtre.

        Returns:
            Une entrée par source signalée, de la plus active à la moins active,
            avec son compte d'échecs, sa sévérité et la date du premier échec
            retenu.
        """
        limite = threshold if threshold is not None else failure_threshold()
        instant = now if now is not None else time.time()
        menaces: List[Dict[str, Any]] = []

        with self._lock:
            for source in list(self._failures):
                self._purger(source, instant)
                echecs = len(self._failures.get(source, ()))
                if echecs >= limite:
                    dernier_succes = self._successes.get(source)
                    menaces.append({
                        "source": source,
                        "failures": echecs,
                        "severity": severity_for(echecs, limite),
                        "first_seen": self._failures[source][0],
                        "window_seconds": window_seconds(),
                        # Des échecs suivis d'un succès ressemblent à une erreur
                        # humaine ; sans succès, l'insistance est le signal.
                        "succeeded_in_window": bool(
                            dernier_succes and dernier_succes >= instant - window_seconds()
                        ),
                    })
        return sorted(menaces, key=lambda m: m["failures"], reverse=True)

    def summary(self, threshold: Optional[int] = None) -> Dict[str, Any]:
        """État complet de la détection, prêt à être servi par une route."""
        limite = threshold if threshold is not None else failure_threshold()
        menaces = self.active_threats(limite)
        with self._lock:
            sources_suivies = len(self._failures)

        return {
            "threats": menaces,
            "tracked_sources": sources_suivies,
            "threshold": limite,
            "window_seconds": window_seconds(),
            "unavailable_methods": dict(UNAVAILABLE_METHODS),
            "scope": (
                "mémoire du processus : un redémarrage efface la fenêtre et une "
                "autre instance a la sienne (ADR-009)"
            ),
        }

    def clear(self) -> None:
        """Vide le détecteur. Réservé aux tests."""
        with self._lock:
            self._failures.clear()
            self._successes.clear()
            self._ordre.clear()

    # -- Interne ---------------------------------------------------------

    def _purger(self, source: str, maintenant: float) -> None:
        """Retire les échecs sortis de la fenêtre (verrou détenu)."""
        limite = maintenant - window_seconds()
        echecs = self._failures.get(source)
        if echecs is None:
            return
        while echecs and echecs[0] < limite:
            echecs.popleft()
        if not echecs:
            del self._failures[source]

    def _evincer_si_necessaire(self) -> None:
        """Borne le nombre de sources suivies (verrou détenu)."""
        while len(self._ordre) > self._max_sources:
            ancienne = self._ordre.popleft()
            self._failures.pop(ancienne, None)


_detecteur: Optional[ThreatDetector] = None
_verrou = threading.Lock()


def get_shared_detector() -> ThreatDetector:
    """Retourne le détecteur partagé du processus."""
    global _detecteur
    if _detecteur is None:
        with _verrou:
            if _detecteur is None:
                _detecteur = ThreatDetector()
    return _detecteur


def reset_detector() -> None:
    """Vide le détecteur partagé. Réservé aux tests."""
    get_shared_detector().clear()
