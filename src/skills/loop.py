"""
La boucle qui fait vivre la bibliothèque : retrouver avant, ranger après.

## Ce qui manquait

`src/skills/library.py` existe depuis le 2026-08-23 et **rien n'y écrivait**.
Une bibliothèque que personne n'alimente et que personne ne consulte n'est pas
une bibliothèque : c'est une structure de données avec des tests.

Son en-tête annonçait pourtant la règle qui la distingue d'Odyssey :

> Odyssey range ce que l'agent a écrit. Ici on range **ce qui a marché**.

Ce module est ce que cette phrase impliquait et qui n'existait pas.

## Les deux moitiés, et pourquoi elles sont chez deux agents différents

- **Retrouver** — chez le `coder`, *avant* de générer. Une procédure qui a déjà
  servi entre dans l'invite comme antériorité, jamais comme réponse toute
  faite : réutiliser sans relire est la façon la plus rapide de propager une
  erreur.
- **Ranger** — chez le `tester`, *après* que les suites ont tourné. C'est le
  seul endroit du dépôt où existe une **preuve**. Ranger côté `coder` reviendrait
  à archiver tout ce qu'un modèle produit, y compris ce qui ne compile pas —
  précisément le tas que `library.py` refuse d'être.

Cette séparation n'est pas de l'élégance : `Competence.valider()` lève déjà
`CompetenceRefusee` sur une compétence qui se dit vérifiée sans preuve. Le seul
agent capable de fournir cette preuve est celui qui exécute.
"""

import logging
import re
from typing import Any, Dict, List, Optional

from .library import BibliothequeCompetences, Competence, CompetenceRefusee

logger = logging.getLogger(__name__)

#: Combien d'antériorités entrent dans une invite. Trois : assez pour couvrir
#: des formulations voisines, assez peu pour que l'invite reste lisible et que
#: le modèle ne se contente pas de recopier.
ANTERIORITES_MAX = 3

#: Longueur minimale d'un contenu rangé. En dessous, ce n'est pas une procédure
#: réutilisable — c'est un fragment, et le retrouver ferait perdre du temps.
CONTENU_MINIMAL = 40


def _nom_de(demande: str) -> str:
    """
    Fabrique un nom stable à partir de la demande.

    Stable est le mot qui compte : deux formulations de la même demande doivent
    tomber sur le même nom, sinon `ajouter()` crée une entrée de plus au lieu de
    remplacer, et la bibliothèque grossit sans rien apprendre.

    Args:
        demande: Le texte de la demande.

    Returns:
        Un identifiant en minuscules, mots significatifs joints par `_`.
    """
    mots = [m for m in re.findall(r"[a-zà-ÿ0-9]+", (demande or "").lower()) if len(m) > 2]
    return "_".join(mots[:6]) or "competence_sans_nom"


def antecedents(
    demande: str,
    bibliotheque: Optional[BibliothequeCompetences] = None,
    limite: int = ANTERIORITES_MAX,
) -> Dict[str, Any]:
    """
    Cherche ce qui a déjà servi pour une demande voisine.

    Args:
        demande: La demande courante.
        bibliotheque: La bibliothèque à consulter ; celle du répertoire de
            données par défaut.
        limite: Nombre maximal d'antériorités rendues.

    Returns:
        `{"skills": [...], "method": ..., "reason": ...}`. `method` dit **par
        quel chemin** le classement a été obtenu — `semantic`, `lexical` ou
        `empty`. Un appelant qui l'ignore présentera un classement par mots
        comme une compréhension du sens, ce que cette plateforme refuse
        ailleurs. La liste est vide quand rien ne correspond, et ce n'est pas
        une panne.
    """
    try:
        depot = bibliotheque or BibliothequeCompetences()
        trouvees, info = depot.retrouver(demande, limite=limite, verifiees_seulement=True)
    except Exception as erreur:  # noqa: BLE001 — la bibliothèque ne bloque jamais le travail
        logger.warning("Bibliothèque de compétences illisible : %s", erreur)
        return {"skills": [], "method": "unavailable", "reason": str(erreur)}

    return {
        "skills": [
            {
                "name": c.nom,
                "description": c.description,
                "content": c.contenu,
                "origin": c.origine,
                "proof": c.preuve,
                "reuses": c.reutilisations,
            }
            for c in trouvees
        ],
        "method": info.get("method"),
        "reason": info.get("reason"),
    }


def rendre_anterioroites(antecedents_trouves: Dict[str, Any]) -> str:
    """
    Met les antériorités en forme pour une invite.

    Le bloc dit explicitement au modèle de **relire** avant de réutiliser. Sans
    cette phrase, une procédure rangée devient une réponse toute faite, et la
    bibliothèque se met à propager ses propres erreurs.

    Args:
        antecedents_trouves: Ce que rend `antecedents()`.

    Returns:
        Un bloc en anglais — comme toute invite système
        (`.claude/rules/prompts.md`) — ou une chaîne vide s'il n'y a rien.
    """
    competences = antecedents_trouves.get("skills") or []
    if not competences:
        return ""

    blocs = []
    for competence in competences:
        blocs.append(
            f"### {competence['name']}\n"
            f"{competence['description']}\n"
            f"(verified by: {competence['proof']}; reused {competence['reuses']} time(s))\n"
            f"```\n{competence['content']}\n```"
        )
    return (
        "## Procedures that already worked here\n\n"
        "These come from earlier work on this repository and passed its test "
        "suites. Read them before writing: reuse what applies, adapt what nearly "
        "applies, and ignore what does not. Do not copy one because it is here.\n\n"
        + "\n\n".join(blocs)
    )


def ranger_si_prouve(
    demande: str,
    contenu: str,
    preuve: str,
    origine: str,
    description: str = "",
    bibliotheque: Optional[BibliothequeCompetences] = None,
) -> Optional[Competence]:
    """
    Range une procédure **dont le fonctionnement a été constaté**.

    Args:
        demande: La demande qui l'a produite ; sert de nom et de description.
        contenu: La procédure elle-même.
        preuve: Ce qui l'a prouvée — un identifiant d'exécution, un résultat de
            suite. **Sans elle, rien n'est rangé** : une compétence qui se dit
            vérifiée sans dire par quoi est une affirmation, et
            `Competence.valider()` la refuse.
        origine: Qui l'a produite.
        description: Description explicite ; la demande sert sinon.
        bibliotheque: Où ranger ; celle du répertoire de données par défaut.

    Returns:
        La compétence rangée, ou `None` quand rien ne devait l'être — contenu
        trop court, preuve absente, bibliothèque indisponible. `None` n'est
        jamais une erreur ici : ne pas ranger est le comportement attendu dans
        la majorité des cas.
    """
    if not preuve or not preuve.strip():
        return None
    if len((contenu or "").strip()) < CONTENU_MINIMAL:
        return None

    competence = Competence(
        nom=_nom_de(demande),
        description=(description or demande or "").strip()[:300] or "Procédure sans description",
        contenu=contenu,
        origine=origine,
        verifiee=True,
        preuve=preuve,
    )
    try:
        depot = bibliotheque or BibliothequeCompetences()
        return depot.ajouter(competence)
    except (CompetenceRefusee, OSError) as erreur:
        # Un rangement raté ne compromet jamais le travail qui l'a produit.
        logger.warning("Compétence « %s » non rangée : %s", competence.nom, erreur)
        return None


def ranger_depuis_le_tester(
    resultat_coder: Optional[Dict[str, Any]],
    verdict: Dict[str, Any],
    demande: str,
    bibliotheque: Optional[BibliothequeCompetences] = None,
) -> Optional[Competence]:
    """
    Range ce que le `coder` a produit, si et seulement si les suites sont vertes.

    Trois refus, dans cet ordre, et chacun compte :

    1. **Pas de code généré** — il n'y a rien à ranger.
    2. **Verdict négatif** — c'est précisément ce que la bibliothèque ne doit
       pas contenir. Ranger un échec le ferait ressortir comme antériorité.
    3. **Aucune suite exécutée** — un verdict `passed` sans exécution n'est pas
       une preuve. Le `tester` rend `passed: True` quand il s'exclut lui-même
       par ré-entrance : accepter ce cas rangerait du code que personne n'a
       éprouvé, sous une preuve qui n'a pas eu lieu.

    Args:
        resultat_coder: Le résultat de l'agent `coder`, ou `None`.
        verdict: Le verdict du `tester`, avec `passed` et `reason`.
        demande: La demande d'origine.
        bibliotheque: Où ranger.

    Returns:
        La compétence rangée, ou `None`.
    """
    if not isinstance(resultat_coder, dict):
        return None
    implementation = resultat_coder.get("implementation")
    if not isinstance(implementation, dict) or implementation.get("status") != "generated":
        return None
    if not verdict.get("passed"):
        return None

    suites = verdict.get("suites_executed")
    if not suites:
        return None

    return ranger_si_prouve(
        demande=demande or resultat_coder.get("request", ""),
        contenu=str(implementation.get("code") or ""),
        preuve=f"tester: {suites} suite(s) vertes — {verdict.get('reason', 'sans motif')}",
        origine="agent:coder",
        bibliotheque=bibliotheque,
    )


def resume(bibliotheque: Optional[BibliothequeCompetences] = None) -> Dict[str, Any]:
    """
    Ce que la bibliothèque contient, pour l'observabilité.

    Args:
        bibliotheque: La bibliothèque à décrire.

    Returns:
        Son état, ou le motif pour lequel il n'a pas pu être lu.
    """
    try:
        return (bibliotheque or BibliothequeCompetences()).etat()
    except Exception as erreur:  # noqa: BLE001
        return {"unavailable": str(erreur)}


def noms_ranges(bibliotheque: Optional[BibliothequeCompetences] = None) -> List[str]:
    """Retourne les noms rangés, pour un diagnostic rapide."""
    try:
        depot = bibliotheque or BibliothequeCompetences()
        return sorted(depot._competences)
    except Exception:  # noqa: BLE001
        return []
