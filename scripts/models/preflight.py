#!/usr/bin/env python3
"""
Ce que la plateforme fera de vos modèles — mesuré, pas supposé.

## À quoi ça sert

Vous venez de faire `ollama pull qwen3.5:9b`. Trois questions se posent, et
aucune n'a de réponse évidente :

1. Le serveur répond-il, et **que dit-il** de ce modèle ?
2. Les capacités retenues sont-elles **mesurées** ou seulement déclarées dans
   `config/model_routing.yaml` ?
3. Quel modèle sera réellement choisi pour une conversation, pour du code, pour
   du raisonnement ?

Ce script répond aux trois **en interrogeant le serveur**, jamais en lisant une
intention. Lancez-le après chaque `ollama pull` et après toute modification de
la politique de routage.

    python scripts/models/preflight.py

Il ne modifie rien, n'installe rien, et n'écrit aucun fichier.

## Ce qu'il ne fait pas

Il ne génère pas. Un modèle peut être installé, correctement profilé, bien
routé, et **échouer à répondre** — le vérifier demande une génération, donc du
temps et de la VRAM. `--generer` la déclenche explicitement ; sans ce drapeau,
la sortie ne dit rien de la qualité ni de la latence.
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.model_engine.local_catalogue import DEFAUT, DECLARE, MESURE  # noqa: E402
from src.model_engine.provider_selector import ProviderSelector  # noqa: E402
from src.model_engine.providers.local_provider import LocalProvider  # noqa: E402
from src.model_engine.providers.provider_registry import ProviderRegistry  # noqa: E402

#: Les rôles interrogés, dans l'ordre où ils comptent pour un utilisateur.
ROLES = (
    "conversation", "implementation", "code_generation", "reasoning",
    "planning", "analysis", "research", "document_analysis",
    "summarization", "vision", "translation",
)

#: Une invite courte, pour que `--generer` reste rapide. Elle vérifie qu'un
#: modèle répond, pas qu'il répond bien.
INVITE = "Réponds en une phrase : quelle est la capitale du Sénégal ?"

_SYMBOLE = {MESURE: "mesuré", DECLARE: "déclaré", DEFAUT: "défaut"}


def _fournisseur(url: Optional[str]) -> LocalProvider:
    """Construit le fournisseur local, sur l'URL demandée ou celle par défaut."""
    return LocalProvider(base_url=url) if url else LocalProvider()


def etat_du_serveur(fournisseur: LocalProvider) -> Dict[str, Any]:
    """
    Interroge le serveur et rend son état.

    Returns:
        `{"joignable": bool, "detail": str, "modeles": [...]}`. `modeles` est
        vide quand le serveur ne répond pas — et **non** rempli par le
        catalogue de repli, qui donnerait l'illusion d'une installation.
    """
    info = fournisseur.check_availability()
    joignable = info.status.value == "ready"
    return {
        "joignable": joignable,
        "detail": info.detail or "",
        "modeles": fournisseur.list_models() if joignable else [],
    }


def _ligne_modele(descripteur: Any) -> str:
    """Rend une ligne par modèle, avec l'origine de chaque capacité."""
    origines = descripteur.capability_sources or {}
    atouts = [a for a in descripteur.special_features
              if a not in ("local", "no_cost", "offline")]
    contexte = _SYMBOLE.get(origines.get("context_window"), "défaut")
    vision = _SYMBOLE.get(origines.get("supports_vision"), "non dit")
    return (
        f"  {descripteur.model_name:24s} "
        f"contexte {descripteur.context_window:>7d} ({contexte})  "
        f"vision {str(descripteur.supports_vision):5s} ({vision})  "
        f"outils {str(descripteur.supports_function_calling):5s}\n"
        f"      atouts : {', '.join(atouts) or 'aucun profil déclaré'}"
    )


def routage(fournisseur: LocalProvider) -> List[str]:
    """
    Dit quel modèle chaque rôle atteindra réellement.

    Args:
        fournisseur: Le fournisseur local, déjà sondé.

    Returns:
        Une ligne par rôle.
    """
    registre = ProviderRegistry(register_defaults=False)
    registre.register(fournisseur)
    selecteur = ProviderSelector(provider_registry=registre)

    lignes = []
    for role in ROLES:
        selection = selecteur.select({"task_type": role})
        nom = selection.descriptor.model_name if selection.descriptor else "AUCUN"
        lignes.append(f"  {role:20s} → {nom}")
    return lignes


def generer(fournisseur: LocalProvider, modeles: List[Any]) -> List[str]:
    """
    Demande une phrase à chaque modèle et mesure le temps réel.

    C'est la seule partie de ce script qui prouve qu'un modèle **répond**. Tout
    le reste décrit ce que la plateforme ferait, pas ce qu'elle obtient.

    Args:
        fournisseur: Le fournisseur local.
        modeles: Les descripteurs à interroger.

    Returns:
        Une ligne par modèle, avec la latence ou le motif de l'échec.
    """
    from src.model_engine.providers.base import GenerationRequest

    lignes = []
    for descripteur in modeles:
        depart = time.perf_counter()
        reponse = fournisseur.generate(GenerationRequest(
            prompt=INVITE, model_name=descripteur.model_name, max_tokens=64,
        ))
        duree = time.perf_counter() - depart
        if reponse.succeeded:
            extrait = " ".join((reponse.text or "").split())[:90]
            lignes.append(
                f"  {descripteur.model_name:24s} {duree:6.2f} s  "
                f"{reponse.completion_tokens or '?'} jetons  « {extrait} »"
            )
        else:
            lignes.append(
                f"  {descripteur.model_name:24s} {duree:6.2f} s  ÉCHEC — "
                f"{reponse.detail or 'sans détail'}"
            )
    return lignes


def rapport(url: Optional[str] = None, avec_generation: bool = False) -> str:
    """
    Assemble le rapport complet.

    Args:
        url: URL du serveur Ollama ; celle par défaut sinon.
        avec_generation: Interroger réellement chaque modèle.

    Returns:
        Le rapport, en français, prêt à coller.
    """
    fournisseur = _fournisseur(url)
    etat = etat_du_serveur(fournisseur)

    lignes = ["Préflight modèles — GalSen IA", f"  serveur : {fournisseur.base_url}"]

    if not etat["joignable"]:
        lignes += [
            "  état    : INJOIGNABLE",
            f"  motif   : {etat['detail']}",
            "",
            "Rien n'est mesuré tant qu'aucun serveur ne répond. Les profils de",
            "`config/model_routing.yaml` restent des déclarations, et le routage",
            "ci-dessous ne peut pas être calculé.",
            "",
            "  Démarrez le serveur :  ollama serve",
            "  Puis un modèle      :  ollama pull qwen3.5:9b",
        ]
        return "\n".join(lignes)

    modeles = etat["modeles"]
    lignes += [f"  état    : PRÊT, {len(modeles)} modèle(s) installé(s)", "",
               "Modèles et origine de chaque capacité :"]
    lignes += [_ligne_modele(d) for d in modeles]

    lignes += ["", "Ce que chaque rôle atteindra :"]
    lignes += routage(fournisseur)

    if avec_generation:
        lignes += ["", "Génération réelle (une phrase par modèle) :"]
        lignes += generer(fournisseur, modeles)
    else:
        lignes += ["", "Aucune génération lancée. `--generer` pour l'exiger :",
                   "ce rapport ne dit donc rien de la qualité ni de la latence."]

    return "\n".join(lignes)


def main() -> int:
    """Point d'entrée. Rend 0 si le serveur répond, 1 sinon."""
    analyseur = argparse.ArgumentParser(
        description="Dit ce que GalSen IA fera des modèles locaux installés.",
    )
    analyseur.add_argument("--url", help="URL du serveur Ollama")
    analyseur.add_argument(
        "--generer", action="store_true",
        help="Interroge réellement chaque modèle et mesure la latence",
    )
    arguments = analyseur.parse_args()

    texte = rapport(url=arguments.url, avec_generation=arguments.generer)
    print(texte)
    return 0 if "INJOIGNABLE" not in texte else 1


if __name__ == "__main__":
    raise SystemExit(main())
