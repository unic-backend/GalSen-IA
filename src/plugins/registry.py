"""
The plugin registry: installed, enabled, and the distance between the two.

Installing a plugin and trusting it are different acts, and this registry exists
so that they cannot be confused. A plugin arrives, is validated against its
manifest, and sits there **disabled**. Someone with the authority to do so
enables it, and that act is recorded with who did it and why.

This is the same shape as the source registry (ADR-021), for the same reason: the
moment "it is present" starts meaning "it may run", the act of copying a file
becomes the act of granting permission.

Three further rules.

**An identifier belongs to one plugin.** Installing over an existing identifier
is refused, not merged: a plugin that silently replaced another would inherit its
authorisation without ever being judged.

**Disabling never asks why, enabling always does.** Turning something off in a
hurry must be free; turning it on is the decision that needs a trace.

**The registry knows nothing about code.** It holds declarations. What actually
runs a plugin, and under what bounds, is `src/plugins/execution.py` — and that
one delegates to the sandbox this repository already has (VOLET 34), rather than
inventing a second one that nobody has tried to escape from.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from .manifest import PluginManifest, read_manifest


class PluginRefused(ValueError):
    """Une opération refusée sur le registre, avec sa raison."""


class PluginRegistry:
    """
    Les greffons installés, et lesquels sont activés.

    En mémoire et thread-safe. Ne charge aucun code : il porte des
    déclarations.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._greffons: Dict[str, PluginManifest] = {}
        self._activations: Dict[str, Dict[str, str]] = {}
        # Où vit chaque greffon, quand il vient d'un répertoire. Un greffon
        # installé depuis un simple dictionnaire n'a pas de code sur le disque
        # et ne s'exécute donc pas : la distinction est portée ici.
        self._emplacements: Dict[str, Dict[str, str]] = {}

    # ------------------------------------------------------------------
    # Installer
    # ------------------------------------------------------------------

    def install(self, declaration: Dict[str, Any]) -> PluginManifest:
        """
        Installe un greffon depuis son manifeste — **désactivé**.

        Args:
            declaration: Le manifeste déclaré.

        Returns:
            Le manifeste validé.

        Raises:
            ManifestRefused: Le manifeste enfreint une règle.
            PluginRefused: L'identifiant est déjà pris.
        """
        manifeste = read_manifest(declaration)
        with self._verrou:
            if manifeste.plugin_id in self._greffons:
                raise PluginRefused(
                    f"Greffon « {manifeste.plugin_id} » déjà installé. "
                    "Réinstaller par-dessus est refusé : un greffon qui en "
                    "remplacerait un autre en silence hériterait de son "
                    "autorisation sans avoir été jugé. Désinstallez d'abord."
                )
            self._greffons[manifeste.plugin_id] = manifeste
        return manifeste

    def bind_directory(self, plugin_id: str, directory: str, entry_file: str) -> None:
        """
        Rattache un greffon au code qui lui appartient.

        Args:
            plugin_id: Le greffon.
            directory: Son répertoire.
            entry_file: Le fichier réellement exécuté, déjà vérifié.
        """
        with self._verrou:
            self._emplacements[plugin_id] = {
                "directory": directory, "entry_file": entry_file,
            }

    def location_of(self, plugin_id: str) -> Optional[Dict[str, str]]:
        """Où vit un greffon, ou `None` s'il n'a pas de code sur le disque."""
        with self._verrou:
            emplacement = self._emplacements.get(plugin_id)
            return dict(emplacement) if emplacement else None

    def uninstall(self, plugin_id: str) -> bool:
        """
        Retire un greffon et son activation.

        Args:
            plugin_id: Le greffon.

        Returns:
            Vrai s'il était installé.
        """
        with self._verrou:
            self._activations.pop(plugin_id, None)
            self._emplacements.pop(plugin_id, None)
            return self._greffons.pop(plugin_id, None) is not None

    # ------------------------------------------------------------------
    # Activer
    # ------------------------------------------------------------------

    def enable(self, plugin_id: str, enabled_by: str, reason: str) -> PluginManifest:
        """
        Active un greffon. **Décision humaine, tracée.**

        Args:
            plugin_id: Le greffon.
            enabled_by: Qui l'active.
            reason: Pourquoi. Elle sera lue par quelqu'un qui n'était pas là.

        Returns:
            Le manifeste activé.

        Raises:
            PluginRefused: Greffon inconnu, ou décision anonyme ou sans motif.
        """
        if not (enabled_by or "").strip():
            raise PluginRefused(
                "Une activation nomme qui la décide : sans cela, personne ne "
                "sait qui a accordé sa confiance à du code écrit ailleurs."
            )
        if not (reason or "").strip():
            raise PluginRefused(
                "Une activation dit pourquoi : la raison sera lue par "
                "quelqu'un qui n'était pas là quand elle a été prise."
            )

        with self._verrou:
            manifeste = self._exiger(plugin_id)
            manifeste.enabled = True
            self._activations[plugin_id] = {
                "enabled_by": enabled_by.strip(),
                "reason": reason.strip(),
            }
            return manifeste

    def disable(self, plugin_id: str) -> PluginManifest:
        """
        Désactive un greffon.

        **Ne demande aucune raison** : arrêter quelque chose dans l'urgence doit
        être gratuit. C'est allumer qui exige une trace.

        Args:
            plugin_id: Le greffon.

        Returns:
            Le manifeste désactivé.
        """
        with self._verrou:
            manifeste = self._exiger(plugin_id)
            manifeste.enabled = False
            self._activations.pop(plugin_id, None)
            return manifeste

    # ------------------------------------------------------------------
    # Lire
    # ------------------------------------------------------------------

    def _exiger(self, plugin_id: str) -> PluginManifest:
        """Retourne un greffon installé, ou refuse."""
        manifeste = self._greffons.get(plugin_id)
        if manifeste is None:
            raise PluginRefused(f"Greffon « {plugin_id} » inconnu.")
        return manifeste

    def get(self, plugin_id: str) -> Optional[PluginManifest]:
        """Retourne un greffon installé, ou `None`."""
        with self._verrou:
            return self._greffons.get(plugin_id)

    def installed(self) -> List[PluginManifest]:
        """Tous les greffons installés, triés."""
        with self._verrou:
            return [self._greffons[nom] for nom in sorted(self._greffons)]

    def enabled(self) -> List[PluginManifest]:
        """Les greffons activés."""
        return [manifeste for manifeste in self.installed() if manifeste.enabled]

    def activation_of(self, plugin_id: str) -> Optional[Dict[str, str]]:
        """Qui a activé un greffon, et pourquoi."""
        with self._verrou:
            trace = self._activations.get(plugin_id)
            return dict(trace) if trace else None

    def registry_report(self) -> Dict[str, Any]:
        """
        L'état des greffons, et ce que ce registre ne fait pas.

        Returns:
            Les greffons, leurs activations, et les règles tenues.
        """
        installes = self.installed()
        return {
            "installed": len(installes),
            "enabled": len(self.enabled()),
            "plugins": [
                {
                    **manifeste.as_dict(),
                    "activation": self.activation_of(manifeste.plugin_id),
                }
                for manifeste in installes
            ],
            "rules": [
                "Installer inscrit, **désactivé**. Activer est une décision "
                "humaine distincte : sinon copier un fichier vaudrait faire "
                "confiance à son auteur.",
                "Une activation nomme qui la décide et pourquoi ; une "
                "désactivation ne demande rien — arrêter dans l'urgence doit "
                "être gratuit.",
                "Un identifiant appartient à un seul greffon : réinstaller "
                "par-dessus hériterait d'une autorisation sans avoir été jugé.",
            ],
            "does_not": [
                "Charger ou analyser du code : ce registre porte des "
                "déclarations.",
                "Vérifier l'identité d'un auteur.",
            ],
        }


#: Répertoire des greffons installés, relatif à la racine du dépôt.
REPERTOIRE_DES_GREFFONS = "plugins"

#: Nom du manifeste dans le répertoire d'un greffon.
FICHIER_MANIFESTE = "manifest.yaml"


def _racine_depot() -> str:
    """La racine du dépôt."""
    import os

    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def read_plugin_directory(chemin: str) -> Dict[str, Any]:
    """
    Lit le manifeste d'un répertoire de greffon, et **vérifie son point d'entrée**.

    Le défaut que cette fonction referme : jusqu'ici, `entry_point` était
    décoratif. Rien ne vérifiait qu'il existait, et rien n'empêchait un
    manifeste de le faire pointer ailleurs — `../../src/api/server.py` est un
    chemin parfaitement valide dans une chaîne. Un greffon ne peut désigner que
    du code **dans son propre répertoire**.

    Args:
        chemin: Le répertoire du greffon.

    Returns:
        La déclaration lue et le chemin absolu du point d'entrée.

    Raises:
        PluginRefused: Manifeste absent, illisible, ou point d'entrée hors du
            répertoire du greffon.
    """
    import os

    import yaml

    manifeste = os.path.join(chemin, FICHIER_MANIFESTE)
    if not os.path.isfile(manifeste):
        raise PluginRefused(
            f"Aucun « {FICHIER_MANIFESTE} » dans {chemin} : rien ne tourne sans "
            "manifeste, et un répertoire n'en est pas un."
        )

    with open(manifeste, "r", encoding="utf-8") as flux:
        declaration = yaml.safe_load(flux) or {}

    point = str(declaration.get("entry_point", "") or "").strip()
    racine = os.path.realpath(chemin)
    cible = os.path.realpath(os.path.join(racine, point))

    if not point or os.path.isabs(point) or not cible.startswith(racine + os.sep):
        raise PluginRefused(
            f"Point d'entrée « {point or '—'} » hors du répertoire du greffon. "
            "Un greffon ne désigne que du code qui lui appartient : "
            "« ../../src/api/server.py » est une chaîne parfaitement valide, et "
            "c'est exactement pourquoi elle est refusée."
        )
    if not os.path.isfile(cible):
        raise PluginRefused(
            f"Point d'entrée « {point} » introuvable. Un manifeste qui désigne "
            "un fichier absent décrit un greffon qui n'existe pas."
        )

    return {"declaration": declaration, "entry_file": cible, "directory": racine}


def install_from_directory(registry: "PluginRegistry", chemin: str) -> PluginManifest:
    """
    Installe un greffon depuis son répertoire.

    Args:
        registry: Le registre.
        chemin: Le répertoire du greffon.

    Returns:
        Le manifeste validé, désactivé.
    """
    lu = read_plugin_directory(chemin)
    manifeste = registry.install(lu["declaration"])
    registry.bind_directory(manifeste.plugin_id, lu["directory"], lu["entry_file"])
    return manifeste


def discover(registry: "PluginRegistry", racine: Optional[str] = None) -> Dict[str, Any]:
    """
    Installe tous les greffons présents dans le répertoire déclaré.

    Un répertoire qui échoue **n'arrête pas les autres**, et sa raison est
    rendue : un greffon mal écrit ne doit pas empêcher les greffons corrects
    d'exister.

    Args:
        registry: Le registre.
        racine: Le répertoire parcouru.

    Returns:
        Les greffons installés et ceux qui ont été refusés, avec leur raison.
    """
    import os

    dossier = racine or os.path.join(_racine_depot(), REPERTOIRE_DES_GREFFONS)
    if not os.path.isdir(dossier):
        return {"installed": [], "refused": [], "directory": dossier,
                "reason": "Aucun répertoire de greffons."}

    installes, refuses = [], []
    for nom in sorted(os.listdir(dossier)):
        chemin = os.path.join(dossier, nom)
        if not os.path.isdir(chemin):
            continue
        try:
            installes.append(install_from_directory(registry, chemin).plugin_id)
        except (PluginRefused, ValueError) as refus:
            refuses.append({"directory": nom, "reason": str(refus)})
    return {"installed": installes, "refused": refuses, "directory": dossier}
