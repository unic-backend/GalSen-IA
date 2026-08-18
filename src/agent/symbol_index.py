"""
Où un nom est défini, et qui s'en sert (VOLET 34, ch. 10, phase 2).

`.claude/rules/verification.md` pose une obligation avant toute modification :

> Check who calls it (`Grep`) before changing a signature, a return type or a
> public name. A change that compiles but breaks three callers is a regression,
> not a refactor.

Cette règle dépend aujourd'hui de la mémoire de celui qui modifie, et d'un
`grep` qu'il pense à lancer. Ce module en fait une requête.

## Ce que `repo_map.py` ne donnait pas

Mesuré : la carte n'indexe que les symboles de **premier niveau**. Pour
`src/agent/repo_map.py`, elle rend `FileEntry` et `RepoMap` — et aucune des
onze méthodes. Or un agent qui doit changer `tests_for()` cherche `tests_for`,
pas `RepoMap`.

L'index descend donc dans les classes, sous le nom qualifié `RepoMap.tests_for`,
et garde la ligne : un symbole sans son emplacement oblige à relire le fichier
pour le trouver, ce qui annule le bénéfice de l'index.

## Ce qu'il ne prétend pas être

Ce n'est **pas** une analyse de types. `resultat.close()` compte comme un usage
de tout `close` du dépôt, parce que rien ici ne sait ce qu'est `resultat`. La
conséquence est écrite plutôt que masquée : les usages sont un **sur-ensemble**
sûr — on n'en manque pas, on en propose parfois trop. L'inverse serait
dangereux : rater un appelant est exactement ce que la règle cherche à empêcher.
"""

import ast
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from .repo_graph import PAQUETS, TESTS, RepoGraph

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Symbol:
    """
    Un symbole défini quelque part dans le dépôt.

    Attributes:
        name: Nom simple — `tests_for`.
        qualified: Nom qualifié — `RepoMap.tests_for`.
        kind: `class`, `function` ou `method`.
        path: Fichier qui le définit.
        line: Ligne de la définition.
        signature: Paramètres déclarés, pour comparer avant de changer.
    """

    name: str
    qualified: str
    kind: str
    path: str
    line: int
    signature: str = ""

    def location(self) -> str:
        """Retourne l'emplacement cliquable : `src/agent/repo_map.py:207`."""
        return f"{self.path}:{self.line}"

    def to_dict(self) -> Dict[str, object]:
        """Sérialise le symbole."""
        return {
            "name": self.name, "qualified": self.qualified, "kind": self.kind,
            "path": self.path, "line": self.line, "signature": self.signature,
        }


class SymbolIndex:
    """
    L'index des définitions et des usages du dépôt.

    Exemple:
        index = SymbolIndex().build()
        index.definitions("tests_for")        # où c'est défini
        index.callers("tests_for")            # qui s'en sert
        index.rename_impact("tests_for")      # ce qu'un renommage touche
    """

    def __init__(
        self,
        root: Optional[str] = None,
        packages: Tuple[str, ...] = PAQUETS,
        tests_dir: str = TESTS,
        graph: Optional[RepoGraph] = None,
    ) -> None:
        """
        Args:
            root: Racine du dépôt.
            packages: Répertoires de code parcourus.
            tests_dir: Répertoire des tests.
            graph: Graphe d'imports réutilisé ; construit sinon. Les deux
                parcourent les mêmes fichiers — les relire deux fois n'apporte
                rien.
        """
        self._graphe = graph or RepoGraph(root=root, packages=packages, tests_dir=tests_dir)
        self.root = self._graphe.root
        self._tests_dir = tests_dir
        self._definitions: Dict[str, List[Symbol]] = {}
        self._par_fichier: Dict[str, List[Symbol]] = {}
        self._usages: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self) -> "SymbolIndex":
        """Construit l'index : définitions d'abord, usages ensuite."""
        self._definitions.clear()
        self._par_fichier.clear()
        self._usages.clear()

        if not self._graphe.files():
            self._graphe.build()

        for chemin in self._graphe.files():
            arbre = self._analyser(chemin)
            if arbre is None:
                continue
            symboles = self._definitions_de(arbre, chemin)
            self._par_fichier[chemin] = symboles
            for symbole in symboles:
                self._definitions.setdefault(symbole.name, []).append(symbole)
            for nom in self._noms_utilises(arbre):
                self._usages.setdefault(nom, set()).add(chemin)

        logger.debug(
            "Index des symboles : %d nom(s) défini(s) dans %d fichier(s).",
            len(self._definitions), len(self._par_fichier),
        )
        return self

    def _analyser(self, chemin_relatif: str) -> Optional[ast.AST]:
        """Analyse un fichier, ou l'écarte en le disant."""
        absolu = os.path.join(self.root, chemin_relatif)
        try:
            with open(absolu, "r", encoding="utf-8") as fichier:
                return ast.parse(fichier.read())
        except (OSError, UnicodeDecodeError, SyntaxError) as erreur:
            logger.debug("Fichier hors index (%s) : %s", chemin_relatif, erreur)
            return None

    def _definitions_de(self, arbre: ast.AST, chemin: str) -> List[Symbol]:
        """Recense les classes, fonctions et **méthodes** d'un fichier."""
        symboles: List[Symbol] = []

        def descendre(corps: List[ast.stmt], prefixe: str) -> None:
            """Descend dans un corps, en portant le nom qualifié du parent."""
            for noeud in corps:
                if isinstance(noeud, ast.ClassDef):
                    qualifie = f"{prefixe}{noeud.name}"
                    symboles.append(Symbol(
                        name=noeud.name, qualified=qualifie, kind="class",
                        path=chemin, line=noeud.lineno,
                    ))
                    descendre(noeud.body, f"{qualifie}.")
                elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualifie = f"{prefixe}{noeud.name}"
                    symboles.append(Symbol(
                        name=noeud.name, qualified=qualifie,
                        kind="method" if prefixe else "function",
                        path=chemin, line=noeud.lineno,
                        signature=_signature(noeud),
                    ))

        descendre(getattr(arbre, "body", []), "")
        return symboles

    @staticmethod
    def _noms_utilises(arbre: ast.AST) -> Set[str]:
        """
        Recense les noms **lus** dans un fichier : variables et attributs.

        Les attributs comptent (`carte.tests_for(...)` est un usage de
        `tests_for`), et c'est ce qui rend les usages sur-inclusifs plutôt que
        lacunaires — le compromis assumé dans l'en-tête de ce module.
        """
        noms: Set[str] = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Name):
                noms.add(noeud.id)
            elif isinstance(noeud, ast.Attribute):
                noms.add(noeud.attr)
        return noms

    # ------------------------------------------------------------------
    # Consultation
    # ------------------------------------------------------------------

    def definitions(self, nom: str) -> List[Symbol]:
        """
        Retourne les endroits où un nom est défini.

        Un nom peut l'être plusieurs fois — `run` existe dans plusieurs modules.
        Rendre la liste entière est plus honnête que d'en choisir un.
        """
        if "." in nom:
            return [
                symbole for symboles in self._definitions.values()
                for symbole in symboles if symbole.qualified == nom
            ]
        return list(self._definitions.get(nom, []))

    def symbols_in(self, chemin_relatif: str) -> List[Symbol]:
        """Retourne les symboles définis par un fichier, méthodes comprises."""
        return list(self._par_fichier.get(chemin_relatif, []))

    def callers(self, nom: str, exclude_definition: bool = True) -> List[str]:
        """
        Retourne les fichiers qui utilisent un nom.

        Args:
            nom: Nom simple ou qualifié ; seul le dernier segment est cherché,
                puisque l'usage s'écrit `objet.methode`.
            exclude_definition: Écarter les fichiers qui ne font que le définir.
        """
        simple = nom.rsplit(".", 1)[-1]
        fichiers = set(self._usages.get(simple, set()))
        if exclude_definition:
            definis = {symbole.path for symbole in self._definitions.get(simple, [])}
            # Un fichier qui définit **et** utilise le nom reste un appelant :
            # seuls ceux qui n'ont aucun usage hors définition sortent.
            fichiers -= {chemin for chemin in definis if chemin not in fichiers}
        return sorted(fichiers)

    def rename_impact(self, nom: str) -> Dict[str, object]:
        """
        Décrit ce qu'un renommage — ou un changement de signature — touche.

        C'est la règle de `verification.md` rendue exécutable : les définitions,
        les fichiers à relire, et **les tests à relancer**, qui viennent du
        graphe d'imports plutôt que d'une convention de nom.
        """
        definitions = self.definitions(nom)
        appelants = self.callers(nom)
        tests: Set[str] = set()
        for symbole in definitions:
            tests.update(self._graphe.tests_to_run(symbole.path))
        prefixe = f"{self._tests_dir}/"
        tests.update(chemin for chemin in appelants if chemin.startswith(prefixe))

        return {
            "name": nom,
            "defined_in": [symbole.location() for symbole in definitions],
            "ambiguous": len(definitions) > 1,
            "callers": appelants,
            "caller_count": len(appelants),
            "tests_to_run": sorted(tests),
            # Un symbole sans définition connue n'est pas un symbole sans
            # appelant : il vient peut-être d'une dépendance. Le dire évite de
            # conclure « rien à faire » sur une recherche qui a simplement
            # cherché au mauvais endroit.
            "known": bool(definitions),
        }

    def unused(self, path_prefix: str = "src/") -> List[Symbol]:
        """
        Retourne les symboles publics qu'aucun autre fichier n'utilise.

        **À lire comme une piste, jamais comme une preuve** : un point d'entrée
        d'API, un rappel enregistré par configuration ou une classe chargée par
        son nom n'ont aucun appelant visible et sont pourtant vivants. Supprimer
        sur la seule foi de cette liste casserait la plateforme.
        """
        candidats: List[Symbol] = []
        for chemin, symboles in self._par_fichier.items():
            if not chemin.startswith(path_prefix):
                continue
            for symbole in symboles:
                if symbole.name.startswith("_"):
                    continue
                ailleurs = [
                    fichier for fichier in self._usages.get(symbole.name, set())
                    if fichier != chemin
                ]
                if not ailleurs:
                    candidats.append(symbole)
        return sorted(candidats, key=lambda symbole: (symbole.path, symbole.line))

    def summary(self) -> Dict[str, object]:
        """Résume l'index : volume, méthodes indexées, définitions ambiguës."""
        tous = [symbole for symboles in self._par_fichier.values() for symbole in symboles]
        return {
            "files": len(self._par_fichier),
            "symbols": len(tous),
            "classes": sum(1 for symbole in tous if symbole.kind == "class"),
            "functions": sum(1 for symbole in tous if symbole.kind == "function"),
            "methods": sum(1 for symbole in tous if symbole.kind == "method"),
            "ambiguous_names": sum(
                1 for symboles in self._definitions.values() if len(symboles) > 1
            ),
        }


def _signature(noeud) -> str:
    """
    Rend la signature déclarée d'une fonction.

    Les valeurs par défaut ne sont pas rendues : elles peuvent contenir un
    appel, et ce qui compte ici est **l'ordre et le nom des paramètres**, qui
    est ce qu'un changement casse chez les appelants.
    """
    arguments = noeud.args
    parties: List[str] = [argument.arg for argument in arguments.posonlyargs]
    if arguments.posonlyargs:
        parties.append("/")
    parties.extend(argument.arg for argument in arguments.args)
    if arguments.vararg:
        parties.append(f"*{arguments.vararg.arg}")
    elif arguments.kwonlyargs:
        parties.append("*")
    parties.extend(argument.arg for argument in arguments.kwonlyargs)
    if arguments.kwarg:
        parties.append(f"**{arguments.kwarg.arg}")
    return f"({', '.join(parties)})"
