"""
The Gmail connector: reading only, and every message leaves as data.

This is the first connector bound to a person, and it is deliberately the
narrowest one that is still useful. It reads. It does not send, does not label,
does not delete. Sending is not a missing feature to be added quietly later: an
email that has gone does not come back, and a connector that can send is a
different thing from one that can read, with a different consent behind it.

Everything the previous phases built comes together here, and none of it is
re-implemented:

- the data contract (41.1) — `user_private`, per subject, retaining nothing;
- the lifecycle and the binding (41.2) — no call without a subject;
- the OAuth session (43.3) — one place for authorization and withdrawal;
- the trust boundary (42.1) — **`receive()` is the only way a message body
  leaves this module**, so a thread saying « ignore your previous instructions »
  arrives as data with an origin, not as an order.

Two things this module does not do, and will not:

**It makes no network call.** It builds requests; an executor sends them. That
separation is not a workaround for this environment — the Google hosts are in
fact reachable from here (measured 2026-08-14) — it is what makes every branch
of this module testable without a credential and without a network.

**It never accepts a mailbox identifier.** Every request targets `me`, the owner
of the token. Taking a user id in a parameter would make « read someone else's
mail » a request one could formulate — the token would refuse it, but the
request should not exist.
"""

from __future__ import annotations

import base64
import binascii
from typing import Any, Dict, List, Optional

from ..lifecycle import SubjectBinding
from ..safety import receive
from ..types import ConnectorKind
from .base import GoogleReadConnector

#: Nombre de messages ramenés par défaut. Volontairement bas : une boîte
#: contient des années de courrier, et en tirer mille d'un coup est presque
#: toujours une erreur de conception plutôt qu'un besoin.
TAILLE_DE_PAGE_PAR_DEFAUT = 25

#: Plafond dur. Au-delà, la demande est ramenée à cette valeur plutôt que
#: refusée : l'appelant obtient moins, jamais rien.
TAILLE_DE_PAGE_MAXIMALE = 100


class GmailConnector(GoogleReadConnector):
    """
    Lecture de la boîte Gmail d'une personne, pour elle seule.

    Le contrat, les privilèges, la vérification et la construction des requêtes
    viennent de `GoogleReadConnector` : ce qui reste ici est ce que Gmail a de
    particulier — sa recherche, ses en-têtes, et son corps en plusieurs parties.
    """

    CONNECTOR_ID = "google_gmail"
    API_NAME = "gmail"
    KIND = ConnectorKind.EMAIL
    SUMMARY = (
        "Lecture de la boîte Gmail d'une personne. N'envoie rien, "
        "n'étiquette rien, ne supprime rien."
    )
    OPERATIONS = ["list_messages", "get_message", "extract_text"]

    # ------------------------------------------------------------------
    # Les requêtes, construites et non envoyées
    # ------------------------------------------------------------------

    def list_messages_request(
        self, binding: SubjectBinding, query: str = "", max_results: int = TAILLE_DE_PAGE_PAR_DEFAUT
    ) -> Dict[str, Any]:
        """
        Construit la requête listant les messages du titulaire.

        Args:
            binding: Le lien à la personne.
            query: Une recherche Gmail, telle quelle. Elle vient de la personne
                et n'est pas interprétée ici.
            max_results: Combien de messages, ramené au plafond si dépassé.

        Returns:
            La requête à envoyer.

        Raises:
            AuthorizationRefused: Si l'accès n'est pas utilisable.
        """
        combien = self._plafonner(
            max_results, TAILLE_DE_PAGE_PAR_DEFAUT, TAILLE_DE_PAGE_MAXIMALE
        )
        parametres: Dict[str, Any] = {"maxResults": combien}
        if query:
            parametres["q"] = query
        return self._requete(
            binding, f"users/{self.api.user_id}/messages", parametres
        )

    def get_message_request(
        self, binding: SubjectBinding, message_id: str
    ) -> Dict[str, Any]:
        """
        Construit la requête lisant un message.

        Args:
            binding: Le lien à la personne.
            message_id: L'identifiant du message.

        Returns:
            La requête à envoyer.

        Raises:
            ValueError: Si l'identifiant est vide.
            AuthorizationRefused: Si l'accès n'est pas utilisable.
        """
        if not (message_id or "").strip():
            raise ValueError("Identifiant de message vide : rien à lire.")
        return self._requete(
            binding,
            f"users/{self.api.user_id}/messages/{message_id.strip()}",
            {"format": "full"},
        )

    # ------------------------------------------------------------------
    # Ce qui sort
    # ------------------------------------------------------------------

    def read_message(
        self, binding: SubjectBinding, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transforme la réponse de Gmail en quelque chose d'utilisable, **en donnée**.

        Le corps passe par `receive()` — le seul chemin de sortie d'un
        connecteur — et revient enveloppé : origine annoncée, balises
        neutralisées, soupçons attachés. Un fil qui dit « ignore tes
        instructions précédentes » n'est pas moins un fil.

        Args:
            binding: Le lien à la personne.
            payload: La réponse du fournisseur pour un message.

        Returns:
            Les en-têtes utiles, le corps **enveloppé**, et ce qui n'a pas pu
            être décodé.

        Raises:
            ValueError: Si la réponse n'est pas exploitable.
        """
        if not isinstance(payload, dict):
            raise ValueError(
                f"Réponse de message inattendue : {type(payload).__name__}."
            )

        identifiant = str(payload.get("id") or "inconnu")
        entetes = self._entetes(payload)
        texte, indecodables = self._texte(payload.get("payload") or {})

        enveloppe = receive(
            self, texte, origin=f"message:{identifiant}", subject=binding.subject
        )
        return {
            "message_id": identifiant,
            "thread_id": payload.get("threadId"),
            # Les en-têtes viennent aussi de l'extérieur : un objet de courriel
            # est du texte écrit par un tiers, exactement comme le corps.
            "headers": {
                nom: receive(
                    self, valeur, origin=f"message:{identifiant}:{nom}",
                    subject=binding.subject,
                ).text
                for nom, valeur in entetes.items()
            },
            "body": enveloppe.text,
            "suspicions": list(enveloppe.suspicions),
            "undecodable_parts": indecodables,
        }

    @staticmethod
    def _entetes(payload: Dict[str, Any]) -> Dict[str, str]:
        """Extrait les en-têtes qui servent à situer un message."""
        interessants = {"from", "to", "subject", "date"}
        entetes: Dict[str, str] = {}
        for entree in (payload.get("payload") or {}).get("headers", []) or []:
            nom = str((entree or {}).get("name", "")).lower()
            if nom in interessants:
                entetes[nom] = str(entree.get("value", ""))
        return entetes

    @classmethod
    def _texte(cls, partie: Dict[str, Any]) -> tuple:
        """
        Extrait le texte d'un message, en parcourant ses parties.

        `text/plain` est préféré : le HTML d'un courriel porte du style, des
        images distantes et parfois du script, et rien de tout cela n'aide à
        comprendre ce qui est écrit.

        Returns:
            Le texte trouvé, et la liste des parties qui n'ont pas pu être
            décodées. **Une partie illisible est rapportée, pas ignorée** : un
            message rendu à moitié sans le dire se lit comme un message entier.
        """
        # Un **seul** parcours, et le choix du type se fait après. Deux
        # parcours — un pour `text/plain`, un de repli — comptaient deux fois
        # la même partie illisible, et deux échecs pour un seul ne se lisent
        # pas comme une information juste.
        par_type: Dict[str, List[str]] = {}
        indecodables: List[str] = []
        cls._parcourir(partie, par_type, indecodables)

        morceaux = par_type.get("text/plain") or [
            texte for type_mime in sorted(par_type) for texte in par_type[type_mime]
        ]
        return "\n".join(morceaux), indecodables

    @classmethod
    def _parcourir(
        cls, partie: Dict[str, Any], par_type: Dict[str, List[str]],
        indecodables: List[str],
    ) -> None:
        """Parcourt récursivement les parties d'un message, une seule fois."""
        type_mime = str(partie.get("mimeType") or "inconnu")
        donnees = ((partie.get("body") or {}).get("data") or "")

        if donnees:
            try:
                texte = base64.urlsafe_b64decode(donnees + "===").decode("utf-8", "replace")
            except (binascii.Error, ValueError):
                indecodables.append(type_mime)
            else:
                par_type.setdefault(type_mime, []).append(texte)

        for sous_partie in partie.get("parts", []) or []:
            cls._parcourir(sous_partie or {}, par_type, indecodables)

    # ------------------------------------------------------------------
    # Rapport
    # ------------------------------------------------------------------

    def extra_refusals(self) -> List[str]:
        """Les refus propres à Gmail, en plus de ceux du socle."""
        return [
            "Envoyer, étiqueter, supprimer — ce connecteur lit.",
            "Prendre un identifiant de boîte : chaque requête vise `me`.",
        ]

    def gmail_report(self, subject: Optional[str] = None) -> Dict[str, Any]:
        """Ce que ce connecteur est, et ce qu'il refuse d'être."""
        return self.connector_report(subject)
