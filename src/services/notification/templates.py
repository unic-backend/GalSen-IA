"""
Gabarits de message des notifications (VOLET 17, chapitres 02 et 04).

Le chapitre 02 nomme un « Template Manager » parmi ses composants et le
chapitre 04 range la gestion des gabarits parmi ses domaines. Rien de tel
n'existait : chaque appelant composait son titre et son message à la main, si
bien que le même événement s'annonçait différemment selon l'endroit du code qui
le signalait — et qu'aucun regroupement ne pouvait les rapprocher, la
déduplication comparant des chaînes exactes.

Ce module reste volontairement petit. Il ne fait pas de rendu conditionnel, pas
de boucles, pas d'héritage de gabarits : une notification tient en une ligne de
titre et quelques lignes de message, et un moteur de gabarits complet serait une
dépendance de plus pour un besoin qui ne la porte pas.

**Aucun gabarit n'est fourni d'avance.** En inscrire pour montrer que le
mécanisme marche fabriquerait des messages que personne n'a demandés ; les
appelants enregistrent les leurs.
"""

import re
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .types import NotificationPriority, NotificationType

# Un paramètre est un nom simple entre accolades : {destinataire}, {seuil}.
_PARAMETRE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class TemplateError(ValueError):
    """
    Gabarit inutilisable : inconnu, ou rendu avec des paramètres manquants.

    Une erreur plutôt qu'un message partiel : une notification annonçant
    « Le disque {nom} est plein à {taux} % » est pire que pas de notification —
    elle a l'air d'une vraie alerte et ne dit rien.
    """


@dataclass(frozen=True)
class NotificationTemplate:
    """
    Gabarit de notification, avec ses valeurs par défaut.

    Attributes:
        name: Identifiant stable du gabarit, cité par l'appelant.
        notification_type: Type appliqué aux notifications produites.
        title: Gabarit du titre, avec ses paramètres entre accolades.
        message: Gabarit du message.
        priority: Priorité appliquée par défaut.
        description: À quoi sert ce gabarit, pour qui le lit dans le registre.
    """

    name: str
    notification_type: NotificationType
    title: str
    message: str
    priority: NotificationPriority = NotificationPriority.NORMAL
    description: str = ""

    @property
    def parameters(self) -> List[str]:
        """Noms des paramètres attendus, titre et message confondus."""
        trouves = _PARAMETRE.findall(self.title) + _PARAMETRE.findall(self.message)
        # Ordre stable et sans doublon : la liste est lue par des humains.
        return sorted(set(trouves))

    def render(self, valeurs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produit le titre et le message du gabarit.

        Args:
            valeurs: valeurs des paramètres.

        Returns:
            Un dictionnaire prêt à passer à `send_notification`.

        Raises:
            TemplateError: si un paramètre attendu manque.
        """
        manquants = [nom for nom in self.parameters if nom not in valeurs]
        if manquants:
            raise TemplateError(
                f"Gabarit '{self.name}' : paramètre(s) manquant(s) {', '.join(manquants)}"
            )

        substitution = {nom: valeurs[nom] for nom in self.parameters}
        return {
            "notification_type": self.notification_type,
            "title": _formater(self.title, substitution),
            "message": _formater(self.message, substitution),
            "priority": self.priority,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Retourne le gabarit sous forme sérialisable."""
        return {
            "name": self.name,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "parameters": self.parameters,
            "description": self.description,
        }


@dataclass
class TemplateRegistry:
    """
    Registre des gabarits connus d'un processus.

    Un registre explicite plutôt qu'un dictionnaire de module : les tests
    peuvent en construire un isolé, et le service en reçoit un plutôt que d'en
    supposer un global.
    """

    _gabarits: Dict[str, NotificationTemplate] = field(default_factory=dict)

    def register(self, gabarit: NotificationTemplate) -> None:
        """
        Enregistre un gabarit, en remplaçant celui de même nom s'il existe.

        Args:
            gabarit: le gabarit à enregistrer.
        """
        self._gabarits[gabarit.name] = gabarit

    def get(self, nom: str) -> Optional[NotificationTemplate]:
        """Retourne un gabarit par son nom, ou None."""
        return self._gabarits.get(nom)

    def render(self, nom: str, valeurs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Rend un gabarit enregistré.

        Args:
            nom: nom du gabarit.
            valeurs: valeurs des paramètres.

        Returns:
            Les champs prêts pour `send_notification`.

        Raises:
            TemplateError: si le gabarit est inconnu ou incomplet.
        """
        gabarit = self.get(nom)
        if gabarit is None:
            connus = ", ".join(sorted(self._gabarits)) or "aucun"
            raise TemplateError(f"Gabarit '{nom}' inconnu (connus : {connus})")
        return gabarit.render(valeurs or {})

    def list_templates(self) -> List[Dict[str, Any]]:
        """Retourne les gabarits enregistrés, triés par nom."""
        return [self._gabarits[nom].to_dict() for nom in sorted(self._gabarits)]

    def __len__(self) -> int:
        """Nombre de gabarits enregistrés."""
        return len(self._gabarits)


def _formater(gabarit: str, valeurs: Dict[str, Any]) -> str:
    """
    Substitue les paramètres sans exécuter le reste de la mini-langue de `format`.

    `str.format` accepte `{a.__class__}` et `{a[0]}` : sur un gabarit venu d'une
    configuration, cela donne accès aux attributs des objets passés. Les valeurs
    substituées ne sont pas non plus réinterprétées — une valeur contenant des
    accolades reste du texte.
    """
    return string.Template(_PARAMETRE.sub(r"${\1}", gabarit)).safe_substitute(valeurs)
