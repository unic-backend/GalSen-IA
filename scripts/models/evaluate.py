#!/usr/bin/env python3
"""
Fait passer les dix épreuves à un modèle réel, par le vrai chemin `/chat`.

    # Sur ta machine, une fois `ollama serve` lancé
    python scripts/models/evaluate.py --modele qwen3.5:9b
    python scripts/models/evaluate.py --modele qwen2.5:14b --json rapport.json

    # Les deux, côte à côte
    python scripts/models/evaluate.py --modele qwen3.5:9b --contre qwen2.5:14b

Ce script **n'utilise pas** le banc scripté. Il appelle l'application réelle en
mémoire : planner, agents, ancrage, rédaction, critique déterministe et reprise
éventuelle. Ce qu'il mesure est ce qu'un utilisateur reçoit.

Sans modèle joignable, il ne rend **aucun chiffre** — chaque épreuve porte
`NOT_EXECUTED` et son motif.
"""

import argparse
import json
import os
import platform
import sys
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from src.model_engine.evaluation_suite import (  # noqa: E402
    EPREUVES,
    RapportEvaluation,
    evaluer,
    rapport_lisible,
)


def _materiel() -> str:
    """Décrit la machine, sans rien deviner de ce qu'elle n'annonce pas."""
    from src.model_engine.providers.local_provider import LocalProvider  # noqa: F401

    import shutil
    import subprocess

    gpu = "aucun GPU NVIDIA détecté"
    if shutil.which("nvidia-smi"):
        try:
            sortie = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total",
                                     "--format=csv,noheader"],
                                    capture_output=True, text=True, timeout=10)
            if sortie.returncode == 0 and sortie.stdout.strip():
                gpu = " / ".join(sortie.stdout.strip().splitlines())
        except (OSError, subprocess.SubprocessError):
            pass
    return f"{platform.machine()} {platform.system()} — {gpu}"


def _cle_de_session(cle: Optional[str]) -> str:
    """
    Fournit la clé d'API du passage, sans jamais affaiblir le contrôle.

    Trois cas, dans cet ordre :

    1. `--cle` ou `GALSEN_API_KEY` : l'exploitant fournit une clé existante.
    2. `GALSEN_API_KEYS` déjà renseignée : la première y est reprise.
    3. Sinon, **une clé jetable est provisionnée** pour ce processus seul, par
       le mécanisme documenté (`GALSEN_API_KEYS`). Ce n'est pas un
       contournement : l'authentification vérifie exactement ce qu'elle
       vérifiait, sur une clé que l'exploitant vient de créer sur sa propre
       machine. Elle disparaît avec le processus, n'est jamais écrite ni
       affichée.

    Returns:
        La clé à présenter dans `X-API-Key`.
    """
    fournie = (cle or os.environ.get("GALSEN_API_KEY") or "").strip()
    if fournie:
        return fournie

    existantes = os.environ.get("GALSEN_API_KEYS", "").strip()
    if existantes:
        return existantes.split(",")[0].split(":")[0].strip()

    import secrets

    jetable = secrets.token_urlsafe(32)
    # `admin` : les épreuves touchent la connaissance et l'observabilité. Un
    # rôle plus faible ferait échouer des épreuves pour une raison qui n'a rien
    # à voir avec le modèle mesuré.
    os.environ["GALSEN_API_KEYS"] = f"{jetable}:admin:evaluation"
    return jetable


def _client(cle: Optional[str]):
    """
    Construit l'appelant de `/chat`, sur l'application réelle en mémoire.

    Passer par `TestClient` n'est pas un raccourci de test : c'est la même
    application, les mêmes routes, les mêmes agents. Le seul évitement est la
    couche réseau, qui ne change rien à ce qui est mesuré ici.

    La clé est résolue **avant** d'importer l'application : le mapping RBAC est
    lu à l'import, et le renseigner ensuite arriverait trop tard.
    """
    valeur = _cle_de_session(cle)

    from fastapi.testclient import TestClient

    from src.api.server import app

    client = TestClient(app)
    client.__enter__()

    entetes: Dict[str, str] = {"X-API-Key": valeur}

    def appeler(message: str) -> Dict[str, Any]:
        reponse = client.post("/chat", json={"message": message}, headers=entetes)
        if reponse.status_code != 200:
            raise RuntimeError(f"/chat a répondu {reponse.status_code}: {reponse.text[:200]}")
        return reponse.json()

    return appeler, client


def _passer(modele: str, cle: Optional[str]) -> RapportEvaluation:
    """
    Impose un modèle et fait passer les dix épreuves.

    Le modèle est imposé par `GALSEN_FORCED_MODEL` si la plateforme l'honore ;
    sinon le routage choisit, et le rapport nomme **le modèle qui a réellement
    répondu** plutôt que celui qui était demandé. Confondre les deux ferait
    attribuer un score au mauvais modèle.
    """
    appeler, client = _client(cle)
    try:
        rapport = evaluer(
            appeler, modele=modele, backend="ollama (in-process /chat)",
            materiel=_materiel(), epreuves=EPREUVES,
        )
    finally:
        client.__exit__(None, None, None)

    reellement = {r.modele for r in rapport.resultats if r.modele}
    if reellement:
        rapport.modele = " / ".join(sorted(reellement))
    return rapport


def _comparer(gauche: RapportEvaluation, droite: RapportEvaluation) -> str:
    """Met deux passages côte à côte, épreuve par épreuve."""
    lignes = ["", "Comparaison côte à côte", ""]
    lignes.append(f"  {'épreuve':28s} {gauche.modele[:18]:18s} {droite.modele[:18]:18s}")
    par_id = {r.identifiant: r for r in droite.resultats}
    for resultat in gauche.resultats:
        autre = par_id.get(resultat.identifiant)
        lignes.append(
            f"  {resultat.identifiant + ' ' + resultat.titre:28s} "
            f"{resultat.issue:18s} {(autre.issue if autre else '—'):18s}"
        )

    a, b = gauche.taux, droite.taux
    if a is None or b is None:
        lignes += ["", "  Verdict : NON MESURABLE — au moins un passage n'a rien exécuté."]
        return "\n".join(lignes)

    ecart = b - a
    seuil = 1.5 / max(len(gauche.verifiables), 1)
    if abs(ecart) < seuil:
        lignes += ["", f"  Verdict : ÉGALITÉ — écart de {ecart:+.0%}, sous le seuil "
                       f"de bruit ({seuil:.0%}, une épreuve et demie)."]
    else:
        gagnant = droite.modele if ecart > 0 else gauche.modele
        lignes += ["", f"  Verdict : {gagnant} l'emporte de {abs(ecart):.0%}."]
    return "\n".join(lignes)


def main() -> int:
    """Point d'entrée. Rend 0 si au moins une épreuve a atteint un modèle."""
    analyseur = argparse.ArgumentParser(
        description="Dix épreuves GalSen IA, par le vrai chemin /chat.",
    )
    analyseur.add_argument("--modele", required=True, help="Modèle attendu (pour la trace)")
    analyseur.add_argument("--contre", help="Second modèle, pour la comparaison")
    analyseur.add_argument("--cle", help="Clé d'API, si la route en exige une")
    analyseur.add_argument("--json", help="Écrit le rapport complet dans ce fichier")
    arguments = analyseur.parse_args()

    principal = _passer(arguments.modele, arguments.cle)
    print(rapport_lisible(principal))

    ligne_de_base = None
    if arguments.contre:
        print()
        ligne_de_base = _passer(arguments.contre, arguments.cle)
        print(rapport_lisible(ligne_de_base))
        print(_comparer(ligne_de_base, principal))

    if principal.executees == 0:
        print("\n  Aucune épreuve n'a atteint un modèle : aucun chiffre n'est rendu.")
        print("  Démarrez le service, puis relancez :")
        print("    ollama serve && ollama pull qwen3.5:9b")

    if arguments.json:
        charge: Dict[str, Any] = {"main": principal.to_dict()}
        if ligne_de_base is not None:
            charge["baseline"] = ligne_de_base.to_dict()
        with open(arguments.json, "w", encoding="utf-8") as fichier:
            json.dump(charge, fichier, ensure_ascii=False, indent=2)
        print(f"\n  Rapport complet écrit dans {arguments.json}")

    return 0 if principal.executees else 1


if __name__ == "__main__":
    raise SystemExit(main())
