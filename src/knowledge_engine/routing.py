"""
Which engine answers, and why it was that one.

By the end of wave IV this repository holds two bodies of knowledge that can
both be asked about Senegal, and they are not the same kind of thing:

- the **world reference** (VOLET 52): 249 countries, one record each — codes,
  capital, currency, region, plus population and GDP series. Breadth.
- the **Senegalese layer** (`src/services/senegal/`): 14 regions, 45
  departments, 271 chunks with provenance, a 2105-sentence Wolof corpus.
  Depth, for one country.

Two engines that can answer the same question is not a feature; it is the
failure this module exists to prevent. Not because either would be wrong, but
because *nobody would know which one answered*, and the day they disagree the
disagreement would be invisible.

So the routing is **declared**, not incidental, and it follows three rules.

**A national subject never leaves its country.** Law, administration, languages:
the world reference is not a fallback for them, it is off-topic. A question about
Senegalese law that reached a global source would be answered by the wrong
authority in a way that reads perfectly.

**Where both can answer, depth goes first and breadth completes it.** The
Senegalese layer knows the department of Podor; the world reference knows the
currency of the country. Neither answer is a better version of the other, and
merging them silently would lose which is which.

**The answer says which layer spoke.** Every result carries `answered_by` and
the reason that layer was chosen. A router whose decision cannot be read is a
router nobody can debug when it picks wrong.

Nothing here guesses a country from prose beyond the markers the repository
already declares (`markers.py`), and those report their method — `keywords`,
never `understanding`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .markers import est_senegalais, sujets_reperes
from .scope import (
    NATIONAL_SUBJECTS,
    KnowledgeScope,
    KnowledgeSubject,
    parse_subject,
)

#: Le pays pour lequel ce dépôt a une couche de profondeur. Un seul : le dire
#: évite de laisser croire que la même profondeur existe ailleurs.
PAYS_SPECIALISE = "country:sn"

#: Les couches disponibles, et ce que chacune est.
COUCHE_SENEGAL = "senegal"
COUCHE_MONDE = "world"
AUCUNE = "none"


def _sujet_de(question: str, subject: Optional[str]) -> Dict[str, Any]:
    """
    Le sujet d'une question : déclaré s'il l'est, repéré sinon.

    Un sujet **déclaré** par l'appelant l'emporte toujours : les marqueurs
    repèrent des mots, ils ne comprennent rien, et le dire est la moitié de leur
    utilité.
    """
    if subject:
        return {"subject": parse_subject(subject).value, "method": "declared"}

    repere = sujets_reperes(question)
    if not repere:
        return {"subject": KnowledgeSubject.UNSPECIFIED.value, "method": "none"}
    return {"subject": repere[0], "method": "keywords", "also_seen": repere[1:]}


def route(
    question: str,
    scope: Optional[str] = None,
    subject: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Décide quelle couche répond, et dit pourquoi.

    Ne consulte aucune connaissance : c'est une **décision**, pas une
    recherche. La séparer de l'exécution est ce qui la rend lisible et
    testable — un routeur dont on ne peut pas lire la décision est un routeur
    que personne ne peut déboguer le jour où il se trompe.

    Args:
        question: La question posée.
        scope: La portée demandée. Déduite des marqueurs si elle est absente.
        subject: Le sujet, s'il est déclaré.

    Returns:
        Les couches à interroger dans l'ordre, et la raison de chaque choix.
    """
    trouve = _sujet_de(question, subject)
    sujet = parse_subject(trouve["subject"])

    if scope:
        portee = str(KnowledgeScope.parse(scope))
        methode_portee = "declared"
    elif est_senegalais(question):
        portee, methode_portee = PAYS_SPECIALISE, "keywords"
    else:
        portee, methode_portee = "global", "default"

    national = sujet in NATIONAL_SUBJECTS
    specialise = portee == PAYS_SPECIALISE

    if national and specialise:
        couches, raison = [COUCHE_SENEGAL], (
            f"Sujet national ({sujet.value}) sur le pays spécialisé : la "
            "référence mondiale n'est pas un repli, elle est hors sujet. Un "
            "droit étranger répondrait à côté d'une façon qui se lit "
            "parfaitement."
        )
    elif national:
        couches, raison = [], (
            f"Sujet national ({sujet.value}) hors du pays spécialisé : ce "
            f"dépôt n'a de profondeur que pour {PAYS_SPECIALISE}, et aucune "
            "source mondiale ne porte le droit d'un pays."
        )
    elif specialise:
        couches, raison = [COUCHE_SENEGAL, COUCHE_MONDE], (
            "Pays spécialisé : la profondeur répond d'abord, la référence "
            "mondiale complète. Ni l'une ni l'autre n'est une meilleure "
            "version de l'autre."
        )
    else:
        couches, raison = [COUCHE_MONDE], (
            "Hors du pays spécialisé : seule la référence mondiale porte "
            "quelque chose. La couche sénégalaise ne répond pas d'un autre "
            "pays."
        )

    return {
        "question": question,
        "scope": portee,
        "scope_method": methode_portee,
        "subject": sujet.value,
        "subject_method": trouve["method"],
        "layers": couches,
        "reason": raison,
        "national_subject": national,
    }


def ask(
    question: str,
    scope: Optional[str] = None,
    subject: Optional[str] = None,
    senegal_answer: Optional[Any] = None,
    world_answer: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Pose la question à la couche qui doit répondre, et dit laquelle a parlé.

    Les deux couches sont **injectées** : ce module décide, il n'importe ni le
    RAG sénégalais ni la connaissance mondiale. C'est ce qui permet de tester la
    décision sans charger 700 ko de séries, et d'éviter qu'un routeur devienne
    le point par lequel tout le dépôt se charge.

    Args:
        question: La question.
        scope: La portée demandée.
        subject: Le sujet déclaré.
        senegal_answer: Appelable `(question) -> dict`, la couche de
            profondeur. Chargée à la demande si elle n'est pas fournie.
        world_answer: Appelable `(question) -> dict`, la référence mondiale.

    Returns:
        La décision, la réponse retenue, et **qui** l'a donnée.
    """
    decision = route(question, scope, subject)
    tentatives: List[Dict[str, Any]] = []

    for couche in decision["layers"]:
        reponse = _interroger(couche, question, senegal_answer, world_answer)
        tentatives.append({"layer": couche, "status": reponse.get("status", "UNKNOWN")})
        if reponse.get("status") == "FOUND":
            return {
                **decision,
                "answered_by": couche,
                "status": "FOUND",
                "answer": reponse["answer"],
                "attempted": tentatives,
            }

    return {
        **decision,
        "answered_by": AUCUNE,
        "status": "UNKNOWN",
        "answer": None,
        "attempted": tentatives,
        # Dire quelles couches ont été interrogées distingue « personne ne
        # sait » de « personne n'a été interrogé ».
        "note": (
            "Aucune couche interrogée n'a de réponse. Les couches consultées "
            "sont listées : « personne ne sait » et « personne n'a été "
            "interrogé » ne sont pas la même chose."
        ),
    }


def _interroger(
    couche: str, question: str,
    senegal_answer: Optional[Any], world_answer: Optional[Any],
) -> Dict[str, Any]:
    """
    Interroge une couche et normalise sa réponse.

    Chaque couche a sa forme propre — la sénégalaise rend `answer` et
    `grounding`, la mondiale rend `status`. Les traduire ici évite que
    l'appelant apprenne deux formes, et évite surtout qu'un `UNKNOWN` de l'une
    se lise comme un succès de l'autre.
    """
    try:
        if couche == COUCHE_SENEGAL:
            appel = senegal_answer or _senegal_par_defaut
            brute = appel(question)
            trouve = str(brute.get("answer") or "").strip() not in ("", "UNKNOWN")
            return {"status": "FOUND" if trouve else "UNKNOWN", "answer": brute}

        appel = world_answer or _monde_par_defaut
        brute = appel(question)
        return {"status": brute.get("status", "UNKNOWN"), "answer": brute}
    except Exception as erreur:  # pragma: no cover - dépend d'une couche absente
        return {"status": "UNKNOWN", "answer": {"error": str(erreur)}}


def _senegal_par_defaut(question: str) -> Dict[str, Any]:
    """La couche de profondeur réelle, chargée à la demande."""
    from src.services.senegal.master_rag import answer_question

    return answer_question(question)


def _monde_par_defaut(question: str) -> Dict[str, Any]:
    """La référence mondiale réelle, chargée à la demande."""
    from .world import answer_country

    return answer_country(question)


def routing_report() -> Dict[str, Any]:
    """
    Ce que le routage garantit, et ce qu'il ne fait pas.

    Returns:
        Les couches, les règles tenues et les limites assumées.
    """
    return {
        "layers": {
            COUCHE_SENEGAL: (
                "Profondeur pour un seul pays : régions, départements, "
                "fragments avec provenance, corpus wolof."
            ),
            COUCHE_MONDE: (
                "Largeur : 249 pays, une fiche chacun, plus les séries "
                "mesurées."
            ),
        },
        "specialised_country": PAYS_SPECIALISE,
        "rules": [
            "Un sujet national ne quitte pas son pays : pour le droit, "
            "l'administration et les langues, la référence mondiale n'est pas "
            "un repli, elle est hors sujet.",
            "Là où les deux peuvent répondre, la profondeur passe d'abord et "
            "la largeur complète. Aucune n'est une meilleure version de "
            "l'autre.",
            "La réponse dit **quelle couche** a parlé et pourquoi : un routeur "
            "dont la décision ne se lit pas est un routeur que personne ne "
            "peut déboguer.",
            "Décider et exécuter sont séparés : `route()` ne consulte aucune "
            "connaissance.",
        ],
        "does_not": [
            "Fusionner deux réponses : cela perdrait laquelle vient d'où.",
            "Répondre du droit d'un pays sans couche nationale pour lui.",
            "Comprendre la question : les marqueurs repèrent des mots et le "
            "disent (`keywords`).",
        ],
    }


def layer_comparison() -> Dict[str, Any]:
    """
    Ce que chaque couche porte réellement, mesuré.

    Le but n'est pas de les classer : c'est de montrer qu'elles ne se
    recouvrent pas. Si l'une était un sous-ensemble de l'autre, la garder serait
    une implémentation parallèle — exactement ce que la directive interdit. Les
    chiffres disent le contraire, et un lecteur doit pouvoir le vérifier sans
    lire le code.

    Returns:
        Les mesures de chaque couche et ce que l'autre ne peut pas offrir.
    """
    from .world import load_world

    monde = load_world()
    pays = monde.get("countries") or []

    try:
        from src.services.senegal.master_rag import knowledge_report

        senegal = knowledge_report()
    except Exception as erreur:  # pragma: no cover - dépend d'un fichier absent
        senegal = {"available": False, "reason": str(erreur)}

    return {
        COUCHE_MONDE: {
            "countries": len(pays),
            "fields_per_country": len(pays[0]) if pays else 0,
            "offers": (
                "Une fiche par pays : codes, capitale, monnaie, région, plus "
                "les séries mesurées."
            ),
            "cannot_offer": (
                "Aucun détail sous le pays : pas une région, pas un "
                "département, pas une phrase de langue."
            ),
        },
        COUCHE_SENEGAL: {
            "available": senegal.get("available", False),
            "regions": senegal.get("regions", 0),
            "departments": senegal.get("departments", 0),
            "offers": (
                "La profondeur sous le pays, avec provenance : régions, "
                "départements, fragments sectoriels, corpus wolof."
            ),
            "cannot_offer": "Tout autre pays que le Sénégal.",
        },
        "overlap": (
            "Aucune des deux n'est un sous-ensemble de l'autre. Si elle "
            "l'était, la garder serait une implémentation parallèle — ce que la "
            "directive interdit."
        ),
    }
