"""
Data Engineering Agent for GalSen IA (VOLET 36, ch. G).

A statistical series is not a document. `DocumentIngestor` cuts prose into
passages and cites them; applied to a CSV it would produce blocks of numbers
with no unit and no period — that is, numbers that mean nothing and can still be
quoted.

## The refusal comes before the happy path

**A series without declared units, period and source is refused.** An ANSD
figure without its year is a wrong figure waiting to be cited: "the population
is 18 million" is true, false, or meaningless depending on a year nobody wrote
down. The same holds for units — 2 500 of what, per what.

The declaration is *not* inferred from the file. A column called `montant` does
not say whether it is FCFA, thousands of FCFA, or dollars, and a guess here
would be indistinguishable from a fact for every later reader.

## What it produces

A described series: columns with an **inferred** type — inferred, and reported
as such — the row count, the declared units, period and source. Nothing is
stored: like `knowledge_architect`, this agent proposes and a person confirms.
"""

import csv
import os
import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.markers import est_senegalais

#: Déclarations exigées avant toute lecture. Elles ne se déduisent pas du
#: fichier : un nom de colonne ne porte ni unité, ni période, ni provenance.
DECLARATIONS_EXIGEES = ("units", "period", "source")

#: Lignes lues pour deviner le type d'une colonne. Assez pour distinguer un
#: nombre d'un texte, assez peu pour ne pas charger une série entière en
#: mémoire pour une description.
LIGNES_ECHANTILLONNEES = 50

#: Une date reconnue à sa forme : `2023-05-01`, `2023/05`, `01/05/2023`. Un
#: nombre à quatre chiffres seul n'en est pas une — c'est peut-être un compte.
_DATE = re.compile(r"^\d{2,4}[-/]\d{1,2}([-/]\d{1,4})?$")

#: Un nombre, éventuellement signé et décimal.
_NOMBRE = re.compile(r"^-?\d+(\.\d+)?$")

#: Ce que l'agent ne déduira jamais du fichier lui-même.
NON_DEDUIT = (
    "l'unité : « montant » ne dit pas si ce sont des FCFA, des milliers ou des dollars",
    "la période : une colonne « valeur » ne porte pas son année",
    "la source : un fichier posé sur un disque n'a pas de provenance",
)


class DataEngineeringAgent(BaseAgent):
    """Agent qui décrit une série structurée, et refuse celle qui ne se déclare pas."""

    agent_id = "data_engineer"
    required_engines = ()

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Décrit une série statistique, ou refuse de la traiter.

        Args:
            context: Contexte d'exécution. `options` porte `path`, `units`,
                `period` et `source`.

        Returns:
            Le schéma décrit, ou le refus avec ce qui manque.
        """
        options = context.options
        chemin = str(options.get("path") or "").strip()
        manquantes = [
            champ for champ in DECLARATIONS_EXIGEES
            if not str(options.get(champ) or "").strip()
        ]

        # Le refus vient avant la lecture : décrire un fichier qu'on refusera
        # ensuite ferait croire que la déclaration est un détail administratif.
        if manquantes:
            return {
                "status": "undeclared_series",
                "missing": manquantes,
                "reason": (
                    "Une série sans " + ", ".join(manquantes) + " ne peut pas être "
                    "citée : un chiffre sans son unité ni son année est un chiffre "
                    "faux en attente d'être repris."
                ),
                "not_inferred": list(NON_DEDUIT),
                "schema": None,
            }

        if not chemin or not os.path.isfile(chemin):
            return {
                "status": "file_not_found",
                "reason": f"Fichier introuvable : {chemin or '(aucun chemin)'}",
                "schema": None,
            }

        try:
            colonnes, lignes = self._lire(chemin)
        except (OSError, csv.Error) as erreur:
            return {
                "status": "unreadable",
                "reason": f"Lecture impossible : {erreur}",
                "schema": None,
            }

        if not colonnes:
            return {
                "status": "empty_series",
                "reason": "Le fichier ne porte aucune colonne : il n'y a rien à décrire.",
                "schema": None,
            }

        return {
            "status": "described",
            "path": chemin,
            "schema": {
                "columns": [
                    {"name": nom, "type": self._type(valeurs), "type_method": "inferred"}
                    for nom, valeurs in colonnes.items()
                ],
                "rows_sampled": lignes,
            },
            "declared": {champ: str(options.get(champ)).strip() for champ in DECLARATIONS_EXIGEES},
            "scope": "country:sn" if est_senegalais(
                chemin + " " + str(options.get("source", ""))
            ) else "global",
            "requires_human_confirmation": True,
            "not_inferred": list(NON_DEDUIT),
            "note": (
                "Série décrite, rien n'a été enregistré. Le type des colonnes est "
                "**déduit** d'un échantillon, pas déclaré."
            ),
        }

    @staticmethod
    def _lire(chemin: str) -> tuple:
        """Lit l'en-tête et un échantillon de lignes."""
        colonnes: Dict[str, List[str]] = {}
        lues = 0
        with open(chemin, "r", encoding="utf-8", errors="replace", newline="") as fichier:
            lecteur = csv.DictReader(fichier)
            for nom in lecteur.fieldnames or []:
                colonnes[nom] = []
            for ligne in lecteur:
                for nom in colonnes:
                    colonnes[nom].append((ligne.get(nom) or "").strip())
                lues += 1
                if lues >= LIGNES_ECHANTILLONNEES:
                    break
        return colonnes, lues

    @staticmethod
    def _type(valeurs: List[str]) -> str:
        """
        Devine le type d'une colonne à partir de ses valeurs.

        `unknown` quand la colonne est vide : une colonne sans valeur n'est pas
        du texte, elle est sans information — et la dire « texte » ferait un
        schéma faux qui aurait l'air complet.

        Une colonne de nombres à quatre chiffres est **ambiguë** entre une année
        et un compte : `2022` est les deux. Elle est rendue `number`, et c'est la
        déclaration `period` qui porte l'année — c'est exactement pourquoi cet
        agent l'exige au lieu de la deviner. Une valeur n'est dite `date` que si
        elle en a la forme, séparateur compris.
        """
        remplies = [valeur for valeur in valeurs if valeur]
        if not remplies:
            return "unknown"
        if all(_DATE.match(valeur) for valeur in remplies):
            return "date"
        if all(_NOMBRE.match(valeur.replace(" ", "").replace(",", ".")) for valeur in remplies):
            return "number"
        return "text"


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Demande portant sur une série structurée.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(DataEngineeringAgent, input_data)
