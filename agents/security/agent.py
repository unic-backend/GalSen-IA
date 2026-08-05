"""
Security Agent for GalSen IA.

Enforces `.claude/rules/security.md` by scanning the source for the things that
rule forbids: hardcoded credentials, dangerous calls, and unprotected `.env`
files.

Findings are reported, never fixed automatically. A secret found in the code has
to be rotated, not merely deleted from the file, and that decision belongs to a
human.
"""

import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module


class SecurityAgent(BaseAgent):
    """Agent qui recherche les risques de sécurité dans le code du projet."""

    agent_id = "security"
    required_engines = ("tool", "memory", "knowledge")

    MAX_FILES_SCANNED = 60

    # Motifs de secrets en dur. La valeur doit être un littéral non vide et ne
    # pas ressembler à un appel de configuration, sinon toute lecture légitime
    # de variable d'environnement serait signalée.
    SECRET_PATTERNS = (
        (
            re.compile(
                r'''(?i)\b(api[_-]?key|secret|password|passwd|token|access[_-]?key)\s*=\s*["'][^"'\s]{8,}["']'''
            ),
            "critical",
            "Secret potentiellement codé en dur",
        ),
        (
            re.compile(r'(?i)\b(sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b'),
            "critical",
            "Clé d'API reconnaissable à son préfixe",
        ),
        (
            re.compile(r'(?i)-----BEGIN\s+(RSA|OPENSSH|DSA|EC|PGP)\s+PRIVATE KEY-----'),
            "critical",
            "Clé privée présente dans le dépôt",
        ),
    )

    # Appels dont l'usage doit être justifié
    DANGEROUS_PATTERNS = (
        (re.compile(r'\beval\s*\('), "high", "eval() exécute du code arbitraire"),
        (re.compile(r'\bexec\s*\('), "high", "exec() exécute du code arbitraire"),
        (re.compile(r'shell\s*=\s*True'), "high", "shell=True expose à l'injection de commande"),
        (re.compile(r'\bpickle\.loads?\s*\('), "high", "pickle désérialise du code exécutable"),
        (re.compile(r'\bos\.system\s*\('), "high", "os.system() passe par un shell"),
        (re.compile(r'verify\s*=\s*False'), "high", "Vérification TLS désactivée"),
        (re.compile(r'(?i)\byaml\.load\s*\((?!.*Loader\s*=)'), "medium",
         "yaml.load() sans Loader sûr: utiliser yaml.safe_load()"),
    )

    # Valeurs manifestement factices, à ne pas signaler comme des secrets réels
    PLACEHOLDER_VALUES = ("test-key", "your-key", "changeme", "example", "xxxxx", "placeholder", "dummy")

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Analyse le projet à la recherche de risques de sécurité.

        Args:
            context: Contexte d'exécution

        Returns:
            Fichiers analysés, vulnérabilités trouvées et état des protections
        """
        files = self._list_source_files(context)

        findings: List[Dict[str, Any]] = []
        scanned: List[str] = []

        for path in files[:self.MAX_FILES_SCANNED]:
            outcome = context.use_tool("filesystem", "read", path)
            if outcome.get("status") != "success":
                continue

            scanned.append(path)
            findings.extend(self._scan_content(path, outcome["result"]["content"]))

        protections = self._check_repository_protections(context)
        findings.extend(protections["findings"])

        by_severity = self._group_by_severity(findings)

        return {
            "files_scanned": len(scanned),
            "findings_count": len(findings),
            "findings_by_severity": {
                severity: len(items) for severity, items in by_severity.items()
            },
            "findings": findings[:50],
            "repository_protections": protections["state"],
            "verdict": self._verdict(by_severity),
            "rules_enforced": [
                "Aucun secret en dur",
                "Aucune clé privée dans le dépôt",
                ".env couvert par .gitignore",
                "Pas d'eval, exec, os.system ni shell=True",
                "Pas de désérialisation pickle de données externes",
                "Vérification TLS active",
            ],
        }

    def _list_source_files(self, context: AgentContext) -> List[str]:
        """Liste les fichiers Python du projet."""
        outcome = context.use_tool("filesystem", "search", "*.py", directory="src")
        source_files = outcome["result"] if outcome.get("status") == "success" else []

        agents_outcome = context.use_tool("filesystem", "search", "*.py", directory="agents")
        if agents_outcome.get("status") == "success":
            source_files.extend(agents_outcome["result"])

        return source_files

    def _scan_content(self, path: str, content: str) -> List[Dict[str, Any]]:
        """Applique tous les motifs de détection à un fichier."""
        findings: List[Dict[str, Any]] = []

        for line_number, line in enumerate(content.splitlines(), start=1):
            for pattern, severity, explanation in self.SECRET_PATTERNS:
                if pattern.search(line) and not self._is_placeholder(line):
                    findings.append(self._finding(
                        path, line_number, severity, "hardcoded_secret", explanation,
                        "Déplacer la valeur dans une variable d'environnement et la révoquer",
                    ))

            for pattern, severity, explanation in self.DANGEROUS_PATTERNS:
                if pattern.search(line):
                    findings.append(self._finding(
                        path, line_number, severity, "dangerous_call", explanation,
                        "Remplacer par une alternative sûre ou justifier l'usage en commentaire",
                    ))

        return findings

    def _is_placeholder(self, line: str) -> bool:
        """Indique si la valeur détectée est manifestement un exemple."""
        normalized = line.lower()
        return any(marker in normalized for marker in self.PLACEHOLDER_VALUES)

    def _check_repository_protections(self, context: AgentContext) -> Dict[str, Any]:
        """Vérifie que le dépôt protège bien les fichiers sensibles."""
        findings: List[Dict[str, Any]] = []
        state: Dict[str, Any] = {}

        gitignore = context.use_tool("filesystem", "read", ".gitignore")
        if gitignore.get("status") == "success":
            content = gitignore["result"]["content"]
            env_protected = ".env" in content
            state["gitignore_present"] = True
            state["env_ignored"] = env_protected

            if not env_protected:
                findings.append(self._finding(
                    ".gitignore", 0, "critical", "unprotected_secrets",
                    ".env n'est pas listé dans .gitignore",
                    "Ajouter .env à .gitignore avant tout commit",
                ))
        else:
            state["gitignore_present"] = False
            findings.append(self._finding(
                ".gitignore", 0, "high", "unprotected_secrets",
                "Aucun fichier .gitignore",
                "Créer un .gitignore couvrant .env, les clés et les artefacts de build",
            ))

        # Un .env présent dans l'arborescence mérite un contrôle explicite
        env_files = context.use_tool("filesystem", "search", ".env*", directory=".", max_depth=2)
        state["env_files_found"] = env_files["result"] if env_files.get("status") == "success" else []

        return {"findings": findings, "state": state}

    def _finding(self, path: str, line: int, severity: str, category: str,
                 message: str, remediation: str) -> Dict[str, Any]:
        """Construit un signalement au format standard."""
        return {
            "file": path,
            "line": line,
            "severity": severity,
            "category": category,
            "message": message,
            "remediation": remediation,
        }

    def _group_by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Regroupe les signalements par gravité."""
        grouped: Dict[str, List[Dict[str, Any]]] = {"critical": [], "high": [], "medium": [], "low": []}
        for finding in findings:
            grouped.setdefault(finding["severity"], []).append(finding)
        return grouped

    def _verdict(self, by_severity: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Conclut sur le niveau de risque du projet."""
        critical_count = len(by_severity.get("critical", []))
        high_count = len(by_severity.get("high", []))

        if critical_count:
            return {
                "safe": False,
                "risk_level": "critical",
                "reason": f"{critical_count} problème(s) critique(s): traiter avant tout commit",
            }
        if high_count:
            return {
                "safe": False,
                "risk_level": "high",
                "reason": f"{high_count} appel(s) dangereux à revoir",
            }
        return {"safe": True, "risk_level": "low", "reason": "Aucun risque bloquant détecté"}


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Requête à traiter

    Returns:
        Résultat de l'agent au format standard
    """
    return run_agent_module(SecurityAgent, input_data)
