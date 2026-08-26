"""
Les contrôles qui portent la critique — déterministes, jamais l'avis du modèle.

## Pourquoi aucun critique ici n'interroge un modèle

`agents/verifier/agent.py` refuse explicitement de demander au modèle s'il avait
raison : *« ce serait mesurer la confiance du modèle en lui-même, ce qu'une
couche de vérification existe précisément pour éviter »*. Un critique bâti sur
la même question aurait la même faille, en plus coûteux — et un modèle qui
valide sa propre réponse la valide presque toujours.

Chaque contrôle ci-dessous se décide donc sur le texte et sur les constats, sans
second appel. Ce qu'ils y perdent en portée, ils le gagnent en signification :
un constat produit ici est reproductible, et il peut être faux **pour une raison
qu'on peut aller lire**.

## Ce qui n'est pas prétendu

Ces contrôles n'attrapent pas « les hallucinations ». Ils attrapent des formes
précises : une affirmation contredite par un constat, un calcul faux, une
certitude affichée sans rien derrière, une réponse vide. Une hallucination
plausible et non contredite passe — et le dire ici vaut mieux que de laisser
croire à un filet qui n'existe pas.
"""

import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

#: Gravités. `BLOQUANT` demande une autre tentative ; `SIGNAL` est consigné et
#: n'en déclenche aucune. Deux niveaux suffisent : un troisième inviterait à
#: ranger au milieu ce qu'on n'a pas su trancher.
BLOQUANT = "blocking"
SIGNAL = "advisory"

#: Marqueurs de certitude. Utilisés seulement pour le contrôle d'assurance,
#: jamais pour juger du fond.
_CERTITUDES = (
    "il est certain", "c'est certain", "sans aucun doute", "assurément",
    "il est prouvé", "il est établi", "de toute évidence", "incontestablement",
    "certainly", "without a doubt", "it is proven", "undoubtedly",
)

#: `a op b = c`, avec des nombres décimaux. Volontairement étroit : élargir
#: attraperait des égalités qui ne sont pas des calculs (« x = 3 »).
#
# La borne de fin est `(?!\d)(?!\.\d)` et non `(?![\w.])` : le point final d'une
# phrase suit très souvent le résultat — « … = 5. » — et l'interdire faisait
# rater le cas le plus courant. Ce qu'il faut écarter, c'est un chiffre qui
# continue (« 5.2 »), pas une ponctuation.
_CALCUL = re.compile(
    r"(?<![\w.])(\d+(?:[.,]\d+)?)\s*([+\-*/×÷])\s*(\d+(?:[.,]\d+)?)"
    r"\s*=\s*(\d+(?:[.,]\d+)?)(?!\d)(?!\.\d)"
)


@dataclass(frozen=True)
class Constat:
    """
    Ce qu'un contrôle a trouvé, et ce qu'il en coûte.

    Attributes:
        code: Identifiant stable du contrôle, pour compter et pour tester.
        gravite: `BLOQUANT` ou `SIGNAL`.
        message: Ce qui ne va pas, en une phrase.
        consigne: Ce qu'une nouvelle tentative doit faire différemment. Vide
            quand le constat n'appelle aucune correction — un signal informe,
            il ne dirige pas.
        details: De quoi retrouver le constat sans relire tout le texte.
    """

    code: str
    gravite: str
    message: str
    consigne: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def bloquant(self) -> bool:
        """Vrai si ce constat justifie une autre tentative."""
        return self.gravite == BLOQUANT

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le constat, pour la trace et pour la réponse."""
        return {
            "code": self.code,
            "severity": self.gravite,
            "message": self.message,
            "instruction": self.consigne,
            "details": dict(self.details),
        }


def reponse_vide(texte: str, **_: Any) -> List[Constat]:
    """
    Une réponse vide n'est pas une réponse.

    **Vide veut dire vide.** La première version de ce contrôle exigeait trois
    mots, et c'était une erreur de conception : « 42 », « Oui, à Dakar. » et
    « Non. » sont des réponses complètes à des questions qui n'en demandent pas
    davantage. Un vérificateur qui relance une génération pour cela coûte un
    appel de modèle et n'améliore rien — il pénalise la concision, qui est une
    qualité.

    Args:
        texte: La réponse produite.

    Returns:
        Un constat bloquant si le texte ne contient aucun caractère utile.
    """
    if (texte or "").strip():
        return []
    return [Constat(
        code="empty_answer",
        gravite=BLOQUANT,
        message="La réponse est vide : le modèle n'a rien produit.",
        consigne="Rédige une réponse complète à la question posée.",
        details={"length": len(texte or "")},
    )]


def calcul_faux(texte: str, **_: Any) -> List[Constat]:
    """
    Vérifie les calculs écrits sous la forme `a op b = c`.

    C'est le seul contrôle de ce module qui puisse prouver qu'une réponse a
    tort, plutôt que constater qu'elle n'est pas étayée. Il travaille en
    `Decimal` : `0.1 + 0.2` vaut `0.3` pour un lecteur humain, et le signaler
    comme faux serait un faux positif que personne ne pardonnerait.

    Args:
        texte: La réponse produite.

    Returns:
        Un constat bloquant par calcul faux.
    """
    constats: List[Constat] = []
    for brut_a, operateur, brut_b, brut_attendu in _CALCUL.findall(texte or ""):
        try:
            a = Decimal(brut_a.replace(",", "."))
            b = Decimal(brut_b.replace(",", "."))
            attendu = Decimal(brut_attendu.replace(",", "."))
        except InvalidOperation:
            continue

        try:
            reel = _appliquer(operateur, a, b)
        except (DivisionByZero, InvalidOperation):
            continue
        if reel is None or reel == attendu:
            continue

        constats.append(Constat(
            code="arithmetic_error",
            gravite=BLOQUANT,
            message=f"« {brut_a} {operateur} {brut_b} = {brut_attendu} » est faux.",
            consigne=f"Corrige le calcul : {brut_a} {operateur} {brut_b} donne {reel}.",
            details={"written": brut_attendu, "computed": str(reel)},
        ))
    return constats


def _appliquer(operateur: str, a: Decimal, b: Decimal) -> Optional[Decimal]:
    """Applique l'opérateur, ou rend `None` s'il n'est pas reconnu."""
    if operateur == "+":
        return a + b
    if operateur == "-":
        return a - b
    if operateur in ("*", "×"):
        return a * b
    if operateur in ("/", "÷"):
        return a / b if b != 0 else None
    return None


def contredit_les_constats(
    texte: str, evidence: Optional[Sequence[Dict[str, Any]]] = None, **_: Any
) -> List[Constat]:
    """
    Confronte la réponse aux constats rassemblés, via l'évaluateur existant.

    `src/knowledge_engine/factual_evaluation.py` sait déjà découper une réponse
    en affirmations et porter un verdict sur chacune face à des passages. En
    écrire un second ici garantirait qu'ils finissent par ne plus dire la même
    chose. Seul `DISPUTED` est retenu comme bloquant : *« un passage parle de
    cela et dit le contraire »*. `UNSUPPORTED` — « aucun passage n'en parle » —
    est banal dès que la réponse dépasse les constats, ce qu'elle a le droit de
    faire.

    Args:
        texte: La réponse produite.
        evidence: Les constats, à la forme rendue par le chercheur.

    Returns:
        Un constat bloquant par affirmation contredite.
    """
    passages = [c for c in (evidence or []) if isinstance(c, dict) and c.get("content")]
    if not passages or not (texte or "").strip():
        return []

    from ..knowledge_engine.factual_evaluation import evaluate_answer

    try:
        evaluation = evaluate_answer(texte, passages)
    except Exception as erreur:  # noqa: BLE001 — un critique en panne ne bloque pas la réponse
        # Journalisé, jamais avalé en silence : la première version de ce
        # critique lisait `evaluation["claims"]` en croyant y trouver une liste
        # d'affirmations, alors que c'est un **compte**. L'itération levait, ce
        # `except` l'absorbait, et le critique ne trouvait jamais rien — un
        # défaut invisible que seul un test d'intégration a révélé.
        logger.warning("Critique factuel indisponible : %s", erreur)
        return []

    constats: List[Constat] = []
    # `evaluate_answer` range les affirmations contredites sous `disputed`, et
    # chacune porte le passage qui la contredit sous `passage`.
    for entree in evaluation.get("disputed", []):
        if not isinstance(entree, dict):
            continue
        affirmation = str(entree.get("claim", ""))[:160]
        constats.append(Constat(
            code="contradicted_by_evidence",
            gravite=BLOQUANT,
            message=f"Un constat rassemblé dit le contraire de : « {affirmation} »",
            consigne=(
                "Reprends cette affirmation : un constat fourni la contredit. "
                "Suis le constat, ou dis explicitement que les sources divergent."
            ),
            details={"claim": affirmation, "passage": entree.get("passage")},
        ))
    return constats


def assurance_sans_appui(
    texte: str,
    evidence: Optional[Sequence[Dict[str, Any]]] = None,
    grounding_status: str = "",
    **_: Any,
) -> List[Constat]:
    """
    Une certitude affichée alors que rien n'est vérifié.

    Ce contrôle ne juge pas le fond : il juge l'écart entre l'assurance du ton
    et l'état de l'ancrage. C'est exactement le mensonge que le reste de la
    plateforme refuse — dire « il est établi que » quand rien n'a été établi.

    Args:
        texte: La réponse produite.
        evidence: Les constats rassemblés.
        grounding_status: `GROUNDED`, `UNGROUNDED` ou `NOT_CHECKED`.

    Returns:
        Un constat bloquant si le ton dépasse ce qui est étayé.
    """
    if str(grounding_status).upper() == "GROUNDED":
        return []
    if any(isinstance(c, dict) and c.get("verified") for c in (evidence or [])):
        return []

    minuscules = (texte or "").lower()
    trouves = [marqueur for marqueur in _CERTITUDES if marqueur in minuscules]
    if not trouves:
        return []

    return [Constat(
        code="unsupported_certainty",
        gravite=BLOQUANT,
        message=(
            f"La réponse affirme avec certitude ({', '.join(trouves[:3])}) "
            f"alors que l'ancrage est « {grounding_status or 'inconnu'} »."
        ),
        consigne=(
            "Retire les marques de certitude : rien de vérifié ne les soutient. "
            "Dis ce que tu sais, et dis que ce n'est pas vérifié."
        ),
        details={"markers": trouves},
    )]


def machinerie_exposee(texte: str, **_: Any) -> List[Constat]:
    """
    La réponse parle des rouages de la plateforme au lieu de répondre.

    Signal, pas blocage : c'est un défaut de forme, et relancer une génération
    pour un mot mal choisi coûte plus cher que le défaut.

    Args:
        texte: La réponse produite.

    Returns:
        Un signal si un nom de rouage interne apparaît.
    """
    rouages = ("planner", "researcher", "orchestrateur", "workflow", "agent researcher")
    minuscules = (texte or "").lower()
    trouves = [mot for mot in rouages if mot in minuscules]
    if not trouves:
        return []
    return [Constat(
        code="internals_exposed",
        gravite=SIGNAL,
        message=f"La réponse nomme des rouages internes : {', '.join(trouves)}.",
        details={"terms": trouves},
    )]


#: Les contrôles appliqués, dans l'ordre. Une liste au niveau du module plutôt
#: qu'une classe : y ajouter un contrôle ne doit demander qu'une ligne.
CONTROLES = (
    reponse_vide,
    calcul_faux,
    contredit_les_constats,
    assurance_sans_appui,
    machinerie_exposee,
)


def critiquer(
    texte: str,
    evidence: Optional[Sequence[Dict[str, Any]]] = None,
    grounding_status: str = "",
) -> List[Constat]:
    """
    Applique tous les contrôles et rend ce qu'ils ont trouvé.

    Args:
        texte: La réponse à critiquer.
        evidence: Les constats rassemblés par l'orchestration.
        grounding_status: L'état d'ancrage calculé avant la génération.

    Returns:
        Les constats, bloquants d'abord. Une liste vide veut dire « aucun
        contrôle n'a rien trouvé », jamais « la réponse est juste ».
    """
    constats: List[Constat] = []
    for controle in CONTROLES:
        constats.extend(controle(
            texte=texte, evidence=evidence, grounding_status=grounding_status
        ))
    return sorted(constats, key=lambda c: 0 if c.bloquant else 1)
