"""
Le graphe d'imports du dépôt (VOLET 34, ch. 10, phase 1).

`repo_map.py` (VOLET 31) répond à « où regarder ». Il ne répond pas à la question
qui vient juste après, et qui est celle que `.claude/rules/verification.md` pose
avant toute modification : **qui casse si je change ce fichier ?**

## Ce que la carte seule ne pouvait pas dire

Mesuré avant d'écrire ce module : la carte relie un fichier à son test **par
convention de nom**, et ne trouve un test que pour **67 fichiers sur 308**
(21,75 %). `src/mcp/exposure.py` en ressort sans test — alors que
`tests/test_mcp.py` le couvre entièrement. La convention de nom n'est pas
fausse, elle est incomplète : elle ignore le fait que la vérité est écrite dans
le code, sous la forme d'un `import`.

Ce module lit donc les imports plutôt que les noms de fichiers :

- **`imports_of`** — ce dont un fichier dépend ;
- **`imported_by`** — ce qui dépend de lui, directement ;
- **`impact_of`** — et **transitivement**, ce qui est le rayon d'une modification ;
- **`tests_to_run`** — les tests qui importent réellement ce rayon, plutôt que
  ceux dont le nom ressemble ;
- **`cycles`** — les dépendances circulaires, qui rendent l'ordre d'import
  significatif et cassent au premier déplacement d'un import.

La règle *« vérifie qui appelle avant de changer une signature »* devient ainsi
une requête, au lieu de dépendre de la mémoire de celui qui modifie.
"""

import ast
import logging
import os
from typing import Dict, List, Optional, Set, Tuple

from .repo_map import IGNORES

logger = logging.getLogger(__name__)

#: Répertoires parcourus par défaut : le code du projet, plus les tests. Les
#: tests sont dans le graphe **volontairement** — sans eux, `tests_to_run` ne
#: pourrait rien répondre d'autre que ce que la convention de nom devinait déjà.
PAQUETS = ("src", "agents", "tools")
TESTS = "tests"


class RepoGraph:
    """
    Qui importe quoi, dans ce dépôt.

    Exemple:
        graphe = RepoGraph().build()
        graphe.impact_of("src/mcp/exposure.py")    # ce qui casse
        graphe.tests_to_run("src/mcp/exposure.py") # ce qu'il faut relancer
    """

    def __init__(
        self,
        root: Optional[str] = None,
        packages: Tuple[str, ...] = PAQUETS,
        tests_dir: str = TESTS,
    ) -> None:
        """
        Args:
            root: Racine du dépôt ; déduite de l'emplacement de ce fichier sinon.
            packages: Répertoires de code parcourus.
            tests_dir: Répertoire des tests, inclus dans le graphe.
        """
        self.root = os.path.realpath(root or self._racine_par_defaut())
        self._packages = tuple(packages)
        self._tests_dir = tests_dir
        self._modules: Dict[str, str] = {}
        self._imports: Dict[str, Set[str]] = {}
        self._immediats: Dict[str, Set[str]] = {}
        self._importers: Dict[str, Set[str]] = {}
        self._externes: Dict[str, Set[str]] = {}

    @staticmethod
    def _racine_par_defaut() -> str:
        """Retourne la racine du dépôt."""
        return os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self) -> "RepoGraph":
        """
        Construit le graphe, en deux passes.

        La première recense les modules — il faut connaître **tous** les noms
        avant de pouvoir dire si `src.mcp.exposure` est interne ou étranger. La
        seconde lit les imports de chaque fichier.
        """
        self._modules.clear()
        self._imports.clear()
        self._immediats.clear()
        self._importers.clear()
        self._externes.clear()

        fichiers: List[str] = []
        for repertoire in (*self._packages, self._tests_dir):
            fichiers.extend(self._fichiers_python(repertoire))

        for chemin in fichiers:
            self._modules[self._module_de(chemin)] = chemin

        for chemin in fichiers:
            internes, immediats, externes = self._lire_imports(chemin)
            self._imports[chemin] = internes
            self._immediats[chemin] = immediats
            self._externes[chemin] = externes
            for cible in internes:
                self._importers.setdefault(cible, set()).add(chemin)

        logger.debug(
            "Graphe d'imports : %d fichier(s), %d arête(s) interne(s).",
            len(self._imports), sum(len(cibles) for cibles in self._imports.values()),
        )
        return self

    def _fichiers_python(self, sous_repertoire: str) -> List[str]:
        """Retourne les fichiers Python d'un sous-répertoire, chemins relatifs."""
        base = os.path.join(self.root, sous_repertoire)
        if not os.path.isdir(base):
            return []

        trouves: List[str] = []
        for dossier, sous_dossiers, noms in os.walk(base):
            sous_dossiers[:] = [d for d in sous_dossiers if d not in IGNORES]
            for nom in noms:
                if nom.endswith(".py"):
                    absolu = os.path.join(dossier, nom)
                    trouves.append(
                        os.path.relpath(absolu, self.root).replace(os.sep, "/")
                    )
        return sorted(trouves)

    @staticmethod
    def _module_de(chemin_relatif: str) -> str:
        """Retourne le nom pointé d'un fichier : `src/mcp/server.py` → `src.mcp.server`."""
        sans_extension = chemin_relatif[:-3] if chemin_relatif.endswith(".py") else chemin_relatif
        pointe = sans_extension.replace("/", ".")
        if pointe.endswith(".__init__"):
            pointe = pointe[: -len(".__init__")]
        return pointe

    def _lire_imports(self, chemin_relatif: str) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Lit les imports d'un fichier.

        Returns:
            Les fichiers internes importés, ceux importés **au chargement du
            module** (hors corps de fonction), et les paquets étrangers.
        """
        absolu = os.path.join(self.root, chemin_relatif)
        try:
            with open(absolu, "r", encoding="utf-8") as fichier:
                arbre = ast.parse(fichier.read())
        except (OSError, UnicodeDecodeError, SyntaxError) as erreur:
            # Un fichier illisible sort du graphe en le disant, plutôt que
            # d'interrompre la construction et de laisser un graphe partiel
            # qu'on croirait complet.
            logger.debug("Fichier hors graphe (%s) : %s", chemin_relatif, erreur)
            return set(), set(), set()

        internes: Set[str] = set()
        immediats: Set[str] = set()
        externes: Set[str] = set()
        for noeud, differe in self._noeuds_import(arbre):
            for cible in self._cibles_du_noeud(noeud, chemin_relatif):
                fichier_interne = self._resoudre(cible)
                if fichier_interne is not None and fichier_interne != chemin_relatif:
                    internes.add(fichier_interne)
                    if not differe:
                        immediats.add(fichier_interne)
                elif fichier_interne is None:
                    externes.add(cible.split(".")[0])
        return internes, immediats, externes

    @staticmethod
    def _noeuds_import(arbre: ast.AST):
        """
        Parcourt les nœuds d'import, en disant lesquels sont différés.

        Un import placé dans un corps de fonction ne s'exécute qu'à l'appel : il
        crée une dépendance réelle, mais **pas** au chargement du module. C'est
        la différence entre un cycle qui casse le démarrage et un cycle que
        Python tolère — les confondre ferait signaler des pannes qui n'existent
        pas, et manquer celles qui existent.
        """
        pile = [(arbre, False)]
        while pile:
            noeud, differe = pile.pop()
            if isinstance(noeud, (ast.Import, ast.ImportFrom)):
                yield noeud, differe
                continue
            dans_fonction = differe or isinstance(
                noeud, (ast.FunctionDef, ast.AsyncFunctionDef)
            )
            for enfant in ast.iter_child_nodes(noeud):
                pile.append((enfant, dans_fonction))

    def _cibles_du_noeud(self, noeud: ast.AST, chemin_relatif: str) -> List[str]:
        """Retourne les noms pointés qu'un nœud d'import désigne."""
        if isinstance(noeud, ast.Import):
            return [alias.name for alias in noeud.names]
        if not isinstance(noeud, ast.ImportFrom):
            return []

        base = noeud.module or ""
        if noeud.level:
            # Import relatif : le point de départ est le paquet du fichier, et
            # chaque niveau supplémentaire remonte d'un cran.
            paquet = self._module_de(chemin_relatif).split(".")
            if not chemin_relatif.endswith("/__init__.py"):
                paquet = paquet[:-1]
            remontee = noeud.level - 1
            if remontee:
                paquet = paquet[:-remontee] if remontee < len(paquet) else []
            base = ".".join([*paquet, base] if base else paquet)

        if not base:
            return []
        # `from x import y` peut désigner le module `x.y` comme un symbole de
        # `x` ; les deux sont proposés, et seule la résolution tranche.
        return [f"{base}.{alias.name}" for alias in noeud.names] + [base]

    def _resoudre(self, nom_pointe: str) -> Optional[str]:
        """
        Retourne le fichier interne désigné par un nom pointé, ou None.

        Un nom qui ne se résout pas est **étranger**, pas manquant : `json` et
        `fastapi` passent par ici à chaque fichier.
        """
        parties = nom_pointe.split(".")
        while parties:
            candidat = ".".join(parties)
            if candidat in self._modules:
                return self._modules[candidat]
            parties.pop()
        return None

    # ------------------------------------------------------------------
    # Consultation
    # ------------------------------------------------------------------

    def files(self) -> List[str]:
        """Retourne les fichiers du graphe."""
        return sorted(self._imports)

    def imports_of(self, chemin_relatif: str) -> List[str]:
        """Retourne ce dont un fichier dépend, directement."""
        return sorted(self._imports.get(chemin_relatif, set()))

    def imported_by(self, chemin_relatif: str) -> List[str]:
        """Retourne ce qui dépend d'un fichier, directement."""
        return sorted(self._importers.get(chemin_relatif, set()))

    def external_imports(self, chemin_relatif: str) -> List[str]:
        """Retourne les paquets étrangers dont un fichier dépend."""
        return sorted(self._externes.get(chemin_relatif, set()))

    def impact_of(self, chemin_relatif: str, depth: Optional[int] = None) -> List[str]:
        """
        Retourne tout ce qui dépend d'un fichier, transitivement.

        C'est le rayon d'une modification : le fichier lui-même n'y figure pas,
        et un cycle ne fait pas boucler — un fichier déjà vu n'est pas revisité.

        Args:
            chemin_relatif: Fichier modifié.
            depth: Profondeur maximale ; sans limite par défaut.
        """
        vus: Set[str] = set()
        frontiere = {chemin_relatif}
        niveau = 0
        while frontiere and (depth is None or niveau < depth):
            suivante: Set[str] = set()
            for fichier in frontiere:
                for dependant in self._importers.get(fichier, set()):
                    if dependant not in vus and dependant != chemin_relatif:
                        vus.add(dependant)
                        suivante.add(dependant)
            frontiere = suivante
            niveau += 1
        return sorted(vus)

    def tests_to_run(self, chemin_relatif: str) -> List[str]:
        """
        Retourne les tests qui importent le fichier ou son rayon d'impact.

        Mesuré, pas deviné : un test entre dans cette liste parce qu'il importe
        le code, pas parce que son nom lui ressemble. C'est ce qui manquait à
        `RepoMap.tests_for`, qui ne trouvait rien pour 241 fichiers sur 308.
        """
        rayon = {chemin_relatif, *self.impact_of(chemin_relatif)}
        prefixe = f"{self._tests_dir}/"
        return sorted(fichier for fichier in rayon if fichier.startswith(prefixe))

    def cycles(self, blocking: bool = False) -> List[List[str]]:
        """
        Retourne les cycles d'imports, un groupe de fichiers par cycle.

        Un cycle n'est pas toujours une faute — Python le tolère quand l'import
        est différé — mais il rend l'ordre d'import significatif : déplacer un
        import différé en tête de fichier suffit alors à casser le démarrage.

        Args:
            blocking: Ne retenir que les cycles formés d'imports exécutés au
                **chargement** des modules. Ceux-là ne se contournent pas : ils
                lèveraient `ImportError` à l'import du premier des deux.
        """
        aretes = self._immediats if blocking else self._imports
        index: Dict[str, int] = {}
        bas: Dict[str, int] = {}
        pile: List[str] = []
        sur_pile: Set[str] = set()
        composantes: List[List[str]] = []
        compteur = [0]

        def parcourir(depart: str) -> None:
            """Tarjan, en itératif : la récursion dépasserait la pile sur 500 fichiers."""
            travaux: List[Tuple[str, List[str]]] = [
                (depart, sorted(aretes.get(depart, set())))
            ]
            index[depart] = bas[depart] = compteur[0]
            compteur[0] += 1
            pile.append(depart)
            sur_pile.add(depart)

            while travaux:
                noeud, restants = travaux[-1]
                if restants:
                    voisin = restants.pop()
                    if voisin not in index:
                        index[voisin] = bas[voisin] = compteur[0]
                        compteur[0] += 1
                        pile.append(voisin)
                        sur_pile.add(voisin)
                        travaux.append((voisin, sorted(aretes.get(voisin, set()))))
                    elif voisin in sur_pile:
                        bas[noeud] = min(bas[noeud], index[voisin])
                    continue

                travaux.pop()
                if travaux:
                    parent = travaux[-1][0]
                    bas[parent] = min(bas[parent], bas[noeud])
                if bas[noeud] == index[noeud]:
                    composante = []
                    while True:
                        membre = pile.pop()
                        sur_pile.discard(membre)
                        composante.append(membre)
                        if membre == noeud:
                            break
                    if len(composante) > 1:
                        composantes.append(sorted(composante))

        for fichier in self.files():
            if fichier not in index:
                parcourir(fichier)
        return sorted(composantes)

    def describe(self, chemin_relatif: str) -> Dict[str, object]:
        """
        Décrit un fichier tel qu'un agent doit le voir avant de le modifier.

        C'est la réponse à « qui casse si je change ceci », en une seule lecture.
        """
        impact = self.impact_of(chemin_relatif)
        tests = self.tests_to_run(chemin_relatif)
        return {
            "path": chemin_relatif,
            "known": chemin_relatif in self._imports,
            "imports": self.imports_of(chemin_relatif),
            "imported_by": self.imported_by(chemin_relatif),
            "impact_count": len(impact),
            "tests_to_run": tests,
            # Un fichier dont personne ne dépend et qu'aucun test n'atteint est
            # le cas où une modification passe inaperçue jusqu'à la production.
            "untested": not tests,
        }

    def summary(self) -> Dict[str, object]:
        """Résume le graphe : volume, densité, cycles, fichiers hors de portée des tests."""
        fichiers = self.files()
        code = [f for f in fichiers if not f.startswith(f"{self._tests_dir}/")]
        sans_test = [f for f in code if not self.tests_to_run(f)]
        return {
            "files": len(fichiers),
            "code_files": len(code),
            "edges": sum(len(cibles) for cibles in self._imports.values()),
            "cycles": len(self.cycles()),
            # Séparés : un cycle bloquant est une panne au démarrage, un cycle
            # différé est un signal. Les additionner ferait passer les deux pour
            # la même chose.
            "blocking_cycles": len(self.cycles(blocking=True)),
            "code_reached_by_tests": len(code) - len(sans_test),
            "code_unreached_by_tests": len(sans_test),
        }
