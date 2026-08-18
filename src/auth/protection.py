"""
Ce qu'ADR-029 devait encore : verrouillage, réinitialisation, notification de fuite.

ADR-029 a choisi l'option C — la plateforme garde des mots de passe — et a
énuméré, dans sa propre section *Consequences*, ce qui restait dû : « password
reset, lockout after repeated failures, and breach notification ». Une dette
écrite dans une ADR et jamais soldée finit par se lire comme une décision.

Les trois tiennent ensemble : ce sont les obligations qu'on accepte en gardant
un secret d'autrui.

## Le verrouillage, et ce qu'il ne doit pas révéler

Bloquer après N échecs est facile ; le faire sans dire à un attaquant quelles
adresses existent l'est moins. Un compte inconnu et un mot de passe faux
doivent **compter pareil** et **répondre pareil**. Sinon le verrouillage devient
un oracle : « cette adresse se verrouille, donc elle existe ».

`register_failure()` accepte donc n'importe quelle adresse, connue ou non, et
`state()` ne dit jamais si le compte existe.

## La réinitialisation, et le même piège

`request_reset()` **rend toujours la même chose**, compte connu ou non. Le jeton
n'est produit que pour un compte réel, mais l'appelant ne peut pas faire la
différence — c'est la seule façon qu'un formulaire « mot de passe oublié » ne
soit pas un annuaire.

Le jeton est à **usage unique**, borné dans le temps, et **consommé même en cas
d'échec** de la nouvelle politique de mot de passe : un jeton rejouable est un
mot de passe qui ne s'expire pas.

## La notification de fuite, et pourquoi elle ne s'invente pas

Un module qui prétendrait « notifier » sans canal d'envoi configuré mentirait
sur la seule obligation qui compte vraiment. `breach_disclosure()` **calcule ce
qui doit être dit et à qui**, puis rapporte `NOT_SENT` avec la raison tant
qu'aucun canal n'est configuré. C'est un dossier prêt, pas un envoi accompli, et
les deux ne se confondent pas.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: Échecs tolérés avant verrouillage. Déclaré, donc discutable — un seuil caché
#: se discute mal, et celui-ci arbitre entre gêner un attaquant et enfermer un
#: utilisateur qui se trompe de clavier.
ECHECS_TOLERES = 5

#: Durée du verrouillage, en secondes. Assez pour rendre le forçage coûteux,
#: assez court pour qu'une personne légitime revienne dans la journée.
DUREE_VERROU = 900.0

#: Fenêtre d'observation. Cinq échecs étalés sur une semaine ne sont pas une
#: attaque ; les compter comme telle verrouillerait des comptes ordinaires.
FENETRE_ECHECS = 3600.0

#: Durée de vie d'un jeton de réinitialisation. Un jeton qui vit longtemps est
#: un second mot de passe, et il dort dans une boîte de courriels.
DUREE_JETON = 1800.0

#: L'état d'une notification de fuite.
PRET = "READY"
NON_ENVOYE = "NOT_SENT"


class ProtectionRefused(ValueError):
    """Une opération de protection impossible, avec sa raison."""


@dataclass
class _Compteur:
    """Les échecs récents d'une adresse, et son verrou éventuel."""

    echecs: List[float] = field(default_factory=list)
    verrouille_jusqu_a: float = 0.0


class LoginGuard:
    """
    Compte les échecs et verrouille, sans jamais révéler qui existe.

    Le magasin est en mémoire. C'est une limite réelle et elle est écrite : sur
    un redémarrage, les compteurs repartent à zéro et un attaquant patient y
    gagne. `GALSEN_STORAGE_BACKEND=sqlite` ne couvre pas encore ce magasin —
    `report()` le dit plutôt que de le laisser croire.
    """

    def __init__(
        self, max_failures: int = ECHECS_TOLERES,
        lock_seconds: float = DUREE_VERROU,
        window_seconds: float = FENETRE_ECHECS,
    ) -> None:
        """Ouvre un garde avec ses seuils déclarés."""
        if max_failures < 1:
            raise ProtectionRefused(
                "Un seuil inférieur à 1 verrouillerait avant tout essai."
            )
        self.max_failures = max_failures
        self.lock_seconds = lock_seconds
        self.window_seconds = window_seconds
        self._verrou = threading.RLock()
        self._compteurs: Dict[str, _Compteur] = {}

    @staticmethod
    def _cle(email: str) -> str:
        """
        La clé d'une adresse — son empreinte, jamais l'adresse elle-même.

        Un journal ou un vidage mémoire du garde ne doit pas rendre la liste
        des adresses ayant tenté de se connecter.
        """
        return hashlib.sha256(str(email or "").strip().lower().encode()).hexdigest()

    def register_failure(self, email: str, now: Optional[float] = None) -> Dict[str, Any]:
        """
        Enregistre un échec, que le compte existe ou non.

        Args:
            email: L'adresse présentée.
            now: L'instant, pour les tests.

        Returns:
            L'état après l'échec. **L'appelant doit appeler cette méthode même
            pour une adresse inconnue** : ne compter que les comptes réels
            ferait du verrouillage un oracle d'existence.
        """
        instant = now or time.time()
        cle = self._cle(email)
        with self._verrou:
            compteur = self._compteurs.setdefault(cle, _Compteur())
            compteur.echecs = [t for t in compteur.echecs
                               if instant - t <= self.window_seconds]
            compteur.echecs.append(instant)
            if len(compteur.echecs) >= self.max_failures:
                compteur.verrouille_jusqu_a = instant + self.lock_seconds
            return self._etat(compteur, instant)

    def register_success(self, email: str) -> None:
        """Efface les échecs d'une adresse après une connexion réussie."""
        with self._verrou:
            self._compteurs.pop(self._cle(email), None)

    def state(self, email: str, now: Optional[float] = None) -> Dict[str, Any]:
        """
        L'état d'une adresse, sans jamais dire si le compte existe.

        Returns:
            `locked`, et le temps restant. Une adresse jamais vue rend
            exactement la même forme qu'une adresse connue sans échec — c'est
            ce qui empêche de s'en servir pour énumérer des comptes.
        """
        instant = now or time.time()
        with self._verrou:
            compteur = self._compteurs.get(self._cle(email))
            if compteur is None:
                return {"locked": False, "remaining_seconds": 0.0,
                        "failures": 0}
            return self._etat(compteur, instant)

    def _etat(self, compteur: _Compteur, instant: float) -> Dict[str, Any]:
        """Met en forme l'état d'un compteur."""
        restant = max(0.0, compteur.verrouille_jusqu_a - instant)
        return {
            "locked": restant > 0,
            "remaining_seconds": round(restant, 1),
            "failures": len([t for t in compteur.echecs
                             if instant - t <= self.window_seconds]),
        }

    def report(self) -> Dict[str, Any]:
        """Les seuils, et la limite du magasin."""
        with self._verrou:
            verrouilles = len([c for c in self._compteurs.values()
                               if c.verrouille_jusqu_a > time.time()])
        return {
            "max_failures": self.max_failures,
            "lock_seconds": self.lock_seconds,
            "window_seconds": self.window_seconds,
            "locked_now": verrouilles,
            "tracked": len(self._compteurs),
            "persistence": "IN_MEMORY",
            "limitation": (
                "Les compteurs ne survivent pas à un redémarrage : un "
                "attaquant patient y gagne. Ce magasin n'est pas encore couvert "
                "par `GALSEN_STORAGE_BACKEND=sqlite`."
            ),
            "rules": [
                "Un échec est compté que le compte existe ou non — sinon le "
                "verrouillage dirait quelles adresses existent.",
                "Les adresses ne sont pas stockées en clair : seule leur "
                "empreinte l'est.",
                "Une fenêtre borne le comptage : cinq échecs sur une semaine "
                "ne sont pas une attaque.",
            ],
        }


@dataclass(frozen=True)
class ResetTicket:
    """
    Un jeton de réinitialisation, et ce qui le borne.

    Attributes:
        token: Le secret remis à la personne.
        user_id: Le compte visé.
        issued_at: Quand il a été émis.
        expires_at: Quand il cesse de valoir.
    """

    token: str
    user_id: str
    issued_at: float
    expires_at: float


class PasswordResetService:
    """
    Réinitialisation par jeton à usage unique, qui ne révèle aucun compte.

    Le magasin est en mémoire, comme celui du garde, et pour la même raison
    déclarée : ADR-029 doit encore décider si un jeton de réinitialisation
    survit à un redémarrage. Ici il ne survit pas, ce qui est le côté prudent
    de l'indécision.
    """

    def __init__(self, ttl_seconds: float = DUREE_JETON) -> None:
        """Ouvre le service avec la durée de vie déclarée."""
        if ttl_seconds <= 0:
            raise ProtectionRefused(
                "Une durée de vie nulle rendrait tout jeton inutilisable."
            )
        self.ttl_seconds = ttl_seconds
        self._verrou = threading.RLock()
        self._billets: Dict[str, ResetTicket] = {}

    def request_reset(
        self, email: str, user_id: Optional[str], now: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Ouvre une réinitialisation, et rend la même chose dans tous les cas.

        Args:
            email: L'adresse demandée.
            user_id: L'identifiant du compte **s'il existe**, sinon `None`.
                C'est l'appelant qui a fait la recherche ; ce service ne
                connaît pas l'annuaire.
            now: L'instant, pour les tests.

        Returns:
            Toujours la même forme, compte connu ou non : `accepted: True` et
            aucune information sur l'existence. Le jeton n'est présent que pour
            un compte réel — et c'est l'appelant qui l'envoie par un canal que
            seule la personne concernée lit.

            Rendre `accepted: False` pour une adresse inconnue transformerait le
            formulaire « mot de passe oublié » en annuaire de comptes.
        """
        instant = now or time.time()
        if user_id is None:
            return {"accepted": True, "ticket": None,
                    "note": ("Réponse identique pour un compte existant ou non "
                             "— c'est ce qui empêche d'énumérer les adresses.")}

        billet = ResetTicket(
            token=secrets.token_urlsafe(32), user_id=user_id,
            issued_at=instant, expires_at=instant + self.ttl_seconds,
        )
        with self._verrou:
            # Un seul jeton vivant par compte : deux jetons valides doublent
            # la surface d'attaque sans rien apporter.
            for jeton, existant in list(self._billets.items()):
                if existant.user_id == user_id:
                    del self._billets[jeton]
            self._billets[billet.token] = billet
        return {"accepted": True, "ticket": billet,
                "note": ("Réponse identique pour un compte existant ou non "
                         "— c'est ce qui empêche d'énumérer les adresses.")}

    def consume(self, token: str, now: Optional[float] = None) -> str:
        """
        Consomme un jeton et rend le compte visé.

        Args:
            token: Le jeton présenté.
            now: L'instant, pour les tests.

        Returns:
            L'identifiant du compte.

        Raises:
            ProtectionRefused: Jeton inconnu, déjà utilisé ou expiré. Le jeton
                est retiré **avant** toute validation du nouveau mot de passe :
                un jeton rejouable après un échec de politique serait un second
                mot de passe qui ne s'expire pas.
        """
        instant = now or time.time()
        with self._verrou:
            billet = self._billets.pop(token, None)
        if billet is None:
            raise ProtectionRefused(
                "Jeton inconnu ou déjà utilisé. Un jeton de réinitialisation "
                "ne sert qu'une fois."
            )
        if instant > billet.expires_at:
            raise ProtectionRefused(
                "Jeton expiré. Un jeton qui vit longtemps dort dans une boîte "
                "de courriels et vaut un second mot de passe."
            )
        return billet.user_id

    def report(self) -> Dict[str, Any]:
        """L'état du service et ses bornes."""
        return {
            "ttl_seconds": self.ttl_seconds,
            "live_tickets": len(self._billets),
            "persistence": "IN_MEMORY",
            "rules": [
                "La demande rend la même chose qu'un compte existe ou non.",
                "Un jeton sert **une** fois et est retiré avant toute "
                "validation du nouveau mot de passe.",
                "Un seul jeton vivant par compte.",
                "Le service ne connaît pas l'annuaire : l'appelant lui dit si "
                "le compte existe, et c'est l'appelant qui envoie le jeton.",
            ],
        }


def breach_disclosure(
    affected_user_ids: List[str],
    what_was_exposed: List[str],
    discovered_at: float,
    delivery_channel: str = "",
) -> Dict[str, Any]:
    """
    Prépare ce qu'une fuite oblige à dire, et refuse de prétendre l'avoir dit.

    Args:
        affected_user_ids: Les comptes concernés.
        what_was_exposed: Ce qui a réellement été exposé — « password_hash »,
            « email », « role »… Écrit tel quel, jamais minimisé.
        discovered_at: Quand la fuite a été découverte.
        delivery_channel: Le canal d'envoi configuré. Vide, rien n'est envoyé.

    Returns:
        Le dossier de notification et son état. `READY` veut dire « prêt à
        partir » ; `NOT_SENT` veut dire « rien n'est parti, et voici pourquoi ».
        **Aucun des deux ne veut dire « les personnes ont été prévenues »** —
        cette phrase-là ne peut être écrite que par ce qui envoie réellement.

    Raises:
        ProtectionRefused: Aucun compte, ou rien d'exposé. Une notification
            sans objet masquerait un incident qu'on n'a pas fini d'analyser.
    """
    if not affected_user_ids:
        raise ProtectionRefused(
            "Aucun compte concerné : une notification sans destinataire "
            "masquerait un incident dont l'analyse n'est pas finie."
        )
    if not what_was_exposed:
        raise ProtectionRefused(
            "Rien de déclaré comme exposé. « On ne sait pas encore » est une "
            "réponse à écrire dans `what_was_exposed`, pas à laisser vide."
        )

    envoye = bool(str(delivery_channel or "").strip())
    return {
        "state": PRET if envoye else NON_ENVOYE,
        "affected_count": len(affected_user_ids),
        "affected_user_ids": list(affected_user_ids),
        "exposed": list(what_was_exposed),
        "discovered_at": discovered_at,
        "must_disclose": [
            "ce qui a été exposé, sans le minimiser",
            "quand la fuite a été découverte",
            "ce que la personne doit faire maintenant (changer son mot de "
            "passe, et partout où elle l'a réutilisé)",
            "ce que la plateforme a fait depuis",
        ],
        "channel": delivery_channel or None,
        "reason": "" if envoye else (
            "Aucun canal d'envoi configuré : le dossier est prêt, rien n'est "
            "parti. Rapporter un envoi qui n'a pas eu lieu serait mentir sur "
            "la seule obligation qui compte vraiment dans une fuite."
        ),
        "note": (
            "`READY` ne veut pas dire « les personnes ont été prévenues ». "
            "Cette phrase ne peut être écrite que par ce qui envoie réellement, "
            "et ce module n'envoie rien."
        ),
    }


def protection_report() -> Dict[str, Any]:
    """
    Ce qu'ADR-029 devait encore, et où cela en est.

    Returns:
        Les trois obligations, leur état, et ce qui reste ouvert.
    """
    return {
        "owed_by_adr_029": [
            {"item": "lockout after repeated failures", "state": "IMPLEMENTED",
             "module": "LoginGuard",
             "limitation": "Compteurs en mémoire : perdus au redémarrage."},
            {"item": "password reset", "state": "IMPLEMENTED",
             "module": "PasswordResetService",
             "limitation": "Jetons en mémoire ; l'envoi appartient à "
                           "l'appelant, ce service ne délivre rien."},
            {"item": "breach notification", "state": "PREPARED_NOT_SENT",
             "module": "breach_disclosure",
             "limitation": "Aucun canal d'envoi configuré. Le dossier se "
                           "calcule ; l'envoi n'a pas lieu et n'est pas "
                           "rapporté comme ayant eu lieu."},
        ],
        "still_open": [
            "`GALSEN_STORAGE_BACKEND=sqlite` ne couvre ni les compteurs "
            "d'échecs ni les jetons de réinitialisation.",
            "Aucun canal de notification n'est configuré, donc aucune fuite "
            "ne serait annoncée automatiquement.",
        ],
    }
