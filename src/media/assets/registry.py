"""
A registry where nothing enters without a source, and a logo is never redrawn.

Directive §16 opens on a rule that sounds like a style note and is not: *never
recreate recognizable logos using generated graphics when an official asset is
available and legally usable.*

A generated logo is wrong in a way that is hard to see and expensive to fix. It
is nearly right — the proportions drift, the colour is a shade off, the mark is
subtly redrawn — so it passes review, ships, and reaches the one person who
knows that logo by heart. Meanwhile the brand's own file was sitting in the
registry the whole time. So `resolve()` returns the registered asset when one
exists and **refuses generation** when the request names a brand the registry
holds. Not a warning: a refusal, because a warning on a long pipeline is a line
of log nobody reads.

The rest follows §31, which is the rule this repository has applied since the
knowledge engine: nothing enters without a source. An asset carries source,
licence, hash, version and usage restrictions, and one missing any of them is
**incomplete** rather than usable. `UNKNOWN` licensing blocks, exactly as it
does for music in M10 — and for the same reason, which has nothing to do with
software.

Generated assets are registered too, and stay distinguishable forever: an
`AI_GENERATED` origin is not a temporary label to be cleaned up before delivery.
The day someone asks whether a frame contains generated imagery, the answer has
to come from the record rather than from memory.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..core.project import ORIGINE_GENEREE, ORIGINE_INCONNUE, ORIGINE_SOURCEE

#: Les natures d'asset (§16).
NATURES = (
    "logo", "brand_mark", "font", "music", "sfx", "image", "video", "icon",
    "svg", "lut",
)

#: Les natures qu'un modèle ne doit jamais produire quand le registre en tient
#: une. Un logo presque juste passe la relecture et atteint la seule personne
#: qui le connaît par cœur.
NATURES_PROTEGEES = ("logo", "brand_mark")

#: L'état des droits, repris de la discipline musicale du VOLET M10.
DROITS_CONNUS = "CLEARED"
DROITS_INCONNUS = "UNKNOWN"
DROITS_REFUSES = "RESTRICTED"


class AssetRefused(ValueError):
    """Un asset qui ne peut pas être enregistré ou employé tel quel."""


@dataclass(frozen=True)
class Asset:
    """
    Un média enregistré, avec tout ce qui permet de le défendre.

    Attributes:
        asset_id: Son identité.
        kind: Sa nature, parmi `NATURES`.
        path: Où il se trouve.
        origin: `SOURCED`, `AI_GENERATED` ou `UNKNOWN_ORIGIN`.
        source: D'où il vient.
        licence: Sous quelle licence.
        rights: `CLEARED`, `UNKNOWN` ou `RESTRICTED`.
        sha256: L'empreinte du fichier.
        version: Sa version, telle que le fournisseur la nomme.
        restrictions: Ce que la licence interdit.
        brand: La marque à laquelle il appartient, pour un logo.
    """

    asset_id: str
    kind: str
    path: str = ""
    origin: str = ORIGINE_INCONNUE
    source: str = ""
    licence: str = ""
    rights: str = DROITS_INCONNUS
    sha256: str = ""
    version: str = ""
    restrictions: tuple = ()
    brand: str = ""

    def __post_init__(self) -> None:
        if self.kind not in NATURES:
            raise AssetRefused(
                f"Nature « {self.kind} » non déclarée. Déclarées : "
                f"{list(NATURES)}."
            )
        if self.origin not in (ORIGINE_SOURCEE, ORIGINE_GENEREE, ORIGINE_INCONNUE):
            raise AssetRefused(f"Origine « {self.origin} » inconnue.")
        if self.kind in NATURES_PROTEGEES and not str(self.brand or "").strip():
            raise AssetRefused(
                f"Un « {self.kind} » sans marque nommée ne peut pas être "
                "retrouvé quand quelqu'un demandera « le logo de X » — et c'est "
                "précisément la demande qui, sans réponse, fait redessiner un "
                "logo."
            )

    @property
    def usable(self) -> bool:
        """
        Vrai pour un asset dont les droits sont **connus et accordés**.

        Un asset généré est employable sans licence externe : personne d'autre
        n'en détient les droits. Ce qu'il doit garder, c'est son origine.
        """
        if self.origin == ORIGINE_GENEREE:
            return True
        return self.rights == DROITS_CONNUS

    @property
    def missing_fields(self) -> List[str]:
        """
        Ce qui manque pour défendre cet asset.

        Un asset sourcé sans source, licence ou empreinte est **incomplet**,
        jamais « probablement bon ».
        """
        manquants: List[str] = []
        if self.origin == ORIGINE_SOURCEE:
            for champ in ("source", "licence", "sha256"):
                if not str(getattr(self, champ) or "").strip():
                    manquants.append(champ)
        if self.origin == ORIGINE_INCONNUE:
            manquants.append("origin")
        return manquants

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "asset_id": self.asset_id, "kind": self.kind, "path": self.path,
            "origin": self.origin, "source": self.source,
            "licence": self.licence, "rights": self.rights,
            "sha256": self.sha256, "version": self.version,
            "restrictions": list(self.restrictions), "brand": self.brand,
            "usable": self.usable, "missing_fields": self.missing_fields,
        }


def file_hash(path: str) -> str:
    """
    L'empreinte SHA-256 d'un fichier.

    Args:
        path: Le chemin, déjà résolu.

    Returns:
        L'empreinte hexadécimale.

    Raises:
        AssetRefused: Si le fichier est illisible. Enregistrer une empreinte
            vide ferait passer deux fichiers différents pour le même.
    """
    try:
        condense = hashlib.sha256()
        with open(path, "rb") as fichier:
            for bloc in iter(lambda: fichier.read(65536), b""):
                condense.update(bloc)
    except OSError as erreur:
        raise AssetRefused(
            f"Fichier illisible pour empreinte : {erreur}. Enregistrer une "
            "empreinte vide ferait passer deux fichiers différents pour le même."
        ) from erreur
    return condense.hexdigest()


class AssetRegistry:
    """
    Le registre des assets. Aucune suppression n'y est exposée.

    Comme le registre de projets (VOLET M02) : un asset retiré est un asset
    qu'une production passée ne peut plus justifier.
    """

    def __init__(self) -> None:
        self._verrou = threading.RLock()
        self._assets: Dict[str, Asset] = {}

    def register(self, asset: Asset) -> Asset:
        """
        Enregistre un asset.

        Args:
            asset: L'asset.

        Returns:
            L'asset enregistré.

        Raises:
            AssetRefused: Si un asset différent porte déjà cette identité —
                l'écraser ferait changer, sans trace, ce qu'une production
                passée a employé.
        """
        with self._verrou:
            existant = self._assets.get(asset.asset_id)
            if existant is not None and existant != asset:
                raise AssetRefused(
                    f"« {asset.asset_id} » existe déjà avec un contenu "
                    "différent. L'écraser ferait changer sans trace ce qu'une "
                    "production passée a employé."
                )
            self._assets[asset.asset_id] = asset
        return asset

    def get(self, asset_id: str) -> Optional[Asset]:
        """Un asset par son identité."""
        with self._verrou:
            return self._assets.get(asset_id)

    def find_brand(self, brand: str, kind: str = "logo") -> List[Asset]:
        """
        Les assets officiels d'une marque.

        Args:
            brand: La marque, comparée sans casse.
            kind: La nature cherchée.

        Returns:
            Les assets correspondants, triés par identité.
        """
        recherche = str(brand or "").strip().casefold()
        with self._verrou:
            return sorted(
                (a for a in self._assets.values()
                 if a.kind == kind and a.brand.casefold() == recherche),
                key=lambda a: a.asset_id,
            )

    def resolve(self, brand: str, kind: str = "logo") -> Dict[str, Any]:
        """
        Répond à « il me faut le logo de X » — et refuse de le faire dessiner.

        Args:
            brand: La marque demandée.
            kind: La nature demandée.

        Returns:
            L'asset officiel s'il existe, avec `may_generate: False`. Sinon,
            `may_generate` reste **False** pour une nature protégée : le
            registre ne connaît pas ce logo, ce qui veut dire qu'il faut le
            demander à la marque, pas le redessiner. Un logo presque juste passe
            la relecture, est livré, et atteint la seule personne qui le connaît
            par cœur.
        """
        trouves = self.find_brand(brand, kind)
        protegee = kind in NATURES_PROTEGEES

        if trouves:
            employables = [a for a in trouves if a.usable]
            return {
                "found": True,
                "asset": (employables[0] if employables else trouves[0]).as_dict(),
                "usable": bool(employables),
                "may_generate": False,
                "reason": (
                    "Asset officiel enregistré : c'est celui-là qu'il faut "
                    "employer."
                    if employables else
                    "Un asset officiel existe mais ses droits ne le rendent pas "
                    "employable. En générer un à la place ne réglerait pas le "
                    "problème de droits — il en créerait un second."
                ),
            }

        return {
            "found": False,
            "asset": None,
            "usable": False,
            "may_generate": not protegee,
            "reason": (
                f"Aucun « {kind} » enregistré pour « {brand} ». Cette nature "
                "est protégée : il faut demander le fichier à la marque, pas le "
                "redessiner. Un logo presque juste passe la relecture, est "
                "livré, et atteint la seule personne qui le connaît par cœur."
                if protegee else
                f"Aucun « {kind} » enregistré pour « {brand} ». Cette nature "
                "n'est pas protégée : une génération est possible, et devra "
                "porter son origine."
            ),
        }

    def incomplete(self) -> List[Dict[str, Any]]:
        """Les assets dont la provenance ne tient pas."""
        with self._verrou:
            return [
                a.as_dict() for a in sorted(
                    self._assets.values(), key=lambda x: x.asset_id,
                )
                if a.missing_fields or not a.usable
            ]

    def report(self) -> Dict[str, Any]:
        """L'état du registre, sans rien arrondir."""
        with self._verrou:
            assets = list(self._assets.values())
        return {
            "count": len(assets),
            "by_kind": {
                nature: sum(1 for a in assets if a.kind == nature)
                for nature in sorted({a.kind for a in assets})
            },
            "generated": [a.asset_id for a in assets
                          if a.origin == ORIGINE_GENEREE],
            "incomplete": self.incomplete(),
            "note": (
                "Une origine `AI_GENERATED` n'est pas une étiquette provisoire "
                "à nettoyer avant livraison : le jour où quelqu'un demande si "
                "une image a été générée, la réponse doit venir de "
                "l'enregistrement et non d'un souvenir."
            ),
        }


def asset_report() -> Dict[str, Any]:
    """
    Ce que le registre d'assets garantit, et ce qu'il refuse.

    Returns:
        Les natures, les natures protégées, et les règles tenues.
    """
    return {
        "kinds": list(NATURES),
        "protected_kinds": list(NATURES_PROTEGEES),
        "rights_states": [DROITS_CONNUS, DROITS_INCONNUS, DROITS_REFUSES],
        "rules": [
            "Un logo ne se **redessine pas**. Un logo presque juste passe la "
            "relecture, est livré, et atteint la seule personne qui le connaît "
            "par cœur — pendant que le fichier officiel était dans le registre.",
            "Une nature protégée sans asset enregistré rend `may_generate: "
            "False` : il faut demander le fichier à la marque.",
            "Rien n'entre sans source (§31) : un asset sourcé sans source, "
            "licence ou empreinte est **incomplet**, jamais « probablement "
            "bon ».",
            "Une origine `AI_GENERATED` est définitive, pas une étiquette à "
            "nettoyer avant livraison.",
            "Aucune suppression n'est exposée : un asset retiré est un asset "
            "qu'une production passée ne peut plus justifier.",
            "Réenregistrer une identité avec un contenu différent est refusé — "
            "cela changerait sans trace ce qu'une production a employé.",
        ],
        "does_not": [
            "Générer un logo ou une marque.",
            "Employer un asset dont les droits sont inconnus.",
            "Enregistrer un asset sourcé sans provenance complète.",
            "Écraser un asset existant.",
        ],
    }
