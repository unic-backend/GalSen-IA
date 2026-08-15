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
