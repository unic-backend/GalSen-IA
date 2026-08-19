"""
L'intention créative : ce qui est demandé, ce qui est permis, ce qui est interdit
(K05, §6 et §7 de la directive Creative Canvas).

## La phrase que ce module existe pour tenir

*« GalSen IA ne doit pas inventer de contenu créatif que l'utilisateur n'a pas
demandé. »* C'est une interdiction, et une interdiction n'est tenue que si
quelque chose peut dire, d'un élément précis, s'il a été demandé ou non.

## Le piège mesuré, et pourquoi il a fallu le mesurer

L'audit K01 a lu une implémentation de référence qui fait exactement l'inverse.
Dans `Higgsfield-Open`, choisir un objectif applique un mouvement de caméra :

```js
"Classic Anamorphic": { pan: 50, tilt: 0, zoom: 0, dolly: 0 },
```

Personne n'a demandé ce panoramique. Il est appliqué comme une décision, pas
proposé comme une suggestion, et rien dans le rendu ne dira jamais d'où il vient.
C'est le contre-exemple exact de §6 — et il est utile, parce qu'il montre que la
faute ne ressemble pas à une faute : elle ressemble à une commodité.

## Les quatre statuts, et pourquoi trois ne suffisent pas

§6 nomme trois catégories : requis, optionnel, interdit. Il en manque une, et
c'est la plus dangereuse :

- `REQUIRED`   — demandé, doit apparaître.
- `OPTIONAL`   — explicitement autorisé, peut apparaître.
- `FORBIDDEN`  — explicitement exclu, ne doit jamais apparaître.
- `NOT_REQUESTED` — **jamais mentionné**.

Un élément jamais mentionné n'est pas optionnel. Le confondre avec `OPTIONAL`
est précisément ce qui autorise un préréglage à ajouter un panoramique : rien ne
l'interdisait, donc on le pose. Ici, `NOT_REQUESTED` refuse au même titre que
`FORBIDDEN` — avec un motif différent, parce que les deux refus ne se corrigent
pas de la même façon : l'un se lève en le demandant, l'autre pas.

`NOT_REQUESTED` n'est jamais **déclaré** : c'est la réponse rendue pour tout ce
qui ne figure pas dans l'intention. §7 le dit autrement — `UNKNOWN` ne se
convertit pas en hypothèse.

## Ce que le module refuse de faire

**Il ne complète pas une intention.** Aucun élément par défaut, aucun élément
déduit d'un autre, aucun style « habituel pour ce genre de plan ».

**Il ne fusionne pas une suggestion.** `offer()` rend des propositions et ne
touche pas à l'intention. Une suggestion devient une décision quand quelqu'un
la demande, jamais parce qu'elle était disponible.

**Il ne normalise pas le texte demandé.** La valeur est conservée telle qu'elle
a été écrite ; seule la clé de comparaison est pliée, des deux côtés, pour que
« Caméra » et « camera » se rejoignent sans qu'aucune écriture soit privilégiée.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..text_normalization import strip_accents

#: Les statuts qu'une personne peut **déclarer** sur un élément (§6).
REQUIS = "REQUIRED"
OPTIONNEL = "OPTIONAL"
INTERDIT = "FORBIDDEN"
STATUTS_DECLARES = (REQUIS, OPTIONNEL, INTERDIT)

#: Le statut rendu pour un élément absent de l'intention. Il n'est jamais
#: déclaré : personne n'écrit « ceci n'a pas été demandé », c'est ce qui reste
#: quand rien n'a été dit.
NON_DEMANDE = "NOT_REQUESTED"

#: Les statuts qui autorisent un élément à figurer dans un plan.
STATUTS_AUTORISANTS = (REQUIS, OPTIONNEL)

#: Les verdicts d'un plan comparé à son intention. Ils sont **trois** et non
#: deux : « il manque un élément requis » et « il y a un élément que personne
#: n'a demandé » ne se corrigent pas de la même façon, et un mot unique pour les
#: deux ferait chercher au mauvais endroit.
CONFORME = "MATCHES_INTENT"
CONTREDIT = "VIOLATES_INTENT"
CONTENU_NON_DEMANDE = "UNREQUESTED_CONTENT"

#: Rendu quand aucun plan n'a été fourni. `None` n'est pas `()` : un plan
#: absent n'a pas été vérifié, un plan vide l'a été et lui manque tout.
NON_VERIFIE = "NOT_CHECKED"

#: Les natures d'élément déclarées. Une nature inconnue est refusée pour être
#: **ajoutée ici** : une nature libre laisserait passer « mouvement » et
#: « movement » comme deux choses différentes, et l'interdit posé sur l'une ne
#: couvrirait pas l'autre.
NATURES = (
    "entity",          # une personne, un personnage
    "object",          # un objet présent dans le plan
    "place",           # un lieu
    "action",          # ce qui se passe
    "style",           # une famille de style (voir style.py)
    "camera_movement",  # un mouvement de caméra (voir direction.py)
    "lighting",        # une intention lumineuse
    "language",        # une langue parlée ou écrite
    "audio",           # musique, ambiance, voix
    "text_overlay",    # un texte incrusté
    "effect",          # un effet visuel
)


class IntentRefused(ValueError):
    """Une intention impossible telle quelle, ou un élément non déclarable."""


def _cle(nature: str, valeur: str) -> Tuple[str, str]:
    """
    Réduit un élément à une clé comparable.

    Le pliage s'applique **des deux côtés** de la comparaison : « caméra » et
    « camera » se rejoignent, et aucune écriture n'est privilégiée. C'est le
    même geste que `style.py` applique déjà aux noms de style.
    """
    valeur_pliee = strip_accents(str(valeur or "").lower())
    valeur_pliee = " ".join(valeur_pliee.replace("-", " ").replace("_", " ").split())
    return (str(nature or "").strip().lower(), valeur_pliee)


@dataclass(frozen=True)
class IntentElement:
    """
    Un élément créatif, avec le statut que la personne lui a donné.

    Attributes:
        kind: La nature, parmi `NATURES`.
        value: La valeur **telle qu'elle a été écrite**. Jamais normalisée :
            c'est ce que la personne a demandé, et un refus doit pouvoir citer
            ses mots.
        status: Le statut déclaré, parmi `STATUTS_DECLARES`.
        stated_as: La phrase d'où l'élément est tiré. Vide quand l'élément a été
            saisi directement. Elle rend le refus contestable : sans elle, « ce
            n'était pas demandé » ne s'oppose à rien.
    """

    kind: str
    value: str
    status: str
    stated_as: str = ""

    def __post_init__(self) -> None:
        if self.kind not in NATURES:
            raise IntentRefused(
                f"Nature « {self.kind} » non déclarée. Déclarées : {list(NATURES)}. "
                "Une nature libre laisserait un interdit posé sur l'une ne pas "
                "couvrir l'autre."
            )
        if self.status not in STATUTS_DECLARES:
            raise IntentRefused(
                f"Statut « {self.status} » non déclarable. Déclarables : "
                f"{list(STATUTS_DECLARES)}. « {NON_DEMANDE} » est ce que rend "
                "l'intention pour un élément absent ; il ne se déclare pas."
            )
        if not str(self.value).strip():
            raise IntentRefused(
                "Un élément sans valeur ne décide rien et ne se conteste pas."
            )

    @property
    def key(self) -> Tuple[str, str]:
        """La clé de comparaison — nature et valeur pliées."""
        return _cle(self.kind, self.value)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "kind": self.kind, "value": self.value, "status": self.status,
            "stated_as": self.stated_as,
        }


@dataclass(frozen=True)
class CreativeIntent:
    """
    Ce qui a été demandé, ce qui est permis, ce qui est exclu.

    Attributes:
        elements: Les éléments déclarés. Un même élément ne peut pas porter deux
            statuts : la contradiction est refusée à la construction, pas
            arbitrée en silence.
        request: La demande d'origine, conservée telle quelle.
    """

    elements: Tuple[IntentElement, ...] = ()
    request: str = ""

    def __post_init__(self) -> None:
        vus: Dict[Tuple[str, str], str] = {}
        for element in self.elements:
            precedent = vus.get(element.key)
            if precedent is not None and precedent != element.status:
                raise IntentRefused(
                    f"« {element.value} » ({element.kind}) est à la fois "
                    f"{precedent} et {element.status}. Une contradiction "
                    "d'intention se lève avec la personne, elle ne s'arbitre pas "
                    "à sa place."
                )
            vus[element.key] = element.status

    def status_of(self, kind: str, value: str) -> str:
        """
        Le statut d'un élément.

        Args:
            kind: La nature cherchée.
            value: La valeur cherchée.

        Returns:
            `REQUIRED`, `OPTIONAL`, `FORBIDDEN`, ou `NOT_REQUESTED` quand
            l'élément n'a jamais été mentionné. **`NOT_REQUESTED` n'est pas
            `OPTIONAL`** : c'est l'absence d'une décision, pas une permission.
        """
        cible = _cle(kind, value)
        for element in self.elements:
            if element.key == cible:
                return element.status
        return NON_DEMANDE

    def may_include(self, kind: str, value: str) -> Dict[str, Any]:
        """
        Dit si un élément a le droit de figurer dans un plan, et pourquoi.

        Args:
            kind: La nature de l'élément.
            value: Sa valeur.

        Returns:
            `allowed`, le `status` qui décide, et un `reason` qui nomme le geste
            qui lèverait le refus. Les deux refus ne se corrigent pas de la même
            façon : un interdit se lève en changeant d'avis, un non-demandé se
            lève en le demandant.
        """
        statut = self.status_of(kind, value)
        if statut in STATUTS_AUTORISANTS:
            return {"allowed": True, "status": statut, "reason": ""}
        if statut == INTERDIT:
            return {
                "allowed": False, "status": statut,
                "reason": (f"« {value} » a été explicitement exclu. Seul un "
                           "changement d'intention le lève."),
            }
        return {
            "allowed": False, "status": NON_DEMANDE,
            "reason": (f"« {value} » n'a jamais été demandé. Ce n'est pas une "
                       "permission implicite : il faut le demander pour qu'il "
                       "apparaisse."),
        }

    def by_status(self, status: str) -> List[IntentElement]:
        """
        Les éléments portant un statut déclaré.

        Args:
            status: Un statut de `STATUTS_DECLARES`.

        Returns:
            Les éléments concernés, dans l'ordre de déclaration.

        Raises:
            IntentRefused: Si le statut n'est pas déclarable — `NOT_REQUESTED`
                n'a pas de liste, puisqu'il désigne tout le reste du monde.
        """
        if status not in STATUTS_DECLARES:
            raise IntentRefused(
                f"« {status} » n'est pas un statut déclaré. `{NON_DEMANDE}` "
                "n'a pas de liste : il désigne tout ce qui n'a pas été dit."
            )
        return [e for e in self.elements if e.status == status]

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "request": self.request,
            "elements": [e.as_dict() for e in self.elements],
            "required": [e.value for e in self.by_status(REQUIS)],
            "optional": [e.value for e in self.by_status(OPTIONNEL)],
            "forbidden": [e.value for e in self.by_status(INTERDIT)],
        }


def declare(request: str,
            required: Iterable[Tuple[str, str]] = (),
            optional: Iterable[Tuple[str, str]] = (),
            forbidden: Iterable[Tuple[str, str]] = (),
            stated_as: str = "") -> CreativeIntent:
    """
    Construit une intention à partir de trois listes explicites.

    Args:
        request: La demande d'origine, conservée telle quelle.
        required: Les couples `(nature, valeur)` requis.
        optional: Les couples explicitement autorisés.
        forbidden: Les couples explicitement exclus.
        stated_as: La phrase d'où viennent ces éléments, quand elle est connue.

    Returns:
        L'intention correspondante.

    Raises:
        IntentRefused: Nature inconnue, valeur vide, ou contradiction.

    Note:
        Les trois listes sont **séparées et vides par défaut**. Rien n'est
        déduit de `request` : extraire des éléments d'un texte libre est une
        analyse, et une analyse qui se tromperait produirait exactement ce que
        §6 interdit — un élément que personne n'a demandé, mais présenté comme
        demandé.
    """
    elements: List[IntentElement] = []
    for couples, statut in ((required, REQUIS), (optional, OPTIONNEL),
                            (forbidden, INTERDIT)):
        for nature, valeur in couples:
            elements.append(IntentElement(kind=nature, value=valeur,
                                          status=statut, stated_as=stated_as))
    return CreativeIntent(elements=tuple(elements), request=request)


def offer(intent: CreativeIntent,
          suggestions: Iterable[Tuple[str, str]],
          source: str = "") -> Dict[str, Any]:
    """
    Propose des éléments **sans jamais les appliquer**.

    Args:
        intent: L'intention en cours. Elle n'est pas modifiée.
        suggestions: Les couples `(nature, valeur)` proposés.
        source: Ce qui propose — un préréglage, un modèle, une personne.

    Returns:
        Chaque suggestion avec son statut actuel et le fait qu'elle est
        `applied: False`, plus l'intention inchangée. **Le retour ne contient
        aucune intention modifiée**, et c'est le seul point du module qui
        compte : `LENS_MOTION_PRESET` fait la même proposition et la pose
        (K01). Une suggestion déjà interdite est rendue avec son refus, pas
        retirée de la liste — la personne doit voir ce qui lui a été proposé
        contre son intention.
    """
    proposees = []
    for nature, valeur in suggestions:
        verdict = intent.may_include(nature, valeur)
        proposees.append({
            "kind": nature, "value": valeur,
            "status": verdict["status"], "would_be_allowed": verdict["allowed"],
            "reason": verdict["reason"], "applied": False,
        })
    return {
        "source": source,
        "suggestions": proposees,
        "applied_count": 0,
        "intent_unchanged": True,
        "note": ("Une suggestion devient une décision quand quelqu'un la "
                 "demande, jamais parce qu'elle était disponible."),
    }


def accept(intent: CreativeIntent,
           accepted: Iterable[Tuple[str, str]],
           status: str = OPTIONNEL,
           stated_as: str = "") -> CreativeIntent:
    """
    Ajoute à l'intention des éléments **qu'une personne a explicitement acceptés**.

    Args:
        intent: L'intention de départ.
        accepted: Les couples `(nature, valeur)` acceptés.
        status: Le statut à leur donner, parmi `STATUTS_DECLARES`.
        stated_as: Ce qui atteste l'acceptation.

    Returns:
        Une **nouvelle** intention. L'originale n'est pas modifiée, pour qu'une
        intention puisse être comparée à ce qu'elle était avant.

    Raises:
        IntentRefused: Statut non déclarable, ou contradiction avec un élément
            déjà déclaré.

    Note:
        C'est la seule porte par laquelle une suggestion entre. Elle demande un
        appel séparé, avec `stated_as` : accepter est un acte, pas la
        continuation d'une proposition.
    """
    if status not in STATUTS_DECLARES:
        raise IntentRefused(
            f"Statut « {status} » non déclarable. Déclarables : "
            f"{list(STATUTS_DECLARES)}."
        )
    nouveaux = [IntentElement(kind=n, value=v, status=status,
                              stated_as=stated_as)
                for n, v in accepted]
    return CreativeIntent(elements=tuple(intent.elements) + tuple(nouveaux),
                          request=intent.request)


def check_plan(intent: CreativeIntent,
               planned: Optional[Iterable[Tuple[str, str]]] = None
               ) -> Dict[str, Any]:
    """
    Compare un plan à l'intention qui l'a commandé.

    Args:
        intent: L'intention déclarée.
        planned: Les couples `(nature, valeur)` que le plan contient. `None`
            veut dire qu'aucun plan n'a été fourni — pas qu'il est vide.

    Returns:
        Le verdict, et **trois listes séparées** :

        - `forbidden_present` — un élément explicitement exclu est là.
        - `required_missing` — un élément demandé manque.
        - `not_requested_present` — un élément que personne n'a mentionné.

    Note:
        Les trois manquements ne valent pas la même chose, et le verdict le dit :

        - `VIOLATES_INTENT` — un interdit est présent, ou un requis manque. Ce
          sont des fautes sans ambiguïté : quelqu'un a dit oui ou non, et le
          plan répond le contraire.
        - `UNREQUESTED_CONTENT` — seuls des éléments jamais mentionnés
          s'ajoutent. **Ce n'est pas automatiquement une faute** : un plan
          contient légitimement des choses qui viennent de l'état du monde et
          non de la demande. C'est un verdict distinct parce que la correction
          est différente — il faut regarder d'où vient l'élément, pas retirer
          une décision.
        - `NOT_CHECKED` — aucun plan fourni. Un plan vide, lui, est vérifié, et
          tout élément requis y manque.
    """
    if planned is None:
        return {
            "verdict": NON_VERIFIE,
            "forbidden_present": [], "required_missing": [],
            "not_requested_present": [], "checked_count": None,
            "note": ("Aucun plan fourni. Un plan vide se vérifie ; un plan "
                     "absent ne se déduit pas."),
        }

    couples = [(str(nature), str(valeur)) for nature, valeur in planned]
    presents = {_cle(nature, valeur) for nature, valeur in couples}

    interdits = [{"kind": n, "value": v} for n, v in couples
                 if intent.status_of(n, v) == INTERDIT]
    non_demandes = [{"kind": n, "value": v} for n, v in couples
                    if intent.status_of(n, v) == NON_DEMANDE]
    manquants = [{"kind": e.kind, "value": e.value}
                 for e in intent.by_status(REQUIS) if e.key not in presents]

    if interdits or manquants:
        verdict = CONTREDIT
    elif non_demandes:
        verdict = CONTENU_NON_DEMANDE
    else:
        verdict = CONFORME

    return {
        "verdict": verdict,
        "forbidden_present": interdits,
        "required_missing": manquants,
        "not_requested_present": non_demandes,
        "checked_count": len(couples),
        "note": ("Un élément non demandé n'est pas forcément une invention : "
                 "il peut venir de l'état du monde. Le verdict est distinct "
                 "pour qu'on aille voir d'où il vient."),
    }


def intent_report(intent: Optional[CreativeIntent] = None) -> Dict[str, Any]:
    """
    Ce que le contrat d'intention garantit, et ce qu'il refuse.

    Args:
        intent: Une intention à décrire. `None` rend seulement le vocabulaire.

    Returns:
        Le vocabulaire déclaré, les règles tenues, et l'intention quand elle est
        fournie.
    """
    rapport: Dict[str, Any] = {
        "declarable_statuses": list(STATUTS_DECLARES),
        "returned_status_for_absent": NON_DEMANDE,
        "kinds": list(NATURES),
        "plan_verdicts": [CONFORME, CONTREDIT, CONTENU_NON_DEMANDE, NON_VERIFIE],
        "rules": [
            "NOT_REQUESTED n'est pas OPTIONAL : l'absence de mention n'est pas "
            "une permission.",
            "Une suggestion n'est jamais appliquée ; elle est proposée, et "
            "acceptée par un appel séparé.",
            "Une contradiction d'intention est refusée, jamais arbitrée.",
            "Rien n'est déduit du texte de la demande : les trois listes sont "
            "explicites.",
            "La valeur demandée est conservée telle qu'écrite ; seule la clé "
            "de comparaison est pliée.",
            "Un plan absent rend NOT_CHECKED ; un plan vide est vérifié.",
            "VIOLATES_INTENT et UNREQUESTED_CONTENT restent deux verdicts : "
            "ils ne se corrigent pas de la même façon.",
        ],
    }
    if intent is not None:
        rapport["intent"] = intent.as_dict()
    return rapport
