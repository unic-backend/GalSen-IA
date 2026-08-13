"""
Récupérer selon la portée, et le dire (VOLET 35, chapitres 04 et 05).

La base porte deux axes depuis l'ADR-019, et la récupération les ignorait : une
question sur le foncier sénégalais et une question sur l'irrigation goutte à
goutte étaient traitées de la même façon. Or elles ne se ressemblent pas.

```
question → détection de portée → récupération → réponse qui dit d'où elle vient
```

## Trois règles, et une seule est une interdiction

1. **Les sujets nationaux ne retombent jamais sur le mondial.** Droit,
   administration, langues : sans source nationale, la réponse est « je n'ai pas
   cette information pour ce pays ». Répondre le droit d'ailleurs serait fluide,
   plausible, et faux là où ça coûte un terrain.
2. **Pour tout le reste, le local enrichit, il ne remplace pas.** L'agronomie du
   mil voyage ; les variétés, les pluies et les prix du Sénégal, non. La réponse
   porte les deux et dit quel passage vient d'où.
3. **La réponse dit sa portée**, comme la récupération dit déjà si elle était
   sémantique ou lexicale (ADR-015). Un lecteur doit pouvoir voir qu'une réponse
   sur le Sénégal a été construite avec des sources sénégalaises — ou qu'elle ne
   l'a pas été.

## Pourquoi une politique, et pas un second récupérateur

Ce module ne cherche rien. Il **ordonne et arbitre** ce qu'un récupérateur
existant a rendu — `retrieve_reliable()` pour le moteur, `search_knowledge()`
pour un agent. Deux chemins de récupération finiraient par ne pas rendre les
mêmes résultats pour la même question, et personne ne saurait lequel a répondu.
"""

from typing import Any, Dict, Iterable, Optional

from .markers import est_senegalais
from .scope import (
    GLOBAL,
    KnowledgeScope,
    KnowledgeSubject,
    parse_subject,
    requires_national_source,
)

#: Portée du pays d'origine de la plateforme. Le module n'est pas limité à lui :
#: `apply_scope_policy(..., scope=…)` prend n'importe quelle portée. Le Sénégal
#: est le défaut de la **détection**, parce que c'est la seule langue de
#: marqueurs que le dépôt porte aujourd'hui.
PORTEE_LOCALE = str(KnowledgeScope.country_("SN"))


def detect_scope(question: str) -> Dict[str, Any]:
    """
    Devine la portée d'une question à partir de ses marqueurs.

    Returns:
        La portée et **la méthode qui l'a produite**. `keywords` n'est pas une
        compréhension : « Quelle est la loi sur le foncier ? » ne porte aucun
        marqueur de pays et sort en `global`, ce qui est exact — c'est le sujet,
        pas la portée devinée, qui interdira le repli mondial.
    """
    senegalais = est_senegalais(question or "")
    return {
        "scope": PORTEE_LOCALE if senegalais else GLOBAL,
        "method": "keywords",
        "detected": senegalais,
    }


def _portee_de(element: Any) -> str:
    """Retourne la portée d'un élément, qu'il soit objet ou dictionnaire."""
    if isinstance(element, dict):
        return str(element.get("scope") or GLOBAL)
    return str(getattr(element, "scope", GLOBAL) or GLOBAL)


def _reference_de(element: Any) -> Optional[str]:
    """Retourne l'identifiant d'un élément, pour que la réponse soit vérifiable."""
    if isinstance(element, dict):
        return element.get("id")
    return getattr(element, "id", None)


def apply_scope_policy(
    items: Iterable[Any],
    question: str = "",
    subject: Any = KnowledgeSubject.UNSPECIFIED,
    scope: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """
    Arbitre et ordonne des éléments déjà récupérés, selon les deux axes.

    Args:
        items: Ce qu'un récupérateur existant a rendu — objets ou dictionnaires.
        question: La question, pour détecter la portée si elle n'est pas donnée.
        subject: Le sujet de la question. C'est lui qui décide de l'interdiction
            de repli, pas la portée détectée.
        scope: Portée voulue ; détectée depuis la question si absente.
        limit: Nombre d'éléments retenus.

    Returns:
        Les éléments retenus, l'ordre appliqué, et le rapport de portée
        (chapitre 05) — y compris quand la réponse est refusée.
    """
    sujet = parse_subject(subject)
    detection = detect_scope(question)
    portee = str(KnowledgeScope.parse(scope)) if scope else detection["scope"]
    national_exige = requires_national_source(sujet)

    elements = list(items)
    locaux = [element for element in elements if _portee_de(element) == portee and portee != GLOBAL]
    mondiaux = [element for element in elements if element not in locaux]

    rapport = {
        "question_scope": portee,
        "scope_method": "declared" if scope else detection["method"],
        "subject": sujet.value,
        "national_subject": national_exige,
        "local_sources": len(locaux),
        "global_sources": len(mondiaux),
        "retrieved": len(elements),
    }

    if national_exige and portee != GLOBAL and not locaux:
        # La seule interdiction du module. Elle ne dépend pas du nombre
        # d'éléments trouvés : cent passages mondiaux ne font pas une source
        # nationale, ils font cent façons de se tromper de pays.
        return {
            "allowed": False,
            "status": "no_national_source",
            "items": [],
            "reason": (
                f"« {sujet.value} » ne se transporte pas d'un pays à l'autre : "
                f"{len(elements)} élément(s) trouvé(s), aucun de portée « {portee} ». "
                "Répondre avec de la connaissance mondiale donnerait une réponse "
                "fluide, plausible et fausse."
            ),
            "what_would_settle_it": [
                f"Ingérer un document déclaré `scope: {portee}` sur ce sujet "
                "(`docs/knowledge/README.md`)",
                "La source doit être nationale : Journal officiel, ministère "
                "compétent, ou administration concernée (`corpus/sources/senegal.yaml`)",
            ],
            "found_but_not_local": [_reference_de(element) for element in elements],
            "scope_report": rapport,
        }

    # Le local d'abord quand la question est locale ; il enrichit, il ne
    # remplace pas — les deux voyagent, dans cet ordre.
    retenus = (locaux + mondiaux)[:limit] if portee != GLOBAL else elements[:limit]
    rapport["answered_with"] = {
        "local": sum(1 for element in retenus if _portee_de(element) == portee and portee != GLOBAL),
        "global": sum(1 for element in retenus if _portee_de(element) != portee or portee == GLOBAL),
    }

    return {
        "allowed": True,
        "status": "scoped" if portee != GLOBAL else "global",
        "items": retenus,
        "reason": (
            f"{len(retenus)} élément(s) retenu(s), les sources de portée "
            f"« {portee} » d'abord." if portee != GLOBAL
            else f"{len(retenus)} élément(s) retenu(s), question de portée mondiale."
        ),
        "scope_report": rapport,
    }


def retrieve_scoped(
    manager: Any,
    question: str,
    subject: Any = KnowledgeSubject.UNSPECIFIED,
    limit: int = 5,
    role: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Récupère par le chemin existant, puis applique la politique de portée.

    `retrieve_reliable()` reste le récupérateur : ce module ne cherche pas, il
    arbitre. Le résultat conserve les champs du récupérateur — `sources`,
    `citation_coverage`, `reliable` — et y ajoute la portée.
    """
    from .health_policy import filter_health_sources, is_health_subject

    brut = manager.retrieve_reliable(question, max_items=max(limit * 3, limit), role=role)
    elements = brut.get("items", [])

    # Le plancher de sources de la santé s'applique **avant** l'arbitrage de
    # portée (VOLET 35, ch. 10) : trier par pays des sources qui n'ont pas le
    # niveau exigé reviendrait à choisir laquelle des mauvaises servir.
    sante = None
    if is_health_subject(subject):
        sante = filter_health_sources(elements)
        elements = sante["items"]

    politique = apply_scope_policy(
        elements, question=question, subject=subject, limit=limit
    )

    resultat = dict(brut)
    if sante is not None:
        resultat["health_policy"] = {
            "applied": True,
            "floor": sante["floor"],
            "dropped": sante["dropped"],
            "reason": sante["reason"],
        }
    resultat.update({
        "items": politique["items"],
        "allowed": politique["allowed"],
        "scope_status": politique["status"],
        "scope_report": politique["scope_report"],
    })
    if not politique["allowed"]:
        # Un refus qui laisserait les citations du récupérateur ferait une
        # réponse vide accompagnée de sources : la pire des deux lectures.
        resultat["sources"] = []
        resultat["reason"] = politique["reason"]
        resultat["what_would_settle_it"] = politique["what_would_settle_it"]
    return resultat


def scope_notice(scope_report: Dict[str, Any]) -> str:
    """
    Rend la phrase qu'une réponse doit porter sur sa propre portée (ch. 05).

    C'est l'équivalent, pour la portée, de ce que l'ADR-015 impose déjà à la
    méthode de récupération : une réponse sur le Sénégal construite sans aucune
    source sénégalaise doit le **dire**, pas le laisser deviner.
    """
    portee = scope_report.get("question_scope", GLOBAL)
    repondu = scope_report.get("answered_with") or {}
    locaux = repondu.get("local", 0)
    mondiaux = repondu.get("global", 0)

    if portee == GLOBAL:
        return f"Réponse de portée mondiale, construite à partir de {mondiaux} source(s)."
    if locaux and mondiaux:
        return (
            f"Réponse construite à partir de {locaux} source(s) de portée « {portee} » "
            f"et de {mondiaux} source(s) mondiale(s), les locales d'abord."
        )
    if locaux:
        return f"Réponse construite uniquement à partir de {locaux} source(s) « {portee} »."
    return (
        f"Question de portée « {portee} », mais **aucune source de cette portée** : "
        f"la réponse repose sur {mondiaux} source(s) mondiale(s)."
    )
