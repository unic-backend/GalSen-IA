"""
What an autonomous repair may never touch, and why the list is derived.

A self-healing engine is a program that edits programs. The only reason it is
safe to run is that some files are outside what it can reach — and the value of
that guarantee is exactly the quality of the list. So the list is **derived from
the repository's own architecture**, not written from memory: every entry below
was checked to exist, and `protected_paths()` reports the ones that do not, so a
renamed module is visible instead of silently unprotected.

Four families, and each is protected for a different reason:

- **The frontier itself** (`src/security/`, `src/api/rbac.py`, the approval
  engine, `src/sandbox/`): the code that decides who may do what. A repair that
  edits it is not a repair, it is a change of rules.
- **The harness** (`src/agent/tools/`, `src/agent/policies/`,
  `src/agent/audit/`, `src/agent/self_healer.py`, `guarded_editor.py`): the
  mechanism that controls autonomy. **An autonomous engine that can weaken the
  thing that restrains it has no restraint** — this is rule 18 of the directive,
  and it is the reason this module protects its own file.
- **The tests of both**: deleting the test is the cheapest way to make a broken
  guarantee look intact.
- **Secrets and configuration of trust**: never in reach, whatever is approved.

One escape hatch exists and it is narrow: a repair explicitly classified as
`SECURITY_MAINTENANCE` may touch the frontier — but never the harness. Someone
has to be able to fix a security bug; nobody needs an automaton that rewrites
its own restraints.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from ..tools.workspace import repo_root

#: Réparation ordinaire : la frontière et le harnais sont hors de portée.
REPARATION_ORDINAIRE = "ORDINARY"

#: Maintenance de sécurité : la frontière devient modifiable, **jamais** le
#: harnais. Quelqu'un doit pouvoir corriger un défaut de sécurité ; personne n'a
#: besoin d'un automate qui réécrit ce qui le retient.
MAINTENANCE_SECURITE = "SECURITY_MAINTENANCE"

#: La frontière de sécurité : le code qui décide qui a le droit de quoi.
FRONTIERE = (
    "src/security/",
    "src/api/rbac.py",
    "src/api/rate_limiter.py",
    "src/api/security_headers.py",
    "src/api/threat_detection.py",
    "src/api/trusted_proxies.py",
    "src/approval_engine/",
    "src/sandbox/",
    "src/tool/capabilities.py",
)

#: Le harnais lui-même. Aucune classification ne le rend modifiable.
HARNAIS = (
    "src/agent/policies/",
    "src/agent/tools/",
    "src/agent/audit/",
    "src/agent/self_healer.py",
    "src/agent/guarded_editor.py",
)

#: Les tests qui gardent l'un et l'autre. Supprimer le test est la façon la
#: moins chère de faire passer une garantie cassée pour intacte.
TESTS_PROTEGES = (
    "tests/agent/",
    "tests/test_rbac.py",
    "tests/test_trust.py",
    "tests/test_isolation.py",
    "tests/test_isolation_knowledge.py",
    "tests/test_sandbox.py",
    "tests/test_redaction.py",
    "tests/test_approval_engine.py",
    "tests/test_security_posture.py",
    "tests/test_api_security_headers.py",
    "tests/test_trusted_proxies.py",
    "tests/test_acquisition_trust_boundary.py",
    "tests/test_knowledge_security.py",
    "tests/test_search_security.py",
    "tests/test_gateway_surface.py",
)

#: Ce qui n'est jamais lisible ni modifiable, quelle que soit la classification.
#: `workspace.resolve()` les refuse déjà ; ils sont répétés ici pour que le
#: rapport de politique soit complet sans avoir à lire un autre module.
SECRETS = (".env", ".git/", "config/secrets", "*.key", "*.pem")


class ImmutabilityRefused(PermissionError):
    """Un correctif touche un fichier hors de portée. Levée, jamais avalée."""


def _normaliser(chemin: str) -> str:
    """
    Ramène un chemin à sa forme relative au dépôt, avec des `/`.

    Les préfixes sont retirés **entiers**, jamais caractère par caractère : un
    `lstrip("./")` transformait `.env` en `env`, et un fichier caché cessait
    ainsi d'être reconnu comme un secret. Défaut trouvé en confrontant la
    politique au dépôt réel, pas en la relisant.
    """
    texte = str(chemin or "").strip().replace(os.sep, "/")
    racine = repo_root().replace(os.sep, "/")
    if texte.startswith(racine):
        texte = texte[len(racine):]
    while texte.startswith("/"):
        texte = texte[1:]
    while texte.startswith("./"):
        texte = texte[2:]
    return texte


def _touche(chemin: str, motifs: Tuple[str, ...]) -> Optional[str]:
    """Le motif protégeant ce chemin, ou `None`."""
    relatif = _normaliser(chemin)
    for motif in motifs:
        if motif.endswith("/"):
            if relatif.startswith(motif):
                return motif
        elif relatif == motif:
            return motif
    return None


def classify(path: str) -> Dict[str, Any]:
    """
    Dit ce qu'un fichier est, du point de vue de la politique.

    Args:
        path: Le fichier visé par un correctif.

    Returns:
        Sa famille (`frontier`, `harness`, `protected_test`, `secret`, `open`)
        et le motif qui l'a classé.
    """
    for famille, motifs in (
        ("harness", HARNAIS),
        ("frontier", FRONTIERE),
        ("protected_test", TESTS_PROTEGES),
    ):
        motif = _touche(path, motifs)
        if motif:
            return {"path": _normaliser(path), "family": famille, "pattern": motif}

    relatif = _normaliser(path)
    for secret in SECRETS:
        touche = (
            relatif.endswith(secret.lstrip("*")) if secret.startswith("*")
            else relatif == secret or relatif.startswith(secret)
        )
        if touche:
            return {"path": relatif, "family": "secret", "pattern": secret}
    return {"path": relatif, "family": "open", "pattern": None}


def may_modify(path: str, repair_class: str = REPARATION_ORDINAIRE) -> Tuple[bool, str]:
    """
    Un correctif peut-il toucher ce fichier ?

    Args:
        path: Le fichier.
        repair_class: `ORDINARY` ou `SECURITY_MAINTENANCE`.

    Returns:
        `(autorisé, motif)`. Le motif est vide quand c'est autorisé, et nomme la
        famille sinon : un refus sans cause fait réessayer à l'identique.
    """
    classement = classify(path)
    famille = classement["family"]

    if famille == "open":
        return True, ""

    if famille == "harness":
        return False, (
            f"« {classement['path']} » appartient au harnais d'autonomie "
            f"({classement['pattern']}). Aucune classification ne le rend "
            "modifiable : un moteur qui peut affaiblir ce qui le retient n'est "
            "retenu par rien."
        )

    if famille == "secret":
        return False, (
            f"« {classement['path']} » est un secret ou une configuration de "
            "confiance. Hors de portée quelle que soit l'approbation."
        )

    if repair_class == MAINTENANCE_SECURITE:
        # La seule porte, et elle est étroite : la frontière et ses tests, pour
        # une réparation *classée* comme telle par un humain en amont.
        return True, ""

    return False, (
        f"« {classement['path']} » appartient à la frontière de sécurité "
        f"({classement['pattern']}). Une réparation ordinaire ne la touche pas : "
        "modifier la règle n'est pas réparer le code. Une maintenance de "
        f"sécurité déclarée ({MAINTENANCE_SECURITE}) le peut."
    )


def check_patch_scope(
    paths: List[str], repair_class: str = REPARATION_ORDINAIRE
) -> Dict[str, Any]:
    """
    Juge l'ensemble des fichiers d'un correctif.

    Args:
        paths: Les fichiers que le correctif modifie.
        repair_class: La classification de la réparation.

    Returns:
        Le verdict global et le refus de chaque fichier concerné.

    Raises:
        ImmutabilityRefused: Jamais. Le verdict est **rendu**, pas levé : c'est
            l'appelant qui décide d'arrêter, et un rapport complet vaut mieux
            qu'un arrêt au premier fichier.
    """
    refus = []
    for chemin in paths:
        autorise, motif = may_modify(chemin, repair_class)
        if not autorise:
            refus.append({"path": _normaliser(chemin), "reason": motif})

    return {
        "allowed": not refus,
        "repair_class": repair_class,
        "files": [_normaliser(c) for c in paths],
        "refused": refus,
        "rules": [
            "Le harnais d'autonomie n'est modifiable par aucune "
            "classification : c'est ce qui empêche un moteur d'affaiblir ce qui "
            "le retient.",
            "La frontière de sécurité n'est modifiable que par une maintenance "
            "de sécurité déclarée : modifier la règle n'est pas réparer le code.",
            "Supprimer un test protégé est la façon la moins chère de faire "
            "passer une garantie cassée pour intacte.",
        ],
    }


def protected_paths(root: Optional[str] = None) -> Dict[str, Any]:
    """
    La liste des protections, **confrontée au dépôt réel**.

    Une politique qui nomme des fichiers disparus protège des noms, pas du code.
    Les entrées manquantes sont donc rendues telles quelles : c'est le signal
    qu'un module a été renommé et qu'il n'est peut-être plus couvert.

    Args:
        root: La racine du dépôt.

    Returns:
        Les familles, ce qui existe, et ce qui manque.
    """
    racine = root or repo_root()
    familles = {"frontier": FRONTIERE, "harness": HARNAIS, "protected_tests": TESTS_PROTEGES}

    rapport: Dict[str, Any] = {"root": racine, "families": {}, "missing": []}
    for nom, motifs in familles.items():
        presents, absents = [], []
        for motif in motifs:
            (presents if os.path.exists(os.path.join(racine, motif)) else absents).append(motif)
        rapport["families"][nom] = {"declared": list(motifs), "present": presents}
        rapport["missing"].extend(absents)

    rapport["secrets"] = list(SECRETS)
    rapport["repair_classes"] = [REPARATION_ORDINAIRE, MAINTENANCE_SECURITE]
    rapport["does_not"] = [
        "Rendre le harnais modifiable, sous aucune classification.",
        "Deviner qu'un fichier renommé reste protégé : ce qui manque est nommé.",
    ]
    return rapport
