"""
Le pilote d'acquisition : les neuf étapes enchaînées, sous portillon (ADR-021, étape 10).

Deux commandes, et **le portillon est entre les deux**. C'est ce qui fait de ce
script un pilote plutôt qu'un aspirateur.

    python scripts/acquisition_pilot.py plan             # découvre, décide, demande
    python scripts/acquisition_pilot.py run --approval <id>   # récupère, évalue, propose

Entre les deux, une personne approuve — dans l'API d'approbation, pas ici. Ce
script **ne peut pas s'approuver lui-même** : il ne touche jamais au statut d'une
demande, et un test le garde.

## Pourquoi rien n'est conservé entre les deux commandes

`run` refait la découverte au lieu de relire un état sur disque. Ce n'est pas de
la paresse : l'approbation porte l'empreinte du lot exact. Si le site a publié
un document entre les deux commandes, la découverte rend un lot différent,
l'empreinte change, et **l'approbation ne vaut plus** — ce qui est précisément
ce qu'on veut. Un état sur disque aurait fait passer l'ancien lot pour le lot
approuvé pendant que le monde avait bougé.

## Ce que le pilote ne fait jamais

Il n'ingère rien. Il s'arrête sur une **proposition de manifeste** en `DRAFT`,
que quelqu'un relit puis ingère avec `DocumentIngestor`. Aucune connaissance
n'est créée par ce script.

## Aujourd'hui

Aucune source n'est activée dans `corpus/sources/senegal.yaml` : le pilote
s'arrête immédiatement et dit quoi faire. Ce n'est pas une panne — c'est la
règle « inscrire n'est pas activer » qui s'applique.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.acquisition.discovery import discover  # noqa: E402
from src.acquisition.fetcher import fetch, fetch_robots, user_agent  # noqa: E402
from src.acquisition.gate import GateRefused, acquire, plan_batch, submit_batch  # noqa: E402
from src.acquisition.manifest import propose_batch, to_yaml  # noqa: E402
from src.acquisition.parsing import cross_boundary  # noqa: E402
from src.acquisition.quality import evaluate  # noqa: E402
from src.acquisition.record import AcquisitionStatus, acquisition_report  # noqa: E402
from src.approval_engine.approval_manager import ApprovalManagerImpl  # noqa: E402
from src.approval_engine.types import ApprovalRequest  # noqa: E402
from src.knowledge_engine.source_registry import (  # noqa: E402
    acquirable_sources,
    load_registry,
)

#: Plafond du pilote. La conception vise 10 à 30 documents : le pilote prouve
#: qu'un chemin existe, pas qu'il passe à l'échelle.
PLAFOND = 30


class _Portillon:
    """Dépose une demande d'approbation dans le gestionnaire réel."""

    def __init__(self, manager: ApprovalManagerImpl) -> None:
        self.manager = manager

    def submit_approval(self, action: str, description: str, metadata: Dict[str, Any]):
        """Dépose la demande et retourne son identifiant."""
        return self.manager.submit(ApprovalRequest(
            agent_id="acquisition", request_id=None, action=action,
            description=description, metadata=metadata,
        ))


def _source_du_pilote(
    registre: Dict[str, Any], nom: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Retourne la source à parcourir, ou None s'il n'y en a aucune.

    Une source non activée n'est pas une source du pilote : `acquirable_sources`
    exige `enabled: true` **et** un rang acquérable.
    """
    collectables = acquirable_sources(registre=registre)
    if not collectables:
        return None
    if nom:
        return next((e for e in collectables if nom.lower() in e["name"].lower()), None)
    return collectables[0]


def _decouvrir(
    source: Dict[str, Any], limite: int, fetch_fn=fetch, robots: Optional[str] = None
) -> Dict[str, Any]:
    """Découvre des candidats pour une source, `robots.txt` d'abord."""
    if robots is None:
        robots = fetch_robots(source["base_url"] or f"https://{source['domain']}")
    resultat = discover(source, robots_txt=robots, max_links=limite, fetch_fn=fetch_fn)
    resultat["robots_txt"] = robots
    return resultat


def phase_plan(
    registre: Dict[str, Any],
    manager: ApprovalManagerImpl,
    nom: str = "",
    limite: int = PLAFOND,
    fetch_fn=fetch,
    robots: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Découvre, décide, et dépose **une** demande d'approbation. Rien n'est récupéré.

    Returns:
        Le lot proposé et l'identifiant de la demande. Le script s'arrête là :
        approuver est une décision humaine, prise ailleurs.
    """
    source = _source_du_pilote(registre, nom)
    if source is None:
        return {
            "phase": "plan",
            "ready": False,
            "reason": (
                "Aucune source activée. Inscrire une source ne la rend pas "
                "collectable : mettre `enabled: true` et `allowed_content_types` "
                "dans `corpus/sources/senegal.yaml`, après avoir lu les conditions "
                "d'utilisation du site."
            ),
            "registered": len(registre["sources"]),
            "acquirable": 0,
        }

    decouverte = _decouvrir(source, limite, fetch_fn, robots)
    if not decouverte["candidates"]:
        return {
            "phase": "plan",
            "ready": False,
            "source": source["name"],
            "reason": (
                "Aucun candidat découvert. Le site ne publie ni plan de site, ni "
                "fil, ni page d'index déclarée — ou tout a été écarté."
            ),
            "dropped": decouverte["dropped"],
            "modes_without_result": decouverte["modes_without_result"],
        }

    lot = plan_batch(
        [candidat["url"] for candidat in decouverte["candidates"]],
        robots_txt=decouverte["robots_txt"],
        agent=user_agent(),
        registre=registre,
    )
    identifiant = submit_batch(_Portillon(manager), lot)

    return {
        "phase": "plan",
        "ready": True,
        "source": source["name"],
        "approval_id": identifiant,
        "fingerprint": lot.fingerprint,
        "candidates": len(lot.documents),
        "refused_before_fetch": lot.refused,
        "dropped_at_discovery": decouverte["dropped"],
        "by_mode": decouverte["by_mode"],
        "next": (
            "Approuver la demande, puis : "
            f"python scripts/acquisition_pilot.py run --approval {identifiant}"
        ),
        "note": "Rien n'a été récupéré. Aucune requête de document n'est partie.",
    }


def phase_run(
    registre: Dict[str, Any],
    manager: ApprovalManagerImpl,
    approval_id: str,
    nom: str = "",
    limite: int = PLAFOND,
    fetch_fn=fetch,
    robots: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Récupère un lot **approuvé**, le fait franchir la barrière, l'évalue, et propose.

    La découverte est refaite : si le lot a changé depuis l'approbation,
    l'empreinte diffère et `acquire()` refuse — c'est le comportement voulu.
    """
    source = _source_du_pilote(registre, nom)
    if source is None:
        return {"phase": "run", "ready": False, "reason": "Aucune source activée."}

    decouverte = _decouvrir(source, limite, fetch_fn, robots)
    if not decouverte["candidates"]:
        return {"phase": "run", "ready": False, "reason": "Aucun candidat découvert."}

    lot = plan_batch(
        [candidat["url"] for candidat in decouverte["candidates"]],
        robots_txt=decouverte["robots_txt"],
        agent=user_agent(),
        registre=registre,
    )
    lot.approval_id = approval_id

    try:
        recuperation = acquire(
            lot, manager,
            allowed_content_types=source.get("allowed_content_types"),
            robots_txt=decouverte["robots_txt"],
            rate_limit_rps=(source.get("access_policy") or {}).get("rate_limit_rps", 0.2),
            fetch_fn=fetch_fn,
        )
    except GateRefused as refus:
        return {
            "phase": "run",
            "ready": False,
            "reason": str(refus),
            "fingerprint": lot.fingerprint,
        }

    for document in lot.documents:
        contenu = recuperation["contents"].get(document.source_url)
        if contenu is None:
            continue
        cross_boundary(document, contenu["body"], contenu["content_type"])
        if document.status is AcquisitionStatus.PARSED:
            evaluate(
                document,
                _texte(contenu),
                declared_subjects=source.get("subjects"),
                tier_defaulted=source.get("tier_defaulted", False),
            )

    proposition = propose_batch(lot.documents, registre=registre)
    return {
        "phase": "run",
        "ready": True,
        "source": source["name"],
        "approval_id": approval_id,
        "fetched": recuperation["fetched"],
        "failed": recuperation["failed"],
        "documents": acquisition_report(lot.documents),
        "manifest": proposition,
        "manifest_yaml": to_yaml(proposition["entries"]) if proposition["entries"] else "",
        "ingested": 0,
        "note": (
            "Aucune connaissance n'a été créée. La proposition est en DRAFT : la "
            "relire, la compléter, puis l'ingérer avec `DocumentIngestor`."
        ),
    }


def _texte(contenu: Dict[str, Any]) -> str:
    """Retourne le texte extrait d'un contenu récupéré."""
    from src.acquisition.parsing import extract_text

    return extract_text(contenu["body"], contenu["content_type"])["text"]


def _afficher(rapport: Dict[str, Any]) -> None:
    """Affiche le rapport sous une forme lisible, sans masquer les refus."""
    if not rapport.get("ready"):
        print(f"[arrêt] {rapport.get('reason', 'raison non dite')}")
        return

    if rapport["phase"] == "plan":
        print(f"Source        : {rapport['source']}")
        print(f"Candidats     : {rapport['candidates']}")
        print(f"Écartés       : {len(rapport['dropped_at_discovery'])} à la découverte, "
              f"{len(rapport['refused_before_fetch'])} à la décision")
        print(f"Approbation   : {rapport['approval_id']}")
        print(f"\n{rapport['next']}")
        return

    documents = rapport["documents"]
    print(f"Source        : {rapport['source']}")
    print(f"Récupérés     : {rapport['fetched']}")
    for statut, compte in sorted(documents["by_status"].items()):
        if compte:
            print(f"  {statut:<12} : {compte}")
    for refus in documents["rejected"]:
        print(f"  [refusé]     {refus['source_url']} — {refus['reason']}")
    for quarantaine in documents["quarantined"]:
        print(f"  [quarantaine] {quarantaine['source_url']} — {quarantaine['reason']}")
    print(f"\nManifeste proposé : {rapport['manifest']['proposed']} entrée(s), "
          f"ingérées : {rapport['ingested']}")


def main(argv: Optional[List[str]] = None) -> int:
    """Exécute une phase du pilote et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("phase", choices=["plan", "run"])
    analyseur.add_argument("--approval", default="", help="Identifiant de la demande approuvée.")
    analyseur.add_argument("--source", default="", help="Nom (partiel) de la source à parcourir.")
    analyseur.add_argument("--registry", default=None, help="Registre à charger.")
    analyseur.add_argument("--limit", type=int, default=PLAFOND, help="Plafond de documents.")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    arguments = analyseur.parse_args(argv)

    registre = load_registry(arguments.registry)
    manager = ApprovalManagerImpl()

    if arguments.phase == "plan":
        rapport = phase_plan(registre, manager, arguments.source, arguments.limit)
    else:
        if not arguments.approval:
            print("[arrêt] `run` demande --approval <id>. Le pilote ne s'approuve pas lui-même.")
            return 2
        rapport = phase_run(
            registre, manager, arguments.approval, arguments.source, arguments.limit
        )

    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2, default=str))
    else:
        _afficher(rapport)
    return 0 if rapport.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
