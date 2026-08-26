#!/usr/bin/env python3
"""
Raccorde un serveur d'inférence distant à GalSen IA, et le prouve.

## Ce que ça vérifie, dans l'ordre

1. **Le serveur répond** — sur `/v1/models`, pas sur `/health`.
2. **La plateforme le voit** — le fournisseur compatible OpenAI l'annonce.
3. **Le routage l'utilise** — quel rôle atteindra quel modèle distant.
4. **Il génère** — seulement avec `--generer`, parce que c'est la seule étape
   qui coûte du temps GPU.

    export GALSEN_OPENAI_COMPATIBLE_URL=http://serveur:8000/v1
    python scripts/models/connect.py --generer

## Pourquoi `/v1/models` et pas `/health`

vLLM expose un point de santé, mais **son chemin n'a pas pu être vérifié** ici :
`docs.vllm.ai` est refusé par le mandataire de cet environnement. Bâtir un
contrôle de santé sur un chemin supposé, c'est fabriquer un test qui échoue le
jour où le chemin diffère — et faire croire à une panne du serveur.

`/v1/models` fait partie du contrat OpenAI que vLLM, SGLang et tout serveur
compatible servent par construction. C'est aussi celui que
`OpenAICompatibleProvider` interroge déjà : le vérifier ici vérifie donc **le
chemin réel de la plateforme**, pas un chemin parallèle.
"""

import argparse
import os
import sys
import time
from typing import List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.model_engine.provider_selector import ProviderSelector  # noqa: E402
from src.model_engine.providers.openai_compatible_provider import (  # noqa: E402
    OpenAICompatibleProvider,
)
from src.model_engine.providers.provider_registry import ProviderRegistry  # noqa: E402

#: Les rôles interrogés. Mêmes que le préflight local : comparer un serveur
#: distant à une machine locale demande la même question des deux côtés.
ROLES = (
    "conversation", "code_generation", "reasoning", "planning",
    "analysis", "document_analysis", "summarization", "vision",
)

INVITE = "Réponds en une phrase : quelle est la capitale du Sénégal ?"


def rapport(url: Optional[str] = None, avec_generation: bool = False) -> str:
    """
    Assemble le rapport de raccordement.

    Args:
        url: Racine de l'API, `.../v1`. Lue dans l'environnement sinon.
        avec_generation: Demander réellement une phrase au serveur.

    Returns:
        Le rapport, prêt à coller.
    """
    fournisseur = OpenAICompatibleProvider(base_url=url) if url else OpenAICompatibleProvider()
    lignes = ["Raccordement d'un serveur d'inférence — GalSen IA",
              f"  URL : {fournisseur._base_url or '(non renseignée)'}"]

    if not fournisseur._base_url:
        lignes += [
            "  état : NON CONFIGURÉ",
            "",
            "  Renseignez l'URL du serveur, puis relancez :",
            "    export GALSEN_OPENAI_COMPATIBLE_URL=http://serveur:8000/v1",
        ]
        return "\n".join(lignes)

    info = fournisseur.check_availability()
    if info.status.value != "ready":
        lignes += [
            "  état : INJOIGNABLE",
            f"  motif: {info.detail or 'sans détail'}",
            "",
            "  Rien n'est raccordé. Vérifiez que le serveur tourne :",
            "    python scripts/models/serve_large.py <modele> --execute",
        ]
        return "\n".join(lignes)

    modeles = fournisseur.list_models()
    lignes += [f"  état : PRÊT, {len(modeles)} modèle(s) annoncé(s)", "",
               "Modèles servis :"]
    for descripteur in modeles:
        lignes.append(
            f"  {descripteur.model_name:34s} contexte {descripteur.context_window}"
        )

    registre = ProviderRegistry(register_defaults=False)
    registre.register(fournisseur)
    selecteur = ProviderSelector(provider_registry=registre)

    lignes += ["", "Ce que chaque rôle atteindra sur ce serveur :"]
    for role in ROLES:
        selection = selecteur.select({"task_type": role})
        nom = selection.descriptor.model_name if selection.descriptor else "AUCUN"
        lignes.append(f"  {role:20s} → {nom}")

    if avec_generation:
        lignes += ["", "Génération réelle :"]
        lignes += _generer(fournisseur, modeles)
    else:
        lignes += ["", "Aucune génération lancée. `--generer` pour l'exiger :",
                   "ce rapport ne dit donc rien de la qualité ni de la latence."]

    lignes += [
        "",
        "Rappel — ADR-014 : un GPU loué est un exécutant tiers. Le raccorder ne",
        "l'autorise pas ; `src/model_engine/providers/derogations.py` décide.",
    ]
    return "\n".join(lignes)


def _generer(fournisseur: OpenAICompatibleProvider, modeles: List) -> List[str]:
    """Interroge chaque modèle annoncé et mesure le temps réel."""
    from src.model_engine.providers.base import GenerationRequest

    lignes = []
    for descripteur in modeles:
        depart = time.perf_counter()
        reponse = fournisseur.generate(GenerationRequest(
            prompt=INVITE, model_name=descripteur.model_name, max_tokens=64,
        ))
        duree = time.perf_counter() - depart
        if reponse.succeeded:
            extrait = " ".join((reponse.text or "").split())[:80]
            lignes.append(f"  {descripteur.model_name:34s} {duree:6.2f} s  « {extrait} »")
        else:
            lignes.append(
                f"  {descripteur.model_name:34s} {duree:6.2f} s  ÉCHEC — "
                f"{reponse.detail or 'sans détail'}"
            )
    return lignes


def main() -> int:
    """Point d'entrée. Rend 0 si le serveur est raccordé."""
    analyseur = argparse.ArgumentParser(
        description="Vérifie qu'un serveur compatible OpenAI est utilisable par la plateforme.",
    )
    analyseur.add_argument("--url", help="Racine de l'API, .../v1")
    analyseur.add_argument(
        "--generer", action="store_true", help="Demande réellement une réponse",
    )
    arguments = analyseur.parse_args()

    texte = rapport(url=arguments.url, avec_generation=arguments.generer)
    print(texte)
    return 0 if "état : PRÊT" in texte else 1


if __name__ == "__main__":
    raise SystemExit(main())
