"""
Activation des sources sénégalaises : mesurer les conditions, puis décider.

    python scripts/activate_senegal_sources.py            # mesure et rapporte
    python scripts/activate_senegal_sources.py --json      # rapport brut

## Ce que « activer une source » veut dire ici

Le registre (`corpus/sources/senegal.yaml`, ADR-021) refuse toute collecte tant
qu'une source n'est pas `enabled: true`, et l'activer demande de savoir **ce que
le site autorise**. Ce script établit cela de la seule façon licite : il lit le
`robots.txt` que le site publie précisément pour ça, et rapporte ce qu'il y
trouve. Il ne contourne rien et n'active rien de lui-même — il **mesure**, et
l'écriture dans le registre reste une modification relue.

## Ce qu'il ne peut pas faire, et pourquoi

Dans cet environnement, la politique réseau refuse la connexion à presque tout :
les neuf domaines sénégalais inscrits répondent `Tunnel connection failed: 403`
avant même qu'une requête HTTP parte. Ce n'est **pas** un refus des sites ; c'est
le mandataire de l'environnement. Un blocage d'environnement et un refus de site
demandent deux actions opposées — changer de machine, ou changer de source — et
les confondre ferait chercher au mauvais endroit.

Le blocage est donc **mesuré et nommé**, jamais contourné.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.acquisition.fetcher import FetchRefused, fetch_robots, user_agent  # noqa: E402
from src.knowledge_engine.collection import robots_disallows  # noqa: E402
from src.knowledge_engine.source_registry import load_registry  # noqa: E402

#: Verdicts possibles pour l'accessibilité d'une source.
JOIGNABLE = "reachable"
BLOQUE_ENVIRONNEMENT = "blocked_by_environment"
REFUSE_PAR_LE_SITE = "refused_by_site"
INCONNU = "UNKNOWN"

#: Signature du refus du mandataire. Le reconnaître permet de ne pas l'imputer
#: au site d'en face, ce qui serait une accusation fausse et coûteuse.
SIGNATURE_MANDATAIRE = ("tunnel connection failed", "connect_rejected", "403 forbidden")


def _maintenant() -> str:
    """Retourne l'instant courant en ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def probe(base_url: str, chemin_test: str = "/publications/document.pdf") -> Dict[str, Any]:
    """
    Mesure ce qu'un site autorise, en lisant son `robots.txt`.

    Args:
        base_url: L'adresse de base de la source.
        chemin_test: Un chemin représentatif, pour savoir si la collecte y est permise.

    Returns:
        L'état d'accessibilité, le contenu de `robots.txt`, et le verdict pour le
        chemin testé. **Aucune conclusion n'est tirée d'un échec réseau** : un
        site injoignable n'est pas un site qui refuse.
    """
    resultat = {
        "base_url": base_url,
        "agent": user_agent(),
        "measured_at": _maintenant(),
        "robots_txt": INCONNU,
        "robots_present": INCONNU,
        "path_allowed": INCONNU,
        "terms_reviewed": INCONNU,
    }
    try:
        contenu = fetch_robots(base_url)
    except (FetchRefused, OSError) as erreur:
        message = f"{type(erreur).__name__}: {erreur}"
        environnement = any(
            signature in message.lower() for signature in SIGNATURE_MANDATAIRE
        )
        resultat.update({
            "state": BLOQUE_ENVIRONNEMENT if environnement else INCONNU,
            "error": message,
            "note": (
                "Refus du mandataire de l'environnement, pas du site : la "
                "connexion n'a jamais atteint l'hôte. Changer de machine, pas de "
                "source."
                if environnement else
                "Échec réseau non attribué : ni le site ni l'environnement ne "
                "peuvent en être tenus responsables sans mesure supplémentaire."
            ),
        })
        return resultat

    interdit = robots_disallows(contenu, base_url.rstrip("/") + chemin_test, agent=user_agent())
    resultat.update({
        "state": REFUSE_PAR_LE_SITE if interdit else JOIGNABLE,
        "robots_txt": contenu[:2000],
        "robots_present": bool(contenu.strip()),
        "path_allowed": not interdit,
        "disallowed_by": interdit or "",
        "note": (
            "Le site publie un robots.txt et il interdit ce chemin."
            if interdit else
            "Le site ne s'oppose pas à la collecte de ce chemin. Les conditions "
            "d'utilisation restent à lire par une personne : robots.txt dit ce "
            "qu'un agent peut atteindre, pas ce qu'on a le droit d'en faire."
        ),
    })
    return resultat


def probe_registry(registre: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Mesure toutes les sources sénégalaises inscrites, une par une.

    Returns:
        Un verdict par source, et le compte par état. Une source injoignable
        reste `enabled: false` : activer ce qu'on n'a pas pu mesurer reviendrait
        à décider sans information.
    """
    registre = registre or load_registry()
    senegalaises = [e for e in registre["sources"] if e["scope"] == "country:sn"]

    verdicts = []
    for entree in senegalaises:
        mesure = probe(entree["base_url"] or f"https://{entree['domain']}")
        verdicts.append({
            "name": entree["name"],
            "domain": entree["domain"],
            "tier": entree["tier"].value,
            "enabled": entree["enabled"],
            **mesure,
        })

    par_etat: Dict[str, int] = {}
    for verdict in verdicts:
        par_etat[verdict["state"]] = par_etat.get(verdict["state"], 0) + 1

    return {
        "measured": len(verdicts),
        "by_state": par_etat,
        "sources": verdicts,
        "activatable": [
            v["name"] for v in verdicts
            if v["state"] == JOIGNABLE and v["path_allowed"] is True
        ],
        "blocked_by_environment": [
            v["name"] for v in verdicts if v["state"] == BLOQUE_ENVIRONNEMENT
        ],
        "note": (
            "Mesure, pas décision. Écrire `enabled: true` dans "
            "`corpus/sources/senegal.yaml` reste une modification relue, et elle "
            "demande aussi d'avoir lu les conditions d'utilisation du site — ce "
            "qu'aucun programme ne peut faire honnêtement."
        ),
    }


def environment_report() -> Dict[str, Any]:
    """
    Décrit la politique réseau de l'environnement, telle qu'elle se mesure.

    Un blocage d'environnement rapporté comme un refus de site enverrait chercher
    une autre source alors qu'il faut changer de machine.
    """
    verdicts = probe_registry()
    bloquees = verdicts["blocked_by_environment"]
    return {
        "senegalese_sources": verdicts["measured"],
        "reachable": len(verdicts["activatable"]),
        "blocked_by_environment": len(bloquees),
        "blocker": (
            "Le mandataire de cet environnement refuse la connexion (CONNECT → "
            "403) à tous les hôtes hors de sa liste d'autorisation. Les domaines "
            "institutionnels sénégalais en font partie. Vérifiable par "
            "`curl -sS \"$HTTPS_PROXY/__agentproxy/status\"`, section "
            "`recentRelayFailures`."
            if bloquees else ""
        ),
        "what_would_settle_it": [
            "Exécuter ce script depuis une machine sans cette politique réseau",
            "Ou autoriser ces hôtes dans la politique de l'environnement",
        ] if bloquees else [],
        "not_a_site_refusal": bool(bloquees),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Mesure les sources inscrites et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    arguments = analyseur.parse_args(argv)

    rapport = probe_registry()
    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        return 0 if rapport["activatable"] else 1

    print(f"Agent déclaré : {user_agent()}")
    print(f"Sources mesurées : {rapport['measured']}")
    for verdict in rapport["sources"]:
        etat = verdict["state"]
        detail = verdict.get("error") or verdict.get("note", "")
        print(f"  {verdict['domain']:28} {etat:22} {detail[:70]}")
    print(f"\nActivables : {len(rapport['activatable'])}")
    print(f"Bloquées par l'environnement : {len(rapport['blocked_by_environment'])}")
    if rapport["blocked_by_environment"]:
        print("\n" + environment_report()["blocker"])
    return 0 if rapport["activatable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
