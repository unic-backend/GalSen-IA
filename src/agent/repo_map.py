"""
Carte du dépôt (VOLET 31, ch. 01).

Un agent de développement doit savoir **où regarder** avant de savoir quoi
écrire. Sans carte, il ne lui reste que deux mauvaises options : lire le dépôt
entier — 387 fichiers Python, impossible à tenir dans un contexte — ou deviner,
ce qui produit du code branché nulle part.

Le motif vient d'OpenHands et d'Aider, qui construisent tous deux une
représentation compacte du dépôt avant de raisonner. **Seul le motif est repris**,
pas leur code : les deux supposent être l'application, alors qu'ici l'agent passe
par le moteur d'outils et par le portillon d'approbation (ADR-006).

Ce que la carte contient, et pourquoi chaque champ y est :

- **les modules et leurs fichiers**, pour situer une demande dans le dépôt ;
- **les symboles de premier niveau** (classes, fonctions), pour viser un fichier
  sans le lire en entier ;
- **le test qui couvre un module**, parce qu'une modification sans son test est
  une modification qu'on ne peut pas vérifier ;
- **la taille**, parce qu'un fichier de 3 000 lignes ne se modifie pas comme un
  fichier de 50.

La carte est **dérivée du code**, jamais tenue à la main : un inventaire
maintenu manuellement se périme au premier fichier ajouté, et ce dépôt a déjà
trouvé huit fois des déclarations que rien n'appliquait.
"""

import ast
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Répertoires que la carte ignore : ils ne contiennent pas de code du projet.
IGNORES = {
    "__pycache__", ".git", ".pytest_cache", "node_modules", ".venv", "venv",
    "data", "logs", "dist", "build", ".cache",
}


@dataclass
class FileEntry:
    """Un fichier du dépôt, tel que la carte le décrit."""

    path: str
    lines: int
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    tested_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise l'entrée, sans champ vide inutile."""
        donnees: Dict[str, Any] = {"path": self.path, "lines": self.lines}
        if self.classes:
            donnees["classes"] = self.classes
        if self.functions:
            donnees["functions"] = self.functions
        if self.tested_by:
            donnees["tested_by"] = self.tested_by
        return donnees


class RepoMap:
    """
    Représentation compacte du dépôt, dérivée du code.

    Exemple:
        carte = RepoMap()
        carte.find("rate limiter")          # où chercher
        carte.tests_for("src/api/rbac.py")  # ce qu'il faudra relancer
    """

    def __init__(self, root: Optional[str] = None, tests_dir: str = "tests"):
        """
        Args:
            root: Racine du dépôt ; déduite de l'emplacement de ce fichier sinon.
            tests_dir: Répertoire des tests, pour relier un module à sa couverture.
        """
        self.root = os.path.realpath(root or self._racine_par_defaut())
        self._tests_dir = tests_dir
        self._entrees: Dict[str, FileEntry] = {}
        self._tests: Dict[str, str] = {}

    @staticmethod
    def _racine_par_defaut() -> str:
        """Retourne la racine du dépôt."""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def build(self, sous_repertoires: Optional[List[str]] = None) -> "RepoMap":
        """
        Construit la carte.

        Args:
            sous_repertoires: Répertoires à parcourir ; `src`, `agents` et
                `tools` par défaut — le code du projet, sans ses dépendances.

        Returns:
            La carte, pour enchaîner les appels.
        """
        self._entrees.clear()
        self._tests.clear()

        for fichier in self._fichiers_python(self._tests_dir):
            self._tests[os.path.basename(fichier)] = fichier

        for repertoire in sous_repertoires or ("src", "agents", "tools"):
            for fichier in self._fichiers_python(repertoire):
                entree = self._decrire(fichier)
                if entree is not None:
                    self._entrees[entree.path] = entree

        logger.debug("Carte du dépôt : %d fichier(s) décrits.", len(self._entrees))
        return self

    def _fichiers_python(self, sous_repertoire: str) -> List[str]:
        """Retourne les fichiers Python d'un sous-répertoire, chemins relatifs."""
        base = os.path.join(self.root, sous_repertoire)
        if not os.path.isdir(base):
            return []

        trouves = []
        for dossier, sous_dossiers, fichiers in os.walk(base):
            sous_dossiers[:] = [d for d in sous_dossiers if d not in IGNORES]
            for nom in fichiers:
                if nom.endswith(".py"):
                    absolu = os.path.join(dossier, nom)
                    trouves.append(os.path.relpath(absolu, self.root))
        return sorted(trouves)

    def _decrire(self, chemin_relatif: str) -> Optional[FileEntry]:
        """Décrit un fichier : taille, symboles, test qui le couvre."""
        absolu = os.path.join(self.root, chemin_relatif)
        try:
            with open(absolu, "r", encoding="utf-8") as fichier:
                source = fichier.read()
        except (OSError, UnicodeDecodeError) as erreur:
            # Un fichier illisible ne doit pas vider la carte : il en sort, en
            # le disant, plutôt que d'interrompre la construction.
            logger.debug("Fichier ignoré dans la carte (%s) : %s", chemin_relatif, erreur)
            return None

        classes: List[str] = []
        fonctions: List[str] = []
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            arbre = None

        if arbre is not None:
            for noeud in arbre.body:
                if isinstance(noeud, ast.ClassDef):
                    classes.append(noeud.name)
                elif isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fonctions.append(noeud.name)

        return FileEntry(
            path=chemin_relatif,
            lines=source.count("\n") + 1,
            classes=classes,
            functions=fonctions,
            tested_by=self._test_de(chemin_relatif),
        )

    def _test_de(self, chemin_relatif: str) -> Optional[str]:
        """
        Retrouve le test qui couvre un fichier, par convention de nom.

        Le dépôt suit **deux** conventions, et n'en connaître qu'une fausse la
        mesure : `tests/test_<module>.py`, et `tests/test_<paquet>_<module>.py`
        quand plusieurs modules portent le même nom — `src/api/rate_limiter.py`
        et `src/model_engine/rate_limiter.py` ne peuvent pas partager
        `test_rate_limiter.py`.

        Ce n'est pas une garantie de couverture : c'est un point de départ pour
        savoir quoi relancer après une modification. Un fichier sans test nommé
        est rendu tel quel — inventer un lien serait pire que de dire qu'il manque.
        """
        base = os.path.splitext(os.path.basename(chemin_relatif))[0]
        if base == "__init__":
            base = os.path.basename(os.path.dirname(chemin_relatif))

        paquet = os.path.basename(os.path.dirname(chemin_relatif))
        for candidat in (f"test_{base}.py", f"test_{paquet}_{base}.py"):
            if candidat in self._tests:
                return self._tests[candidat]
        return None

    # ------------------------------------------------------------------
    # Consultation
    # ------------------------------------------------------------------

    def entries(self) -> List[FileEntry]:
        """Retourne toutes les entrées de la carte."""
        return list(self._entrees.values())

    def entry(self, chemin_relatif: str) -> Optional[FileEntry]:
        """Retourne l'entrée d'un fichier, ou None s'il n'est pas cartographié."""
        return self._entrees.get(chemin_relatif)

    def tests_for(self, chemin_relatif: str) -> Optional[str]:
        """Retourne le test couvrant un fichier, ou None."""
        entree = self._entrees.get(chemin_relatif)
        return entree.tested_by if entree else None

    def find(self, requete: str, limit: int = 10) -> List[FileEntry]:
        """
        Cherche où traiter une demande.

        La recherche porte sur le chemin **et sur les symboles** : « rate
        limiter » doit ramener `src/api/rate_limiter.py` comme
        `TokenBucketRateLimiter`.

        Args:
            requete: Mots de la demande.
            limit: Nombre maximal de fichiers rendus.

        Returns:
            Les fichiers les plus proches, du plus pertinent au moins pertinent.
        """
        termes = [terme for terme in requete.lower().replace("_", " ").split() if terme]
        if not termes:
            return []

        notes = []
        for entree in self._entrees.values():
            cible = entree.path.lower().replace("_", " ").replace("/", " ")
            symboles = " ".join(entree.classes + entree.functions).lower()
            symboles = symboles.replace("_", " ")
            note = sum(2 for terme in termes if terme in cible)
            note += sum(1 for terme in termes if terme in symboles)
            if note:
                notes.append((note, entree))

        notes.sort(key=lambda paire: (-paire[0], paire[1].path))
        return [entree for _, entree in notes[:limit]]

    def summary(self) -> Dict[str, Any]:
        """
        Résume le dépôt : volume, couverture par convention, plus gros fichiers.

        Le taux de fichiers sans test nommé est **la mesure la plus utile de la
        carte** : c'est là qu'une modification ne peut pas être vérifiée.
        """
        entrees = self.entries()
        if not entrees:
            return {"files": 0, "lines": 0, "with_named_test": 0, "coverage_by_convention": 0.0}

        avec_test = sum(1 for entree in entrees if entree.tested_by)
        plus_gros = sorted(entrees, key=lambda entree: -entree.lines)[:5]
        return {
            "files": len(entrees),
            "lines": sum(entree.lines for entree in entrees),
            "with_named_test": avec_test,
            "coverage_by_convention": round(avec_test / len(entrees), 4),
            "largest": [{"path": entree.path, "lines": entree.lines} for entree in plus_gros],
        }
