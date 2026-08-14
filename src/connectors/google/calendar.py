"""
The Calendar connector: reading events, nothing else.

Same shape as the other two — see `base.py`. One difference is worth stating
rather than leaving implicit, because it is a real departure from Gmail's rule.

Gmail never accepts a mailbox identifier: every request targets `me`. Calendar
**does** accept a calendar identifier, and that is deliberate. A person often
has several calendars, and some of them belong to other people who shared them.
Refusing the parameter would not protect anyone — the token decides what is
readable, exactly as the provider's own interface does — it would only make the
connector unable to do what the person can already do. The default is
`primary`, so the ordinary case never has to name anything.

The other difference is that an event is almost entirely third-party text. Its
title, description and location were written by whoever created it, which is
frequently not the person reading it. All three cross the trust boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..lifecycle import SubjectBinding
from ..safety import receive
from ..types import ConnectorKind
from .base import GoogleReadConnector

#: Nombre d'événements ramenés par défaut, et plafond dur.
TAILLE_DE_PAGE_PAR_DEFAUT = 25
TAILLE_DE_PAGE_MAXIMALE = 250

#: L'agenda par défaut. La valeur est celle du fournisseur, et elle désigne
#: toujours l'agenda principal du porteur du jeton.
AGENDA_PRINCIPAL = "primary"

#: Les champs d'un événement qui sont du texte écrit par un tiers. Ils
#: traversent tous la barrière de confiance — un intitulé de rendez-vous est
#: aussi bien un endroit où glisser une consigne qu'un corps de courriel.
CHAMPS_DE_TEXTE = ("summary", "description", "location")


class CalendarConnector(GoogleReadConnector):
    """Lecture de l'agenda d'une personne, pour elle seule."""

    CONNECTOR_ID = "google_calendar"
    API_NAME = "calendar"
    KIND = ConnectorKind.CALENDAR
    SUMMARY = (
        "Lecture des agendas d'une personne. Ne crée rien, ne déplace rien, "
        "n'invite personne, ne supprime rien."
    )
    OPERATIONS = ["list_calendars", "list_events", "get_event", "read_event"]

    def extra_refusals(self) -> List[str]:
        """Les refus propres à l'agenda."""
        return [
            "Créer, déplacer, annuler un rendez-vous, ou inviter quelqu'un — "
            "ce connecteur lit.",
            "Rendre l'intitulé, la description ou le lieu d'un événement "
            "autrement qu'enveloppés : ils sont écrits par un tiers.",
        ]

    # ------------------------------------------------------------------
    # Les requêtes
    # ------------------------------------------------------------------

    def list_calendars_request(self, binding: SubjectBinding) -> Dict[str, Any]:
        """
        Construit la requête listant les agendas visibles par le titulaire.

        Args:
            binding: Le lien à la personne.

        Returns:
            La requête à envoyer.
        """
        return self._requete(binding, "users/me/calendarList")

    def list_events_request(
        self,
        binding: SubjectBinding,
        calendar_id: str = AGENDA_PRINCIPAL,
        time_min: str = "",
        time_max: str = "",
        max_results: int = TAILLE_DE_PAGE_PAR_DEFAUT,
    ) -> Dict[str, Any]:
        """
        Construit la requête listant les événements d'un agenda.

        Args:
            binding: Le lien à la personne.
            calendar_id: L'agenda visé. `primary` par défaut ; un autre
                identifiant reste borné par ce que le jeton autorise.
            time_min: Borne basse, au format RFC 3339. Elle est passée telle
                quelle : la reformater ici reviendrait à deviner un fuseau.
            time_max: Borne haute, même règle.
            max_results: Combien d'événements, ramené au plafond si dépassé.

        Returns:
            La requête à envoyer.

        Raises:
            ValueError: Si l'identifiant d'agenda est vide.
        """
        if not (calendar_id or "").strip():
            raise ValueError(
                "Identifiant d'agenda vide : `primary` est le défaut, mais la "
                "chaîne vide ne désigne rien."
            )

        parametres: Dict[str, Any] = {
            "maxResults": self._plafonner(
                max_results, TAILLE_DE_PAGE_PAR_DEFAUT, TAILLE_DE_PAGE_MAXIMALE
            ),
            # Un agenda sans ordre est illisible, et les occurrences d'un
            # événement récurrent sont plus utiles que la règle qui les produit.
            "singleEvents": "true",
            "orderBy": "startTime",
        }
        if time_min:
            parametres["timeMin"] = time_min
        if time_max:
            parametres["timeMax"] = time_max

        return self._requete(
            binding, f"calendars/{calendar_id.strip()}/events", parametres
        )

    def get_event_request(
        self, binding: SubjectBinding, event_id: str,
        calendar_id: str = AGENDA_PRINCIPAL,
    ) -> Dict[str, Any]:
        """
        Construit la requête lisant un événement.

        Args:
            binding: Le lien à la personne.
            event_id: L'identifiant de l'événement.
            calendar_id: L'agenda qui le porte.

        Returns:
            La requête à envoyer.

        Raises:
            ValueError: Si un identifiant est vide.
        """
        if not (event_id or "").strip():
            raise ValueError("Identifiant d'événement vide : rien à lire.")
        if not (calendar_id or "").strip():
            raise ValueError("Identifiant d'agenda vide.")
        return self._requete(
            binding,
            f"calendars/{calendar_id.strip()}/events/{event_id.strip()}",
        )

    # ------------------------------------------------------------------
    # Ce qui sort
    # ------------------------------------------------------------------

    def read_event(
        self, binding: SubjectBinding, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Rend un événement exploitable, **textes enveloppés**.

        Args:
            binding: Le lien à la personne.
            payload: L'événement rendu par le fournisseur.

        Returns:
            L'événement, ses champs de texte enveloppés, et les soupçons relevés.

        Raises:
            ValueError: Si la réponse n'est pas exploitable.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                f"Réponse d'événement inattendue : {type(payload).__name__}."
            )

        identifiant = str(payload.get("id") or "inconnu")
        textes: Dict[str, Optional[str]] = {}
        soupcons: List[str] = []

        for champ in CHAMPS_DE_TEXTE:
            valeur = payload.get(champ)
            if valeur is None:
                textes[champ] = None
                continue
            enveloppe = receive(
                self, str(valeur), origin=f"event:{identifiant}:{champ}",
                subject=binding.subject,
            )
            textes[champ] = enveloppe.text
            soupcons.extend(enveloppe.suspicions)

        return {
            "event_id": identifiant,
            **textes,
            # Les dates et les identifiants de participants ne sont pas du
            # texte libre : les envelopper n'apporterait rien et rendrait la
            # réponse illisible.
            "start": (payload.get("start") or {}).get("dateTime")
            or (payload.get("start") or {}).get("date"),
            "end": (payload.get("end") or {}).get("dateTime")
            or (payload.get("end") or {}).get("date"),
            "attendee_count": len(payload.get("attendees") or []),
            "suspicions": soupcons,
        }

    def calendar_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """Ce que ce connecteur est, et ce qu'il refuse d'être."""
        return self.connector_report(subject)
