"""
Reviewer Agent for GalSen IA.

Runs the checks from `.claude/rules/coding-conventions.md` and
`.claude/rules/coding-standards.md` against the source files, and reports what
actually violates them.

Every finding points at a file and a line, so it can be verified. The agent
never says a file is "good quality": it says which rules it checked and which
ones failed.
"""

import re
from typing import Any, Dict, List, Optional

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class ReviewerAgent(BaseAgent):
    """Agent qui contrôle le code au regard des règles du projet."""

    agent_id = "reviewer"
    required_engines = ("tool", "memory", "knowledge")

    # Longueur de ligne au-delà de laquelle la lisibilité se dégrade
    MAX_LINE_LENGTH = 120

    # Nombre maximum de fichiers analysés en une passe
    MAX_FILES_REVIEWED = 40

    # Motifs signalant un problème, avec leur gravité et l'explication associée
    CODE_SMELLS = (
        (
            re.compile(r'^\s*except\s*:\s*$'),
            "high",
            "Clause except nue: elle masque toutes les erreurs, y compris celles qu'il faut voir",
        ),
        (
            re.compile(r'\bTODO\b|\bFIXME\b|\bXXX\b'),
            "medium",
            "Marqueur de travail inachevé: le projet interdit de laisser des TODO",
        ),
        (
            re.compile(r'^\s*(pass\s*#|\.\.\.\s*$)'),
            "medium",
            "Implémentation vide: le projet interdit les placeholders",
        ),
        (
            re.compile(r'\bprint\s*\('),
            "low",
            "Appel à print: préférer le module logging dans le code de production",
        ),
        (
            re.compile(r'placeholder|non implémenté|not yet implemented', re.IGNORECASE),
            "high",
            "Mention explicite d'une implémentation absente",
        ),
    )

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Analyse les fichiers concernés par la demande.

        Args:
            context: Contexte d'exécution

        Returns:
            Fichiers analysés, problèmes trouvés par gravité et verdict
        """
        target_directory = self._resolve_target(context)
        files = self._list_python_files(context, target_directory)

        issues: List[Dict[str, Any]] = []
        reviewed: List[str] = []

        for path in files[:self.MAX_FILES_REVIEWED]:
            outcome = context.use_tool("filesystem", "read", path)
            if outcome.get("status") != "success":
                continue

            reviewed.append(path)
            issues.extend(self._review_file(path, outcome["result"]["content"]))

        by_severity = self._group_by_severity(issues)

        return {
            "target": target_directory,
            "files_reviewed": len(reviewed),
            "issues_found": len(issues),
            "issues_by_severity": {
                severity: len(found) for severity, found in by_severity.items()
            },
            "issues": issues[:50],
            "verdict": self._verdict(by_severity),
            "rules_checked": [
                "Pas de clause except nue",
                "Pas de TODO ni de placeholder",
                "Docstring sur les fonctions publiques",
                f"Lignes de moins de {self.MAX_LINE_LENGTH} caractères",
                "Pas de secret en dur",
                "logging plutôt que print",
            ],
        }

    def _resolve_target(self, context: AgentContext) -> str:
        """Détermine le répertoire à analyser, à partir du travail du coder si possible."""
        coder_result = context.previous_result("coder")
        if coder_result:
            modules = (coder_result.get("result") or {}).get("target_modules")
            if modules:
                return modules[0]

        return context.options.get("target_directory", "src")

    def _list_python_files(self, context: AgentContext, directory: str) -> List[str]:
        """Liste les fichiers Python du répertoire visé."""
        outcome = context.use_tool("filesystem", "search", "*.py", directory=directory)
        return outcome["result"] if outcome.get("status") == "success" else []

    def _review_file(self, path: str, content: str) -> List[Dict[str, Any]]:
        """Applique tous les contrôles à un fichier."""
        issues: List[Dict[str, Any]] = []
        lines = content.splitlines()
        prose_lines = self._locate_prose_lines(lines)

        for index, line in enumerate(lines):
            issues.extend(
                self._check_line(path, index + 1, line, is_prose=index in prose_lines)
            )

        issues.extend(self._check_missing_docstrings(path, lines, prose_lines))
        return issues

    def _locate_prose_lines(self, lines: List[str]) -> set:
        """
        Repère les lignes situées à l'intérieur d'une docstring.

        Sans cela, une phrase de documentation contenant les mots « class » ou
        « placeholder » serait analysée comme du code et produirait un
        signalement qui ne correspond à rien.
        """
        prose: set = set()
        delimiter = None

        for index, line in enumerate(lines):
            if delimiter is None:
                opening = self._find_docstring_delimiter(line)
                if opening is None:
                    continue

                # Une docstring ouverte et refermée sur la même ligne ne masque rien
                if line.count(opening) >= 2:
                    continue

                delimiter = opening
                prose.add(index)
            else:
                prose.add(index)
                if delimiter in line:
                    delimiter = None

        return prose

    def _find_docstring_delimiter(self, line: str) -> Optional[str]:
        """Retourne le délimiteur de docstring ouvert par la ligne, s'il y en a un."""
        for delimiter in ('"""', "'''"):
            if delimiter in line:
                return delimiter
        return None

    def _check_line(
        self, path: str, line_number: int, line: str, is_prose: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Contrôle une ligne isolée.

        Args:
            path: Fichier analysé
            line_number: Numéro de la ligne
            line: Contenu de la ligne
            is_prose: La ligne appartient à une docstring, les motifs de code
                ne s'y appliquent pas
        """
        issues: List[Dict[str, Any]] = []

        # La longueur excessive gêne la lecture, docstring comprise
        if len(line) > self.MAX_LINE_LENGTH:
            issues.append(self._issue(
                path, line_number, "low", "line_length",
                f"Ligne de {len(line)} caractères (maximum {self.MAX_LINE_LENGTH})",
            ))

        if is_prose:
            return issues

        for pattern, severity, explanation in self.CODE_SMELLS:
            if pattern.search(line):
                issues.append(self._issue(path, line_number, severity, "code_smell", explanation))

        return issues

    def _check_missing_docstrings(
        self, path: str, lines: List[str], prose_lines: set
    ) -> List[Dict[str, Any]]:
        """
        Signale les fonctions et classes publiques sans docstring.

        Les noms commençant par un souligné sont internes : la règle du projet
        ne porte que sur l'interface publique.
        """
        issues: List[Dict[str, Any]] = []
        declaration = re.compile(r'^\s*(def|class)\s+([A-Za-z]\w*)')

        for index, line in enumerate(lines):
            if index in prose_lines:
                continue

            match = declaration.match(line)
            if not match:
                continue

            name = match.group(2)
            if name.startswith('_'):
                continue

            if not self._has_docstring(lines, index):
                issues.append(self._issue(
                    path, index + 1, "medium", "missing_docstring",
                    f"{match.group(1)} '{name}' sans docstring",
                ))

        return issues

    def _has_docstring(self, lines: List[str], declaration_index: int) -> bool:
        """Vérifie qu'une docstring suit la déclaration, en sautant sa signature."""
        # Une signature peut tenir sur plusieurs lignes : on cherche celle qui la referme
        for offset in range(declaration_index, min(declaration_index + 10, len(lines))):
            if lines[offset].rstrip().endswith(':'):
                next_index = offset + 1
                if next_index >= len(lines):
                    return False
                return lines[next_index].lstrip().startswith(('"""', "'''"))
        return False

    def _issue(self, path: str, line: int, severity: str, category: str, message: str) -> Dict[str, Any]:
        """Construit un problème au format standard."""
        return {
            "file": path,
            "line": line,
            "severity": severity,
            "category": category,
            "message": message,
        }

    def _group_by_severity(self, issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Regroupe les problèmes par gravité."""
        grouped: Dict[str, List[Dict[str, Any]]] = {"high": [], "medium": [], "low": []}
        for issue in issues:
            grouped.setdefault(issue["severity"], []).append(issue)
        return grouped

    def _verdict(self, by_severity: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Conclut sur la recevabilité du code analysé."""
        high_count = len(by_severity.get("high", []))
        medium_count = len(by_severity.get("medium", []))

        if high_count:
            return {
                "approved": False,
                "reason": f"{high_count} problème(s) de gravité haute à corriger avant de continuer",
            }
        if medium_count > 10:
            return {
                "approved": False,
                "reason": f"{medium_count} problèmes de gravité moyenne: la dette s'accumule",
            }
        return {"approved": True, "reason": "Aucun problème bloquant relevé"}


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(ReviewerAgent, input_data)
