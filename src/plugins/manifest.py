"""
Plugin manifests: what a third party declares before anything of theirs runs.

A plugin system is where a platform stops being responsible only for its own
code. Everything else in this repository was written here; a plugin is not, and
the whole design follows from that single fact.

**Nothing runs undeclared.** A plugin arrives with a manifest naming its author,
its version, what it does, and — the part that matters — **which capabilities it
asks for**, in the vocabulary the tools already use (`Effect`, `DataScope`). A
plugin that asks for nothing gets nothing; a plugin that asks is judged on what
it asked, before its code is read.

**Declaring is not enabling.** The same rule as knowledge sources (ADR-021):
installing a plugin puts it in the registry, disabled. Enabling it is a separate,
human decision. The two states are different, and merging them would mean the act
of copying a file was the act of trusting its author.

**Two combinations are refused outright, at declaration.** A plugin that reads
private user data *and* reaches outside the machine is an exfiltration path
however well-intentioned — the same rule `capabilities.py` holds for tools. And a
plugin that asks for `system` scope is asking to modify the platform that judges
it, which no manifest can make safe.

**A refusal names the rule it broke.** A plugin author who cannot see why they
were refused will guess, and guessing produces a manifest that passes without
being safer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.tool.capabilities import DataScope, Effect

#: Forme d'un identifiant de greffon. Étroite volontairement : il sert de nom de
#: répertoire, de clé de registre et d'identifiant dans les journaux.
MOTIF_IDENTIFIANT = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")

#: Champs qu'un manifeste doit porter. Aucun n'a de valeur par défaut : un défaut
#: silencieux ferait passer un oubli pour une décision.
CHAMPS_OBLIGATOIRES = ("plugin_id", "version", "author", "description", "entry_point")


class ManifestRefused(ValueError):
    """Un manifeste refusé, avec la règle qu'il enfreint."""


@dataclass
class PluginManifest:
    """
    Ce qu'un greffon déclare de lui-même.

    Attributes:
        plugin_id: Son identifiant.
        version: Sa version, telle que son auteur la nomme.
        author: Qui l'a écrit. Une chaîne libre : ce dépôt ne vérifie aucune
            identité et ne prétend pas le contraire.
        description: Ce qu'il fait, en une phrase lisible.
        entry_point: Le fichier Python exécuté.
        effects: Ce qu'il fait au monde.
        scopes: Les classes de données qu'il atteint.
        enabled: Faux à l'installation. Activer est une décision humaine
            distincte.
    """

    plugin_id: str
    version: str
    author: str
    description: str
    entry_point: str
    effects: List[Effect] = field(default_factory=list)
    scopes: List[DataScope] = field(default_factory=list)
    enabled: bool = False

    @property
    def reaches_private(self) -> bool:
        """Vrai s'il atteint une donnée appartenant à quelqu'un."""
        return DataScope.USER_PRIVATE in self.scopes

    @property
    def leaves_the_machine(self) -> bool:
        """Vrai s'il sort de la machine."""
        return Effect.EXTERNAL in self.effects

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "plugin_id": self.plugin_id,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "entry_point": self.entry_point,
            "effects": [effet.value for effet in self.effects],
            "scopes": [portee.value for portee in self.scopes],
            "enabled": self.enabled,
            "reaches_private": self.reaches_private,
            "leaves_the_machine": self.leaves_the_machine,
        }


def _liste(valeurs: Any, classe: Any, champ: str, identifiant: str) -> List[Any]:
    """Lit une liste de valeurs d'énumération, ou refuse en nommant la faute."""
    lues = []
    for valeur in (valeurs or []):
        try:
            lues.append(classe(str(valeur).strip().lower()))
        except ValueError:
            connues = ", ".join(membre.value for membre in classe)
            raise ManifestRefused(
                f"Greffon « {identifiant} » : « {valeur} » n'est pas un {champ} "
                f"connu. Valeurs possibles : {connues}."
            ) from None
    return lues


def read_manifest(declaration: Dict[str, Any]) -> PluginManifest:
    """
    Lit un manifeste, ou le refuse en nommant la règle enfreinte.

    Args:
        declaration: Le manifeste déclaré.

    Returns:
        Le manifeste validé, **désactivé** quoi qu'il déclare : `enabled` dans
        un manifeste serait l'auteur s'accordant sa propre confiance.

    Raises:
        ManifestRefused: Champ manquant, identifiant mal formé, valeur inconnue,
            ou combinaison de capacités interdite.
    """
    declaration = declaration or {}
    identifiant = str(declaration.get("plugin_id", "") or "?").strip()

    manquants = [
        champ for champ in CHAMPS_OBLIGATOIRES
        if not str(declaration.get(champ, "") or "").strip()
    ]
    if manquants:
        raise ManifestRefused(
            f"Greffon « {identifiant} » : champs manquants — "
            f"{', '.join(manquants)}. Aucun n'a de défaut : un défaut "
            "silencieux ferait passer un oubli pour une décision."
        )

    if not MOTIF_IDENTIFIANT.match(identifiant):
        raise ManifestRefused(
            f"Identifiant « {identifiant} » mal formé : minuscules, chiffres, "
            "tiret et souligné, de 3 à 40 caractères. Il sert de nom de "
            "répertoire et de clé de journal."
        )

    effets = _liste(declaration.get("effects"), Effect, "effet", identifiant)
    portees = _liste(declaration.get("scopes"), DataScope, "portée", identifiant)

    manifeste = PluginManifest(
        plugin_id=identifiant,
        version=str(declaration["version"]).strip(),
        author=str(declaration["author"]).strip(),
        description=str(declaration["description"]).strip(),
        entry_point=str(declaration["entry_point"]).strip(),
        effects=effets,
        scopes=portees,
        # Jamais lu du manifeste : ce serait l'auteur s'accordant sa propre
        # confiance.
        enabled=False,
    )

    refus = forbidden_combination(manifeste)
    if refus:
        raise ManifestRefused(refus)
    return manifeste


def forbidden_combination(manifeste: PluginManifest) -> Optional[str]:
    """
    La règle qu'un manifeste enfreint, ou `None`.

    Deux combinaisons sont refusées, et aucune n'est une question d'intention.

    Args:
        manifeste: Le manifeste examiné.

    Returns:
        La raison du refus, en clair.
    """
    if manifeste.reaches_private and manifeste.leaves_the_machine:
        return (
            f"Greffon « {manifeste.plugin_id} » : il demande la donnée privée "
            "**et** la sortie de la machine. C'est un chemin d'exfiltration "
            "quelles que soient les intentions de son auteur — la même règle "
            "que les outils de la plateforme tiennent depuis le VOLET 38."
        )
    if DataScope.SYSTEM in manifeste.scopes:
        return (
            f"Greffon « {manifeste.plugin_id} » : il demande la portée "
            "`system`, c'est-à-dire le droit de modifier la plateforme qui le "
            "juge. Aucun manifeste ne peut rendre cela sûr."
        )
    return None


def manifest_report() -> Dict[str, Any]:
    """
    Ce qu'un manifeste doit porter, et ce que ce module refuse.

    Returns:
        Les champs obligatoires, les règles et leurs raisons.
    """
    return {
        "required_fields": list(CHAMPS_OBLIGATOIRES),
        "effects": [effet.value for effet in Effect],
        "scopes": [portee.value for portee in DataScope],
        "rules": [
            "Rien ne tourne sans manifeste : un greffon déclare ce qu'il "
            "demande, et il est jugé là-dessus avant que son code soit lu.",
            "Déclarer n'est pas activer : installer inscrit, désactivé. "
            "Activer est une décision humaine distincte — sinon copier un "
            "fichier vaudrait faire confiance à son auteur.",
            "Donnée privée **et** sortie de la machine : refusé à la "
            "déclaration. C'est un chemin d'exfiltration, pas une intention.",
            "Portée `system` : refusée. C'est demander à modifier la "
            "plateforme qui juge le greffon.",
            "`enabled` n'est jamais lu du manifeste : ce serait l'auteur "
            "s'accordant sa propre confiance.",
        ],
        "does_not": [
            "Vérifier l'identité d'un auteur : `author` est une chaîne libre, "
            "et prétendre le contraire serait pire que de ne rien vérifier.",
            "Analyser le code du greffon : un manifeste juge une déclaration.",
        ],
    }
