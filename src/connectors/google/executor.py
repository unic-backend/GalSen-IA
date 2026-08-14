"""
The request executor: the one place a connector's request becomes a call.

The connectors build requests and never send them. Something has to send them,
and putting that somewhere separate is not bookkeeping — it is what makes the
rest testable: every branch of the Gmail connector runs in a test with no
network and no credential, because the only part that needs either lives here.

It also gives the platform one place to hold the things that are easy to get
wrong once and then forget:

- **A refusal is data, never an exception.** A 401 means the person's access
  died and must be asked for again; a 429 means wait; a 500 means the provider
  is having a bad day. Collapsing the three into one raised exception loses the
  only information that decides what to do next.
- **A token never reaches a log or an error.** The header is stripped before
  anything about the request is recorded, so a failure report can be read by
  anyone without handing them the credential that caused it.
- **Nothing is retried by default.** A retry on a request that already
  succeeded server-side is how one message becomes three; retrying is the
  caller's decision, and only for the statuses that say so.

In this environment the Google hosts *are* reachable (measured 2026-08-14) —
what is missing is a credential, and none will be fabricated. So the executor is
real, and every test drives it through a stub transport rather than the network:
a test that depends on someone else's server is a test that fails for reasons
that have nothing to do with the code.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from ...security.redaction import redact_mapping

#: Les états qui disent « recommence plus tard ». Ils sont **nommés**, pas
#: devinés à partir d'une plage : `503` se réessaie, `500` peut être une requête
#: malformée qui échouera identiquement à chaque fois.
ETATS_REESSAYABLES = frozenset({429, 500, 502, 503, 504})

#: Les états qui disent « cet accès est mort ». Ils appellent un nouveau
#: consentement, pas une attente.
ETATS_D_AUTORISATION = frozenset({401, 403})


@dataclass
class ExecutionResult:
    """
    Ce qu'un appel a donné, refus compris.

    Attributes:
        status: Le code HTTP obtenu, ou `0` si rien n'a été atteint.
        body: Le corps décodé, quand il y en a un.
        error: Ce qui a empêché l'appel, s'il n'a pas eu lieu.
        elapsed_ms: Durée mesurée.
        request: La requête, **sans son en-tête d'autorisation**.
    """

    status: int
    body: Optional[Any] = None
    error: str = ""
    elapsed_ms: float = 0.0
    request: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Vrai pour un succès franc, `2xx`."""
        return 200 <= self.status < 300

    @property
    def authorization_lost(self) -> bool:
        """Vrai si l'accès de la personne doit être redemandé."""
        return self.status in ETATS_D_AUTORISATION

    @property
    def retryable(self) -> bool:
        """Vrai si recommencer plus tard a un sens."""
        return self.status in ETATS_REESSAYABLES or (self.status == 0 and bool(self.error))

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans aucun jeton."""
        return {
            "status": self.status,
            "ok": self.ok,
            "authorization_lost": self.authorization_lost,
            "retryable": self.retryable,
            "error": self.error,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "request": self.request,
        }


def strip_credentials(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Retire d'une requête tout ce qui permettrait de la rejouer.

    Utilisé avant toute journalisation et dans tout résultat : un rapport
    d'échec doit pouvoir être lu par quelqu'un sans lui remettre l'identifiant
    qui a causé l'échec.

    Args:
        request: La requête construite par un connecteur.

    Returns:
        Une copie, en-têtes masqués.
    """
    copie = {
        cle: valeur for cle, valeur in (request or {}).items()
        if cle not in ("headers", "data")
    }
    if "headers" in (request or {}):
        copie["headers"] = redact_mapping(request["headers"])
    if "data" in (request or {}):
        copie["data"] = redact_mapping(request["data"])
    return copie


class RequestExecutor:
    """
    Envoie les requêtes construites par les connecteurs.

    Le transport est **injecté**. Par défaut il n'y en a aucun, et l'exécuteur
    le dit au lieu d'inventer un client : une dépendance réseau choisie en
    silence est une dépendance que personne n'a revue.
    """

    def __init__(
        self,
        transport: Optional[Callable[..., Any]] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """
        Args:
            transport: Un appelable `(method, url, headers, params, data,
                timeout) -> (status, body)`. Sans lui, l'exécuteur refuse.
            timeout_seconds: Au-delà, l'appel est abandonné. Un appel sans
                délai bloque un serveur entier sur un fournisseur lent.
        """
        self._transport = transport
        self._timeout = float(timeout_seconds)

    @property
    def available(self) -> bool:
        """Indique si un transport est branché."""
        return self._transport is not None

    def execute(self, request: Dict[str, Any]) -> ExecutionResult:
        """
        Envoie une requête et rend ce qu'elle a donné.

        **Ne lève pas** pour un refus du fournisseur : un `401` et un `429`
        appellent deux suites différentes, et une exception commune effacerait
        justement l'information qui les distingue.

        Args:
            request: La requête construite par un connecteur.

        Returns:
            Le résultat, refus compris.
        """
        sans_secret = strip_credentials(request)

        if not self.available:
            return ExecutionResult(
                status=0,
                error=(
                    "Aucun transport branché : l'exécuteur n'invente pas de "
                    "client réseau. Fournissez-en un explicitement."
                ),
                request=sans_secret,
            )

        depart = time.monotonic()
        try:
            status, corps = self._transport(
                method=request.get("method", "GET"),
                url=request.get("url", ""),
                headers=dict(request.get("headers") or {}),
                params=dict(request.get("params") or {}),
                data=request.get("data"),
                timeout=self._timeout,
            )
        except Exception as erreur:
            # Le message d'une exception de transport peut contenir l'URL
            # complète ; il ne contiendra pas l'en-tête, qui n'y entre pas.
            return ExecutionResult(
                status=0,
                error=f"{type(erreur).__name__}: {erreur}",
                elapsed_ms=(time.monotonic() - depart) * 1000,
                request=sans_secret,
            )

        return ExecutionResult(
            status=int(status),
            body=corps,
            elapsed_ms=(time.monotonic() - depart) * 1000,
            request=sans_secret,
        )

    def executor_report(self) -> Dict[str, Any]:
        """
        Ce que l'exécuteur peut faire, et ce qu'il ne fait jamais.

        Returns:
            L'état du transport et les règles qu'il tient.
        """
        return {
            "transport_attached": self.available,
            "timeout_seconds": self._timeout,
            "retryable_statuses": sorted(ETATS_REESSAYABLES),
            "authorization_statuses": sorted(ETATS_D_AUTORISATION),
            "never": [
                "Réessayer de lui-même : un réessai sur une requête déjà "
                "passée côté serveur transforme un message en trois.",
                "Lever pour un refus du fournisseur : « accès mort » et "
                "« attends » appellent deux suites différentes.",
                "Laisser un jeton entrer dans un résultat, un journal ou une "
                "erreur.",
                "Choisir un client réseau en silence.",
            ],
        }
