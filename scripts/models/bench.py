#!/usr/bin/env python3
"""
Fait passer le banc GalSen IA à un ou deux modèles, et compare.

    # Un modèle local
    python scripts/models/bench.py --modele qwen3.5:9b

    # La comparaison que la mission demande
    python scripts/models/bench.py --modele qwen3.5:9b --contre qwen2.5:14b

    # Un serveur distant
    python scripts/models/bench.py --serveur http://gpu:8000/v1 --modele Qwen/Qwen3.5-397B-A17B-FP8

Sans modèle joignable, ce script **ne rend aucun chiffre**. Il dit ce qui
manque. C'est la seule sortie honnête quand rien n'a tourné.
"""

import argparse
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.model_engine.benchmark import (  # noqa: E402
    EXECUTE,
    REAL,
    BancRefuse,
    comparer,
    executer,
)
from src.model_engine.providers.local_provider import LocalProvider  # noqa: E402
from src.model_engine.providers.openai_compatible_provider import (  # noqa: E402
    OpenAICompatibleProvider,
)


def _fournisseur(serveur: str) -> Any:
    """Rend le fournisseur visé : distant si une URL est donnée, local sinon."""
    if serveur:
        return OpenAICompatibleProvider(base_url=serveur)
    return LocalProvider()


def _resume(rapport: Any) -> str:
    """Rend un rapport lisible, ou son motif de non-exécution."""
    if rapport.status != EXECUTE:
        return (f"  {rapport.modele:28s} NON EXÉCUTÉ — {rapport.raison}")

    lignes = [
        f"  {rapport.modele:28s} {rapport.reussites}/{len(rapport.resultats)} "
        f"({rapport.taux:.1%})  {rapport.duree_totale_secondes:.1f} s"
        f"  contexte {rapport.fenetre_contexte or '?'}  {rapport.erreurs} erreur(s)"
    ]
    for categorie, detail in sorted(rapport.par_categorie().items()):
        lignes.append(
            f"      {categorie:15s} {detail['reussies']}/{detail['total']}"
        )
    return "\n".join(lignes)


def main() -> int:
    """Point d'entrée. Rend 0 quand au moins un passage a été exécuté."""
    analyseur = argparse.ArgumentParser(description="Banc de modèles GalSen IA.")
    analyseur.add_argument("--modele", required=True, help="Modèle à éprouver")
    analyseur.add_argument("--contre", help="Modèle de comparaison (ligne de base)")
    analyseur.add_argument("--serveur", default="", help="URL .../v1 d'un serveur distant")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON complète")
    analyseur.add_argument("--temperature", type=float, default=0.0)
    arguments = analyseur.parse_args()

    fournisseur = _fournisseur(arguments.serveur)
    backend = "vllm/sglang" if arguments.serveur else "ollama"

    print("Banc de modèles — GalSen IA")
    print(f"  mode     : {REAL}  (aucune simulation dans ce script)")
    print(f"  backend  : {backend}\n")

    principal = executer(
        fournisseur, arguments.modele, mode=REAL,
        temperature=arguments.temperature, backend=backend,
    )
    print(_resume(principal))

    ligne_de_base = None
    if arguments.contre:
        ligne_de_base = executer(
            fournisseur, arguments.contre, mode=REAL,
            temperature=arguments.temperature, backend=backend,
        )
        print(_resume(ligne_de_base))

        try:
            comparaison = comparer(ligne_de_base, principal)
        except BancRefuse as refus:
            print(f"\n  Comparaison refusée : {refus}")
        else:
            print(f"\n  Verdict : {comparaison['verdict']}")
            for categorie, detail in sorted(comparaison["by_category"].items()):
                ecart = detail["delta"]
                marque = "—" if ecart is None else f"{ecart:+.1%}"
                print(f"      {categorie:15s} {marque}")

    if arguments.json:
        charge = {"main": principal.to_dict()}
        if ligne_de_base is not None:
            charge["baseline"] = ligne_de_base.to_dict()
        print("\n" + json.dumps(charge, ensure_ascii=False, indent=2))

    return 0 if principal.status == EXECUTE else 1


if __name__ == "__main__":
    raise SystemExit(main())
