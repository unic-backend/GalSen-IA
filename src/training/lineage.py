"""
D'où vient un modèle SamP ou ToP (VOLET 33, ch. 05 — ADR-014).

Un modèle servi dont personne ne peut dire sur quoi il a été entraîné est un
modèle qu'on ne peut ni corriger, ni défendre, ni reproduire. Le jour où SamP
répond quelque chose de faux, la première question sera « qu'est-ce qu'il a
appris, et d'où ? » — et il faut que la réponse existe.

Le registre inscrit, pour chaque version :

- **la base et sa licence.** C'est une obligation légale autant qu'une hygiène :
  ADR-014 écarte Llama parce que sa licence impose de porter « Llama » dans le
  nom, ce qui contredit l'identité SamP/ToP. Ne pas noter la licence, c'est
  découvrir le problème le jour de la publication.
- **le condensat des données**, pour qu'on puisse dire si deux versions ont vu le
  même corpus.
- **les mesures**, celles du chapitre 02 — et **une version qui n'a pas été
  mesurée est inscrite comme telle**, jamais avec un score supposé.
- **la décision de garder ou non.** Un entraînement raté qui n'apparaît nulle
  part sera refait. Un journal qui ne contient que des succès n'est pas un journal.
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

FICHIER = os.path.join("docs", "training", "lineage.jsonl")

# Licences sous lesquelles une adaptation peut porter le nom SamP ou ToP
# (ADR-014). La liste est courte à dessein : une licence absente d'ici demande
# une décision, pas une supposition.
LICENCES_PERMISSIVES = {"apache-2.0", "mit", "bsd-3-clause", "cc-by-4.0"}


@dataclass
class ModelVersion:
    """Une version entraînée de SamP ou de ToP."""

    name: str
    family: str
    base_model: str
    base_license: str
    method: str = "qlora"
    data_hash: str = ""
    data_description: str = ""
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    kept: Optional[bool] = None
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la version."""
        return {
            "name": self.name,
            "family": self.family,
            "base_model": self.base_model,
            "base_license": self.base_license,
            "method": self.method,
            "data_hash": self.data_hash,
            "data_description": self.data_description,
            "hyperparameters": self.hyperparameters,
            "metrics": self.metrics or None,
            "kept": self.kept,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    def license_is_permissive(self) -> bool:
        """Indique si la licence de la base autorise le renommage."""
        return self.base_license.strip().lower() in LICENCES_PERMISSIVES

    def issues(self) -> List[str]:
        """
        Retourne ce qui empêche de publier cette version.

        Un entraînement peut être excellent et impubliable : la licence de sa
        base décide, pas la qualité du résultat.
        """
        problemes = []
        if not self.license_is_permissive():
            problemes.append(
                f"licence « {self.base_license} » non permissive : renommer en "
                f"« {self.name} » demande une vérification juridique (ADR-014)."
            )
        if not self.metrics:
            problemes.append(
                "aucune mesure : un modèle non évalué ne peut pas être comparé "
                "à sa base, donc pas gardé pour une bonne raison (ch. 02)."
            )
        if not self.data_hash:
            problemes.append(
                "aucun condensat de données : impossible de dire si une autre "
                "version a vu le même corpus."
            )
        return problemes


class LineageRegistry:
    """
    Journal des versions entraînées, en JSONL versionné dans le dépôt.

    Exemple:
        registre = LineageRegistry()
        registre.record(ModelVersion(name="samp-1", family="samp", ...))
    """

    def __init__(self, chemin: Optional[str] = None):
        """
        Args:
            chemin: Fichier de lignée ; `docs/training/lineage.jsonl` par défaut.
                Un fichier du dépôt, pas une base : la lignée doit se relire dans
                une revue de code et suivre les branches.
        """
        self._chemin = chemin or os.path.join(self._racine(), FICHIER)

    @staticmethod
    def _racine() -> str:
        """Retourne la racine du dépôt."""
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    def record(self, version: ModelVersion) -> ModelVersion:
        """
        Inscrit une version, réussie ou non.

        Args:
            version: La version entraînée.

        Returns:
            La version inscrite.
        """
        os.makedirs(os.path.dirname(self._chemin), exist_ok=True)
        with open(self._chemin, "a", encoding="utf-8") as fichier:
            fichier.write(json.dumps(version.to_dict(), ensure_ascii=False) + "\n")
        return version

    def versions(self, family: Optional[str] = None) -> List[ModelVersion]:
        """Retourne les versions inscrites, éventuellement filtrées par famille."""
        if not os.path.isfile(self._chemin):
            return []

        trouvees = []
        with open(self._chemin, "r", encoding="utf-8") as fichier:
            for ligne in fichier:
                ligne = ligne.strip()
                if not ligne or ligne.startswith("//"):
                    continue
                try:
                    donnees = json.loads(ligne)
                except ValueError:
                    continue
                version = ModelVersion(
                    name=donnees["name"],
                    family=donnees.get("family", ""),
                    base_model=donnees.get("base_model", ""),
                    base_license=donnees.get("base_license", ""),
                    method=donnees.get("method", ""),
                    data_hash=donnees.get("data_hash", ""),
                    data_description=donnees.get("data_description", ""),
                    hyperparameters=donnees.get("hyperparameters", {}),
                    metrics=donnees.get("metrics") or {},
                    kept=donnees.get("kept"),
                    notes=donnees.get("notes", ""),
                    created_at=donnees.get("created_at", 0.0),
                )
                if family is None or version.family == family:
                    trouvees.append(version)
        return trouvees

    def latest(self, family: str) -> Optional[ModelVersion]:
        """
        Retourne la dernière version **gardée** d'une famille.

        Une version rejetée reste au journal — elle dit ce qui a été essayé —
        mais elle n'est jamais rendue comme la version courante.
        """
        gardees = [version for version in self.versions(family) if version.kept]
        return max(gardees, key=lambda version: version.created_at) if gardees else None

    def summary(self) -> Dict[str, Any]:
        """Résume la lignée : versions par famille, gardées, publiables."""
        toutes = self.versions()
        familles: Dict[str, Dict[str, int]] = {}
        for version in toutes:
            compte = familles.setdefault(version.family, {"versions": 0, "kept": 0, "publishable": 0})
            compte["versions"] += 1
            if version.kept:
                compte["kept"] += 1
            if not version.issues():
                compte["publishable"] += 1
        return {"total": len(toutes), "by_family": familles, "path": self._chemin}
