"""
Liste de contrôle de publication (VOLET_04 ch. 03).

Le chapitre exige cinq choses avant toute publication officielle :
fonctionnalités complètes, défauts critiques résolus, contrôles de sécurité
faits, documentation à jour, cibles de performance vérifiées.

Une liste de contrôle que personne n'exécute est un document. Celle-ci
s'exécute :

    python scripts/release_check.py

Ce qui peut être vérifié par une machine l'est. Ce qui demande un jugement
humain est **affiché comme tel** et n'est jamais coché automatiquement — un
point qui se coche tout seul sans être vérifié est pire que pas de point du
tout.

Code de sortie : 0 si aucun contrôle bloquant n'échoue, 1 sinon.
"""

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, List, Optional

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from src.version import __release_type__, __version__  # noqa: E402

# Niveaux de résultat.
OK = "ok"
ALERTE = "alerte"
ECHEC = "échec"


@dataclass
class Resultat:
    """Issue d'un contrôle."""

    niveau: str
    detail: str


@dataclass
class Controle:
    """Un point de la liste, et la façon de le vérifier."""

    nom: str
    exigence: str  # l'exigence du chapitre 03 à laquelle il répond
    verifier: Callable[[], Resultat]
    bloquant: bool = True


def _git(*arguments: str) -> Optional[str]:
    """Exécute une commande git et retourne sa sortie, ou None si elle échoue."""
    try:
        resultat = subprocess.run(
            ["git", *arguments], cwd=RACINE, capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return resultat.stdout.strip() if resultat.returncode == 0 else None


def _lire(chemin: str) -> str:
    """Retourne le contenu d'un fichier du dépôt, vide s'il est absent."""
    try:
        with open(os.path.join(RACINE, chemin), encoding="utf-8") as fichier:
            return fichier.read()
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Contrôles automatiques
# ---------------------------------------------------------------------------


def controler_version() -> Resultat:
    """La version est unique, bien formée, et cohérente avec son type."""
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", __version__):
        return Resultat(ECHEC, f"Version mal formée : {__version__}")

    trouve = re.search(r"^ARG GALSEN_VERSION=(\S+)", _lire("Dockerfile"), re.MULTILINE)
    if not trouve:
        return Resultat(ECHEC, "Le Dockerfile ne déclare pas ARG GALSEN_VERSION.")
    if trouve.group(1) != __version__:
        return Resultat(
            ECHEC, f"Dockerfile {trouve.group(1)} ≠ src/version.py {__version__}"
        )

    if __release_type__ in ("prototype", "alpha", "beta") and not __version__.startswith("0."):
        return Resultat(
            ECHEC,
            f"{__version__} annoncée « {__release_type__} » : la majeure doit rester 0.",
        )
    return Resultat(OK, f"{__version__} ({__release_type__}), cohérente partout")


def controler_etiquette() -> Resultat:
    """La version à publier ne doit pas déjà exister comme étiquette git."""
    etiquettes = _git("tag", "--list")
    if etiquettes is None:
        return Resultat(ALERTE, "git indisponible : étiquettes non vérifiées")
    existantes = [e for e in etiquettes.splitlines() if e.strip()]
    attendue = f"v{__version__}"
    if attendue in existantes:
        return Resultat(ECHEC, f"L'étiquette {attendue} existe déjà — incrémentez la version.")
    return Resultat(OK, f"{attendue} disponible ({len(existantes)} étiquette(s) existante(s))")


def controler_arbre_propre() -> Resultat:
    """Publier depuis un arbre modifié rend la version irreproductible."""
    etat = _git("status", "--porcelain")
    if etat is None:
        return Resultat(ALERTE, "git indisponible : arbre non vérifié")
    if etat:
        nombre = len(etat.splitlines())
        return Resultat(ECHEC, f"{nombre} fichier(s) non commité(s)")
    return Resultat(OK, "arbre propre")


def controler_secrets() -> Resultat:
    """Aucun secret ni base de données ne doit être suivi par git."""
    suivis = _git("ls-files")
    if suivis is None:
        return Resultat(ALERTE, "git indisponible : fichiers suivis non vérifiés")

    interdits = []
    for chemin in suivis.splitlines():
        nom = os.path.basename(chemin)
        if nom == ".env" or nom.startswith(".env."):
            if nom != ".env.example":
                interdits.append(chemin)
        elif chemin.endswith((".sqlite", ".db", ".pem", ".key")):
            interdits.append(chemin)

    if interdits:
        return Resultat(ECHEC, "suivis par git : " + ", ".join(interdits[:5]))
    return Resultat(OK, "aucun .env, base ou clé suivis")


def controler_changelog() -> Resultat:
    """Le journal doit porter des entrées non publiées à faire remonter."""
    contenu = _lire("docs/changelog/CHANGELOG.md")
    if "## [Unreleased]" not in contenu:
        return Resultat(ECHEC, "CHANGELOG.md n'a pas de section [Unreleased].")

    apres = contenu.split("## [Unreleased]", 1)[1]
    section = apres.split("\n## ", 1)[0]
    entrees = [l for l in section.splitlines() if l.strip().startswith("- ")]
    if not entrees:
        return Resultat(ECHEC, "La section [Unreleased] est vide : rien à publier.")
    return Resultat(OK, f"{len(entrees)} entrée(s) à publier")


def controler_documentation() -> Resultat:
    """Les documents que le chapitre 03 exige à jour doivent exister."""
    requis = [
        "docs/architecture/overview.md",
        "docs/roadmap/roadmap.md",
        "docs/changelog/CHANGELOG.md",
        "docs/memory/session-state.md",
    ]
    manquants = [c for c in requis if not _lire(c).strip()]
    if manquants:
        return Resultat(ECHEC, "absents ou vides : " + ", ".join(manquants))
    return Resultat(OK, f"{len(requis)} documents présents")


def controler_demarrage() -> Resultat:
    """L'application doit démarrer et répondre : le reste en dépend."""
    try:
        from fastapi.testclient import TestClient

        from src.api.server import app

        with TestClient(app) as client:
            reponse = client.get("/health")
    except Exception as erreur:  # une publication ne se décide pas sur une exception
        return Resultat(ECHEC, f"l'application ne démarre pas : {erreur}")

    if reponse.status_code != 200:
        return Resultat(ECHEC, f"/health répond {reponse.status_code}")
    etat = reponse.json().get("status", "inconnu")
    if etat != "healthy":
        return Resultat(ALERTE, f"/health rapporte « {etat} »")
    return Resultat(OK, "/health rapporte healthy")


def controler_suite(ignorer: bool) -> Resultat:
    """La suite complète doit passer — c'est le contrôle des défauts critiques."""
    if ignorer:
        return Resultat(ALERTE, "ignorée par --sans-tests : à lancer avant de publier")
    try:
        resultat = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=RACINE,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except (OSError, subprocess.SubprocessError) as erreur:
        return Resultat(ECHEC, f"pytest n'a pas pu s'exécuter : {erreur}")

    derniere = [l for l in resultat.stdout.strip().splitlines() if l.strip()]
    resume = derniere[-1] if derniere else "sortie vide"
    if resultat.returncode != 0:
        return Resultat(ECHEC, resume)
    return Resultat(OK, resume)


# ---------------------------------------------------------------------------
# Points qui demandent un jugement humain
# ---------------------------------------------------------------------------

CONFIRMATIONS_HUMAINES = [
    (
        "Fonctionnalités complètes",
        "Les fonctionnalités annoncées pour cette version sont livrées, "
        "pas seulement commencées.",
    ),
]


def controler_cibles_performance() -> Resultat:
    """Les cibles de performance existent et sont vérifiées par la suite.

    Ce point est resté longtemps « non tenable » faute de cible : une mesure sans
    seuil n'informe aucune décision. Les cibles sont désormais écrites dans
    `docs/standards/performance.md` et `tests/test_performance_targets.py` les
    vérifie — ce contrôle échoue donc si l'un des deux disparaît, jamais parce
    qu'un humain a oublié de cocher.
    """
    relatifs = ("docs/standards/performance.md", "tests/test_performance_targets.py")
    manquants = [c for c in relatifs if not os.path.exists(os.path.join(RACINE, *c.split("/")))]
    if manquants:
        return Resultat(ECHEC, "absent : " + ", ".join(manquants))

    contenu = _lire(os.path.join(RACINE, "docs", "standards", "performance.md"))
    if "## Targets" not in contenu:
        return Resultat(ECHEC, "docs/standards/performance.md ne déclare aucune cible")
    return Resultat(OK, "cibles déclarées et couvertes par tests/test_performance_targets.py")


def controles(sans_tests: bool) -> List[Controle]:
    """Construit la liste des contrôles automatiques, dans l'ordre de lecture."""
    return [
        Controle("Version", "documentation à jour", controler_version),
        Controle("Étiquette git", "traçabilité", controler_etiquette),
        Controle("Arbre de travail", "reproductibilité", controler_arbre_propre),
        Controle("Secrets", "contrôles de sécurité", controler_secrets),
        Controle("Journal des changements", "notes de version", controler_changelog),
        Controle("Documentation", "documentation à jour", controler_documentation),
        Controle("Démarrage", "défauts critiques", controler_demarrage),
        Controle("Cibles de performance", "cibles de performance vérifiées",
                 controler_cibles_performance),
        Controle("Suite de tests", "défauts critiques", lambda: controler_suite(sans_tests)),
    ]


def main() -> int:
    """Exécute la liste et rapporte ce qui bloque la publication."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument(
        "--sans-tests",
        action="store_true",
        help="ne pas lancer pytest (contrôle rapide ; la suite reste à lancer avant publication)",
    )
    options = analyseur.parse_args()

    print(f"Contrôle de publication — GalSen IA {__version__} ({__release_type__})\n")

    symboles = {OK: "  ok  ", ALERTE: "alerte", ECHEC: " échec"}
    bloquants = []
    for controle in controles(options.sans_tests):
        resultat = controle.verifier()
        print(f"[{symboles[resultat.niveau]}] {controle.nom:24} {resultat.detail}")
        if resultat.niveau == ECHEC and controle.bloquant:
            bloquants.append(controle.nom)

    print("\nÀ confirmer par un humain — jamais coché automatiquement :")
    for titre, explication in CONFIRMATIONS_HUMAINES:
        print(f"  [ ] {titre} — {explication}")

    if bloquants:
        print(f"\nPublication bloquée par : {', '.join(bloquants)}")
        return 1

    print("\nAucun contrôle automatique ne bloque. Les points humains restent à confirmer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
