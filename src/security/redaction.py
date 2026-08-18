"""
Redaction: the one list of names whose value is never written down.

A token that reaches a log file has left the platform. Log files are copied,
shipped to an aggregator, pasted into a bug report, and read by people who were
never granted the access that token carries — and unlike a database row, nobody
ever goes back and deletes a line from last month's log.

The repository already had this list, in `AgentContext._SENSITIVE_ARG_NAMES`,
private to one class. Every other place that needed it would have written its
own, and the second copy is where the two start to disagree. This module is the
single list, and the redactors that use it.

Two design points worth keeping:

**Names, not values.** Nothing here tries to *recognise* a secret in a string —
that game is unwinnable, and a redactor that mostly works is worse than none,
because it teaches people to trust it. What is redacted is anything whose
**name** says it carries a secret.

**Redaction shows that something was removed.** A field that vanishes silently
is indistinguishable from a field that was never set, and someone debugging
would spend an hour on the wrong question.
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Iterable, Mapping

#: Marque laissée à la place d'une valeur retirée. Elle est visible à dessein.
MASQUE = "***"

#: Les fragments de nom qui trahissent un secret. La liste est volontairement
#: large : un faux positif masque un champ anodin, un faux négatif publie un
#: jeton. Les deux erreurs ne coûtent pas le même prix.
NOMS_SENSIBLES: FrozenSet[str] = frozenset({
    "password", "passwd", "mot_de_passe",
    "token", "jeton", "access_token", "refresh_token", "id_token",
    "secret", "client_secret",
    "api_key", "apikey", "key",
    "authorization", "auth",
    "credential", "credentials",
    "cookie", "session_id",
    "private_key", "signature",
})


#: Les noms qui portent un secret **sans ambiguïté**. Sous-ensemble volontaire
#: de `NOMS_SENSIBLES`, et la différence n'est pas une divergence : les deux
#: listes répondent à deux questions.
#:
#: `NOMS_SENSIBLES` sert au **masquage**, où un faux positif ne coûte qu'un
#: champ caché. Celle-ci sert à la **garde de journalisation**, où un faux
#: positif signale une faute qui n'existe pas — et une garde qui crie à tort est
#: une garde que quelqu'un finit par désactiver.
#:
#: L'exemple qui a produit cette séparation : le connecteur de stockage
#: journalise sa `key`, qui est un chemin d'objet et non un secret. `key` reste
#: masqué à l'écriture, il n'est plus une faute à la lecture.
NOMS_CERTAINEMENT_SECRETS: FrozenSet[str] = frozenset({
    "password", "passwd", "mot_de_passe",
    "access_token", "refresh_token", "id_token",
    "client_secret", "secret",
    "api_key", "apikey", "private_key",
    "authorization", "credential", "credentials",
    "cookie", "signature",
})


def is_sensitive(name: str) -> bool:
    """
    Indique si un nom annonce une valeur à ne pas écrire.

    Utilisé pour **masquer**. Large à dessein : un faux positif cache un champ
    anodin, un faux négatif publie un jeton.

    Args:
        name: Le nom du champ, de l'argument ou de la variable.

    Returns:
        True si son contenu doit être masqué.
    """
    minuscule = (name or "").lower()
    return any(fragment in minuscule for fragment in NOMS_SENSIBLES)


def is_certainly_secret(name: str) -> bool:
    """
    Indique si un nom porte un secret sans ambiguïté possible.

    Utilisé pour **accuser** — signaler qu'un code journalise un secret. Plus
    étroit que `is_sensitive` : accuser à tort finit par faire désactiver la
    garde, ce qui coûte plus cher que la faute qu'elle cherche.

    Args:
        name: Le nom du champ, de l'argument ou de la variable.

    Returns:
        True si journaliser cette valeur est une faute.
    """
    minuscule = (name or "").lower()
    return any(fragment in minuscule for fragment in NOMS_CERTAINEMENT_SECRETS)


def redact_mapping(data: Mapping[str, Any], depth: int = 4) -> Dict[str, Any]:
    """
    Recopie un dictionnaire en masquant les valeurs sensibles.

    Le masquage est **récursif** : un jeton rangé sous `credentials.access_token`
    est aussi dangereux qu'à la racine, et c'est là qu'il se trouve en pratique.

    Args:
        data: Le dictionnaire à recopier.
        depth: Profondeur maximale. Au-delà, la valeur est remplacée par son
            type — une structure trop profonde pour être parcourue est aussi
            trop profonde pour être publiée en confiance.

    Returns:
        Une copie masquée. L'original n'est pas modifié.
    """
    if depth <= 0:
        return {cle: f"<{type(valeur).__name__}>" for cle, valeur in data.items()}

    masque: Dict[str, Any] = {}
    for cle, valeur in data.items():
        if is_sensitive(str(cle)):
            masque[cle] = MASQUE
        elif isinstance(valeur, Mapping):
            masque[cle] = redact_mapping(valeur, depth - 1)
        elif isinstance(valeur, (list, tuple)):
            masque[cle] = [
                redact_mapping(element, depth - 1) if isinstance(element, Mapping)
                else element
                for element in valeur
            ]
        else:
            masque[cle] = valeur
    return masque


def redact_pairs(pairs: Iterable[tuple], limit: int = 200) -> str:
    """
    Rend une suite de couples nom/valeur, masquée, pour un message de journal.

    Args:
        pairs: Les couples `(nom, valeur)`.
        limit: Longueur maximale d'une valeur rendue.

    Returns:
        Les couples, séparés par des virgules, valeurs sensibles masquées.
    """
    morceaux = []
    for nom, valeur in pairs:
        if is_sensitive(str(nom)):
            morceaux.append(f"{nom}={MASQUE}")
            continue
        texte = str(valeur)
        if len(texte) > limit:
            texte = texte[:limit] + "..."
        morceaux.append(f"{nom}={texte}")
    return ", ".join(morceaux)


def redaction_report() -> Dict[str, Any]:
    """
    Ce que cette couche masque, et ce qu'elle ne prétend pas faire.

    Returns:
        La liste des noms surveillés et la limite assumée.
    """
    return {
        "names": sorted(NOMS_SENSIBLES),
        "marker": MASQUE,
        "limitation": (
            "Le masquage porte sur les **noms**, jamais sur la reconnaissance "
            "d'un secret dans une chaîne : un détecteur qui marche à peu près "
            "est pire qu'aucun, parce qu'on finit par lui faire confiance."
        ),
    }
