"""
Ce qu'un fournisseur de recherche déclare, et ce qu'il refuse (R04, STEP 4).

## Pourquoi un quatrième type de déclaration, alors que trois existent

`creative/providers.py`, `model_engine/providers/provider_registry.py` et
`media/providers/base.py` déclarent déjà des fournisseurs. En ajouter un
quatrième demande une justification, parce que le programme précédent a mesuré
ce que coûte de ne pas la demander.

La voici : **un fournisseur de recherche ne produit rien, il rapporte**. Ses
capacités — chercher, récupérer une page, lire un fil Reddit — ne sont pas des
tâches créatives, et les déclarer dans le vocabulaire créatif serait l'erreur de
catégorie que le programme MoneyPrinterTurbo a évitée en refusant de déclarer
`text_to_video` pour un outil qui assemble des rushes.

Ce module **réutilise** donc plutôt que de recopier :

- `LicenceRecord` (`creative/providers.py`) — le droit d'usage et sa preuve ;
- `ProviderPrivacyPolicy` (`creative/canvas/privacy.py`, K07) — où part la
  donnée, et son `UNKNOWN` qui retombe sur `EXTERNAL` ;
- `TrustLevel` (`security/trust.py`) — le contenu récupéré est une **donnée**.

Rien de tout cela n'est réécrit ici.

## Le champ qui ne s'appelle pas `invocation`

ADR-031 a enregistré que `invocation` se lit déjà de deux façons opposées :
« comment le fournisseur est appelé » côté média, « la licence du dépôt est-elle
copyleft » côté créatif, parce que `adapt_declared()` le calcule depuis la
licence. Un troisième sens sur le même mot serait pire que les deux premiers.

Ce module déclare donc `execution`, avec des valeurs qui ne se confondent pas :
`IN_PROCESS`, `SUBPROCESS`, `HOSTED_SERVICE`.

## Ce que les audits ont établi et qui est encodé ici

R01 a mesuré qu'**Agent-Reach n'a pas d'API importable** : sa seule classe
publique porte `doctor()` et `doctor_report()`, et toute la capacité vit dans un
`cli.py` de 87 Ko avec 43 appels à `subprocess`. Il est donc `SUBPROCESS`, et ce
n'est pas un choix d'empaquetage — c'est ce que le dépôt est.

R02 a mesuré que trois des six programmes tiers qu'il orchestre **n'ont aucune
licence**. `LicenceRecord.commercial` reste donc `UNKNOWN` pour lui, et aucun
routage ne peut le sélectionner pour un usage commercial.

## Ce que ce module refuse

**Aucune capacité déclarée n'est disponible tant qu'elle n'a pas été mesurée.**
`health()` interroge l'environnement — le paquet est-il importable, le programme
est-il sur le `PATH`, la variable d'authentification est-elle posée — et rend
`BLOCKED` en nommant chaque condition manquante avec le geste qui la répare.
Aucun fournisseur n'est installé dans ce dépôt, donc **tous rendent `BLOCKED`
aujourd'hui**, et c'est la réponse honnête, pas une panne.

**Aucun classement sur un chiffre absent.** `typical_latency_ms = None` veut dire
« jamais mesuré », jamais « rapide ». C'est la règle que `routing.py` tient déjà.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..creative.canvas.privacy import ProviderPrivacyPolicy, unknown_policy
from ..creative.providers import LicenceRecord

#: Les capacités de recherche déclarables. Le vocabulaire vient des audits
#: R01/R03, pas d'une liste souhaitée : chaque entrée correspond à une capacité
#: qu'au moins un des trois systèmes comparés sait réellement servir.
CAPACITES = (
    "web_search",          # chercher sur le web ouvert
    "page_fetch",          # récupérer et extraire une page
    "reddit_search",       # fils et commentaires Reddit
    "hackernews_search",   # Hacker News
    "github_search",       # issues et pull requests
    "github_read",         # dépôts, fichiers, fils
    "x_search",            # X / Twitter
    "linkedin_search",     # LinkedIn public
    "academic_search",     # arXiv et équivalents
    "wikipedia_search",    # Wikipédia
    "youtube_transcript",  # sous-titres de vidéo
    "rss_read",            # flux RSS / Atom
)

#: Comment le fournisseur s'exécute. **Ce n'est pas `invocation`** : ADR-031 a
#: enregistré que ce mot porte déjà deux sens opposés dans ce dépôt.
DANS_LE_PROCESSUS = "IN_PROCESS"
SOUS_PROCESSUS = "SUBPROCESS"
SERVICE_HEBERGE = "HOSTED_SERVICE"
MODES_D_EXECUTION = (DANS_LE_PROCESSUS, SOUS_PROCESSUS, SERVICE_HEBERGE)

#: L'état d'un fournisseur, mesuré. Trois, et chacun dit autre chose.
DISPONIBLE = "AVAILABLE"
BLOQUE = "BLOCKED"
NON_MESURABLE = "NOT_MEASURABLE"
ETATS = (DISPONIBLE, BLOQUE, NON_MESURABLE)


class ResearchProviderRefused(ValueError):
    """Une déclaration de fournisseur impossible telle quelle."""


@dataclass(frozen=True)
class ResearchProvider:
    """
    Ce qu'un fournisseur de recherche déclare de lui-même.

    Attributes:
        provider_id: Son identifiant.
        version: La version déclarée par le projet, ou `UNKNOWN`. Ce n'est pas
            un SHA : l'API d'arbre de GitHub répond `403` depuis cette session,
            donc aucun commit n'a pu être lu (R01).
        capabilities: Les capacités déclarées, parmi `CAPACITES`.
        supported_sources: Les sources atteintes, en clair.
        authentication: Les **noms** des variables d'environnement requises.
            Jamais les valeurs — un secret n'entre pas dans une déclaration.
        execution: Comment il tourne, parmi `MODES_D_EXECUTION`.
        requires: Ce qu'il faut installer hors Python : programmes, services,
            sessions de navigateur.
        python_module: Le module à importer quand il est `IN_PROCESS`.
        executable: Le programme à trouver sur le `PATH` quand il est
            `SUBPROCESS`.
        licence: Le droit d'usage — `LicenceRecord`, réutilisé.
        privacy: Où part la donnée — `ProviderPrivacyPolicy`, réutilisé.
        rate_limits: Les limites déclarées. `None` = non déclarées, jamais
            « aucune ».
        typical_latency_ms: `None` = **jamais mesuré**, jamais « rapide ».
        limitations: Ce qu'il ne sait pas faire, en clair.
    """

    provider_id: str
    version: str = "UNKNOWN"
    capabilities: Tuple[str, ...] = ()
    supported_sources: Tuple[str, ...] = ()
    authentication: Tuple[str, ...] = ()
    execution: str = DANS_LE_PROCESSUS
    requires: Tuple[str, ...] = ()
    python_module: str = ""
    executable: str = ""
    licence: LicenceRecord = field(default_factory=LicenceRecord)
    privacy: Optional[ProviderPrivacyPolicy] = None
    rate_limits: Optional[Dict[str, Any]] = None
    typical_latency_ms: Optional[float] = None
    limitations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.provider_id).strip():
            raise ResearchProviderRefused(
                "Un fournisseur sans identifiant ne se route pas."
            )
        inconnues = [c for c in self.capabilities if c not in CAPACITES]
        if inconnues:
            raise ResearchProviderRefused(
                f"Capacités non déclarées : {inconnues}. Déclarées : "
                f"{list(CAPACITES)}. Une capacité inventée ici serait routée "
                "vers un fournisseur qui ne sait pas la servir."
            )
        if not self.capabilities:
            raise ResearchProviderRefused(
                f"« {self.provider_id} » ne déclare aucune capacité : rien ne "
                "peut lui être confié."
            )
        if self.execution not in MODES_D_EXECUTION:
            raise ResearchProviderRefused(
                f"Mode d'exécution « {self.execution} » non déclaré. Déclarés : "
                f"{list(MODES_D_EXECUTION)}."
            )
        if self.execution == DANS_LE_PROCESSUS and not self.python_module:
            raise ResearchProviderRefused(
                f"« {self.provider_id} » est `IN_PROCESS` sans module à "
                "importer : sa disponibilité ne pourrait pas être mesurée."
            )
        if self.execution == SOUS_PROCESSUS and not self.executable:
            raise ResearchProviderRefused(
                f"« {self.provider_id} » est `SUBPROCESS` sans exécutable : sa "
                "disponibilité ne pourrait pas être mesurée."
            )
        for nom in self.authentication:
            if "=" in nom or len(nom) > 64:
                raise ResearchProviderRefused(
                    f"« {nom} » ressemble à une valeur, pas à un nom de "
                    "variable. Une déclaration ne porte jamais de secret."
                )
        if self.typical_latency_ms is not None and self.typical_latency_ms < 0:
            raise ResearchProviderRefused(
                f"Latence {self.typical_latency_ms} ms impossible."
            )

    @property
    def trust_level(self) -> Any:
        """
        Le niveau de confiance de ce qui revient de ce fournisseur.

        Il vient de `ProviderPrivacyPolicy.data_destination` (ADR-031,
        décision 3), et une politique absente vaut `UNKNOWN`, donc `EXTERNAL`.
        Le contenu récupéré est de la **donnée**, jamais une instruction
        (STEP 6).
        """
        politique = self.privacy or unknown_policy(self.provider_id)
        return politique.trust_level

    def serves(self, capability: str) -> bool:
        """Dit si ce fournisseur déclare servir une capacité."""
        return capability in self.capabilities

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, sans aucun secret."""
        politique = self.privacy or unknown_policy(self.provider_id)
        return {
            "provider_id": self.provider_id,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "supported_sources": list(self.supported_sources),
            "authentication": list(self.authentication),
            "execution": self.execution,
            "requires": list(self.requires),
            "licence": self.licence.as_dict(),
            "privacy": politique.as_dict(),
            "rate_limits": self.rate_limits,
            "typical_latency_ms": self.typical_latency_ms,
            "limitations": list(self.limitations),
            "trust_level": self.trust_level.value,
        }


def health(provider: ResearchProvider) -> Dict[str, Any]:
    """
    Interroge l'environnement pour savoir si ce fournisseur peut tourner ici.

    Args:
        provider: Le fournisseur déclaré.

    Returns:
        `state`, et `missing` — une liste de conditions absentes, chacune avec
        **le geste qui la répare**. Un état sans geste oblige l'opérateur à
        deviner quoi installer.

    Note:
        La capacité est mesurée en **interrogeant l'environnement**, pas en
        supposant : un module est cherché avec `importlib.util.find_spec`, un
        programme avec `shutil.which`, une variable avec `os.environ`. C'est la
        règle que le moteur média tient déjà — *une capacité se mesure en
        interrogeant l'outil, jamais en vérifiant qu'un binaire existe*.
    """
    manquants: List[Dict[str, str]] = []

    if provider.execution == DANS_LE_PROCESSUS and provider.python_module:
        try:
            present = importlib.util.find_spec(provider.python_module) is not None
        except (ImportError, ValueError):
            present = False
        if not present:
            manquants.append({
                "condition": f"module Python « {provider.python_module} »",
                "repair": f"pip install {provider.provider_id.replace('_', '-')}",
            })

    if provider.execution == SOUS_PROCESSUS and provider.executable:
        if shutil.which(provider.executable) is None:
            manquants.append({
                "condition": f"programme « {provider.executable} » sur le PATH",
                "repair": f"installer {provider.executable}",
            })

    for variable in provider.authentication:
        if not os.environ.get(variable, "").strip():
            manquants.append({
                "condition": f"variable d'environnement « {variable} »",
                "repair": f"poser {variable} dans l'environnement",
            })

    for exigence in provider.requires:
        manquants.append({
            "condition": exigence,
            "repair": "hors de ce dépôt — décision d'un opérateur",
        })

    return {
        "provider_id": provider.provider_id,
        "state": BLOQUE if manquants else DISPONIBLE,
        "missing": manquants,
        "trust_level": provider.trust_level.value,
        "commercially_cleared": provider.licence.usable_commercially,
    }


#: Les trois fournisseurs déclarés, avec ce que les audits ont **lu**.
#:
#: `existing_galsen_research` n'est pas un dépôt tiers : c'est ce que la
#: plateforme sait déjà faire, déclaré au même format pour que le routage n'ait
#: pas deux façons de parler de ses fournisseurs.
FOURNISSEURS: Tuple[ResearchProvider, ...] = (
    ResearchProvider(
        provider_id="existing_galsen_research",
        version="interne",
        capabilities=("web_search", "page_fetch", "github_read"),
        supported_sources=("duckduckgo.com (HTML)", "toute page web",
                           "api.github.com"),
        authentication=(),
        execution=DANS_LE_PROCESSUS,
        python_module="src.tools.web_search.tool",
        licence=LicenceRecord(
            repository="propriétaire — ce dépôt",
            commercial="ALLOWED",
            verified_from="ce dépôt",
        ),
        privacy=ProviderPrivacyPolicy(
            provider_id="existing_galsen_research",
            data_destination="THIRD_PARTY_HOST",
            host="duckduckgo.com",
            evidence="AUTHORITATIVE",
            verified_from="src/tools/web_search/tool.py",
        ),
        limitations=(
            "La recherche web analyse le HTML de DuckDuckGo : une évolution du "
            "balisage se manifeste par « aucun résultat », pas par une erreur.",
            "`tools/browser` n'a aucun contrôle SSRF et déclare un agent qui se "
            "fait passer pour un navigateur (R00).",
        ),
    ),
    ResearchProvider(
        provider_id="web_search_mcp",
        version="0.6.3",
        capabilities=("web_search", "page_fetch", "reddit_search",
                      "hackernews_search", "github_search", "github_read",
                      "x_search", "linkedin_search", "academic_search",
                      "wikipedia_search"),
        supported_sources=("duckduckgo.com", "exa.ai", "reddit.com",
                           "news.ycombinator.com", "github.com", "x.com",
                           "linkedin.com", "arxiv.org", "wikipedia.org"),
        authentication=("EXA_API_KEY", "GITHUB_TOKEN", "XQUIK_API_KEY"),
        execution=DANS_LE_PROCESSUS,
        python_module="web_search_mcp",
        requires=("Node.js 22+ pour le CLI Bird vendorisé, sauf si "
                  "XQUIK_API_KEY est posée",),
        licence=LicenceRecord(
            repository="MIT",
            commercial="UNKNOWN",
            verified_from="https://raw.githubusercontent.com/sydasif/web-search-mcp/main/LICENSE",
            restrictions=(
                "Le dépôt est MIT. Les conditions d'Exa, de Xquik et de "
                "DuckDuckGo n'ont pas été lues, et les droits sur le contenu "
                "récupéré sont propres à chaque source."
            ),
        ),
        privacy=ProviderPrivacyPolicy(
            provider_id="web_search_mcp",
            data_destination="THIRD_PARTY_HOST",
            host="duckduckgo.com, exa.ai, r.jina.ai",
            evidence="DECLARED",
            verified_from="https://raw.githubusercontent.com/sydasif/web-search-mcp/main/README.md",
        ),
        limitations=(
            "Le contrôle SSRF de `fetch_page` ne bloque que les adresses IP "
            "littérales : sa propre docstring dit que les noms de domaine sont "
            "résolus par le système, pas par lui.",
            "S310 — la règle SSRF — est désactivée dans `social/reddit`, "
            "`social/x` et `social/github`, trois modules qui ouvrent des URL.",
            "Un échec de récupération directe bascule sur Exa : l'URL et son "
            "contenu partent alors chez un tiers sans que l'appelant l'ait "
            "demandé.",
        ),
    ),
    ResearchProvider(
        provider_id="agent_reach",
        version="1.5.0",
        capabilities=("web_search", "page_fetch", "youtube_transcript",
                      "rss_read", "github_read", "x_search", "reddit_search",
                      "linkedin_search"),
        supported_sources=("toute page web via r.jina.ai", "youtube.com",
                           "tout flux RSS/Atom", "github.com", "x.com",
                           "reddit.com", "linkedin.com", "bilibili.com",
                           "xiaohongshu.com", "v2ex.com"),
        authentication=(),
        execution=SOUS_PROCESSUS,
        executable="agent-reach",
        requires=(
            "des programmes tiers installés par `npm install -g` (OpenCLI, "
            "mcporter) — trois d'entre eux n'ont aucune licence (R02)",
            "une session Chrome de bureau pour Reddit, Facebook, Instagram et "
            "Xiaohongshu — qu'un serveur ne peut pas réutiliser",
        ),
        licence=LicenceRecord(
            repository="MIT",
            commercial="UNKNOWN",
            verified_from="https://raw.githubusercontent.com/Panniantong/Agent-Reach/main/LICENSE",
            restrictions=(
                "Le dépôt est MIT, mais trois des six programmes qu'il "
                "orchestre — twitter-cli, rdt-cli, bilibili-cli — n'ont aucun "
                "fichier de licence : tous droits réservés par défaut (R02)."
            ),
        ),
        privacy=ProviderPrivacyPolicy(
            provider_id="agent_reach",
            data_destination="THIRD_PARTY_HOST",
            host="r.jina.ai",
            evidence="DECLARED",
            verified_from="https://raw.githubusercontent.com/Panniantong/Agent-Reach/main/README.md",
        ),
        limitations=(
            "Aucune API Python importable : la seule classe publique porte "
            "`doctor()` et `doctor_report()`, et la capacité vit dans un "
            "`cli.py` de 87 Ko avec 43 appels à `subprocess` (R01).",
            "Son propre README conseille un compte jetable, l'accès scripté "
            "risquant la suspension — ce qui heurte la discipline de "
            "`acquisition/fetcher.py`, qui refuse un agent déguisé dans le code.",
            "Ses routages changent : une série de CLI mono-plateforme est "
            "tombée en désuétude ensemble en mars 2026.",
        ),
    ),
)


def declared_providers() -> Tuple[ResearchProvider, ...]:
    """Les fournisseurs déclarés, dans l'ordre de déclaration."""
    return FOURNISSEURS


def provider(provider_id: str) -> ResearchProvider:
    """
    Le fournisseur portant cet identifiant.

    Raises:
        ResearchProviderRefused: S'il n'est pas déclaré.
    """
    for fournisseur in FOURNISSEURS:
        if fournisseur.provider_id == provider_id:
            return fournisseur
    raise ResearchProviderRefused(
        f"Fournisseur « {provider_id} » non déclaré. Déclarés : "
        f"{[f.provider_id for f in FOURNISSEURS]}."
    )


def providers_serving(capability: str) -> List[ResearchProvider]:
    """
    Les fournisseurs déclarant servir une capacité.

    Args:
        capability: La capacité cherchée.

    Returns:
        Les fournisseurs concernés. **Aucun classement** : les latences ne sont
        pas mesurées, et ordonner sur un chiffre absent est ce que `routing.py`
        refuse déjà.

    Raises:
        ResearchProviderRefused: Si la capacité n'est pas déclarée — chercher
            une capacité inventée rendrait une liste vide qui se lirait comme
            « aucun fournisseur ne sait le faire ».
    """
    if capability not in CAPACITES:
        raise ResearchProviderRefused(
            f"Capacité « {capability} » non déclarée. Déclarées : "
            f"{list(CAPACITES)}."
        )
    return [f for f in FOURNISSEURS if f.serves(capability)]


def providers_report() -> Dict[str, Any]:
    """
    Ce que la couche fournisseurs déclare, et ce qu'elle refuse.

    Returns:
        Le vocabulaire, l'état mesuré de chaque fournisseur, et les règles.
    """
    etats = [health(f) for f in FOURNISSEURS]
    return {
        "capabilities": list(CAPACITES),
        "execution_modes": list(MODES_D_EXECUTION),
        "states": list(ETATS),
        "providers": [f.as_dict() for f in FOURNISSEURS],
        "health": etats,
        "available_count": sum(1 for e in etats if e["state"] == DISPONIBLE),
        "blocked_count": sum(1 for e in etats if e["state"] == BLOQUE),
        "commercially_cleared_count": sum(
            1 for f in FOURNISSEURS if f.licence.usable_commercially),
        "reused_types": [
            "creative.providers.LicenceRecord",
            "creative.canvas.privacy.ProviderPrivacyPolicy",
            "security.trust.TrustLevel",
        ],
        "rules": [
            "Le champ s'appelle `execution`, pas `invocation` : ce mot porte "
            "déjà deux sens opposés dans ce dépôt (ADR-031).",
            "Aucune valeur d'authentification n'entre dans une déclaration, "
            "seulement des noms de variables.",
            "`typical_latency_ms = None` veut dire jamais mesuré, jamais rapide.",
            "Aucun classement des fournisseurs : pas de tri sur un chiffre "
            "absent.",
            "La santé est mesurée en interrogeant l'environnement, et un état "
            "bloqué nomme le geste qui le répare.",
            "La confiance vient de la destination des données, pas du type de "
            "fournisseur.",
        ],
    }
