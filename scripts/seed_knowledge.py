#!/usr/bin/env python3
"""
Remplit la base de connaissances (VOLET 28, ch. 02).

La base contient **0 élément**. Le moteur de connaissances, l'outil RAG, le
service de recherche et le classement — environ 7 000 lignes — travaillent tous
sur rien.

Ce script verse ce qui peut l'être **sans rien inventer**, et c'est le point le
plus important de ce fichier.

## Ce qui est versé par défaut, et pourquoi

La documentation du projet lui-même : ADR, architecture, déploiement, feuille de
route. Ces textes existent, ils sont dans le dépôt, ils sont vérifiables ligne à
ligne, et leur ingestion rend un service immédiat — la plateforme devient capable
de répondre sur sa propre architecture, ce qu'aucun modèle généraliste ne sait
faire.

## Ce qui n'est **pas** versé, et pourquoi

Aucune connaissance agricole, sanitaire ou économique sur le Sénégal n'est écrite
ici. Ce serait le pire usage possible de ce dépôt : des affirmations produites de
mémoire, sans source, servies ensuite à des agriculteurs ou à des soignants comme
si la plateforme les savait. `.claude/rules/verification.md` interdit d'épingler
une valeur fabriquée dans un test ; en verser dans une base de connaissances
serait la même faute, avec des conséquences hors du dépôt.

Le corpus sénégalais s'ingère donc à partir de **vrais documents** — textes
officiels, publications d'instituts de recherche, guides d'ONG — déclarés dans un
manifeste avec leur titre, leur auteur, leur URL et leur catégorie de fiabilité :

    python scripts/seed_knowledge.py --manifeste corpus/senegal.yaml

Le format du manifeste est décrit dans `docs/knowledge/README.md`.

## Usage

    python scripts/seed_knowledge.py                 # documentation du projet
    python scripts/seed_knowledge.py --manifeste F   # un corpus déclaré
    python scripts/seed_knowledge.py --etat          # ce que la base contient
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.types import (  # noqa: E402
    KnowledgeDomain,
    KnowledgeStatus,
    Language,
    SourceCategory,
)

# Documentation du projet : chemin, titre, domaine.
# Ces documents décrivent la plateforme et sont vérifiables dans le dépôt.
DOCUMENTATION = (
    ("docs/architecture/overview.md", "Architecture GalSen IA", KnowledgeDomain.TECHNICAL),
    ("docs/architecture/decisions", "Décisions d'architecture (ADR)", KnowledgeDomain.TECHNICAL),
    ("docs/deployment", "Déploiement et exploitation", KnowledgeDomain.OPERATIONAL),
    ("docs/roadmap/roadmap.md", "Feuille de route", KnowledgeDomain.PROJECT_DOCUMENTATION),
    ("docs/standards", "Standards du projet", KnowledgeDomain.TECHNICAL),
)


def _manager() -> KnowledgeManagerImpl:
    """Construit le moteur de connaissances tel que la plateforme l'utilise."""
    return KnowledgeManagerImpl()


def semer_documentation(manager, ingestor) -> List[Dict[str, Any]]:
    """Ingère la documentation du projet ; retourne un rapport par document."""
    rapports = []
    for chemin_relatif, titre, domaine in DOCUMENTATION:
        chemin = RACINE / chemin_relatif
        if chemin.is_dir():
            fichiers = sorted(chemin.rglob("*.md"))
        elif chemin.is_file():
            fichiers = [chemin]
        else:
            print(f"  [absent] {chemin_relatif}")
            continue

        for fichier in fichiers:
            rapport = ingestor.ingest_file(
                str(fichier),
                title=f"{titre} — {fichier.stem}" if len(fichiers) > 1 else titre,
                # La documentation du projet fait autorité **sur le projet**, et
                # sur rien d'autre. C'est exactement ce que cette catégorie dit.
                source_category=SourceCategory.OFFICIAL_DOCUMENTATION,
                domain=domaine,
                author="GalSen IA",
                tags=["galsen-ia", "documentation"],
                language=Language.FR,
                # La documentation du projet est vérifiée par construction : elle
                # est relue et versionnée. Elle entre donc validée, contrairement
                # à un document externe.
                status=KnowledgeStatus.APPROVED,
            )
            rapports.append(rapport.to_dict())
            print(
                f"  {fichier.relative_to(RACINE)} → {len(rapport.knowledge_ids)} bloc(s)"
                + (f" | {len(rapport.errors)} erreur(s)" if rapport.errors else "")
            )
    return rapports


def semer_manifeste(manager, ingestor, chemin_manifeste: str) -> List[Dict[str, Any]]:
    """
    Ingère les documents déclarés dans un manifeste.

    Le manifeste **exige** un titre, une catégorie de source et un chemin. Un
    document sans provenance déclarée est refusé : c'est ce qui distingue une
    base de connaissances d'un tas de texte.
    """
    import yaml

    with open(chemin_manifeste, "r", encoding="utf-8") as fichier:
        manifeste = yaml.safe_load(fichier) or {}

    rapports = []
    for entree in manifeste.get("documents", []):
        manquants = [champ for champ in ("path", "title", "source_category") if not entree.get(champ)]
        if manquants:
            print(f"  [refusé] {entree.get('path', '?')} — champs manquants : {', '.join(manquants)}")
            continue

        chemin = Path(entree["path"])
        if not chemin.is_absolute():
            chemin = Path(chemin_manifeste).resolve().parent / chemin
        if not chemin.exists():
            print(f"  [absent] {chemin}")
            continue

        try:
            categorie = SourceCategory[entree["source_category"].upper()]
        except KeyError:
            valides = ", ".join(c.name for c in SourceCategory)
            print(f"  [refusé] {chemin} — catégorie inconnue. Valides : {valides}")
            continue

        rapport = ingestor.ingest_file(
            str(chemin),
            title=entree["title"],
            source_category=categorie,
            domain=KnowledgeDomain[entree.get("domain", "UNSPECIFIED").upper()],
            author=entree.get("author"),
            url=entree.get("url"),
            tags=entree.get("tags", []),
            # Un document externe entre en brouillon. Le valider est une décision
            # humaine, et le cycle de vie du VOLET 05 existe pour la porter.
            status=KnowledgeStatus.DRAFT,
        )
        rapports.append(rapport.to_dict())
        print(f"  {chemin.name} → {len(rapport.knowledge_ids)} bloc(s)")
    return rapports


def etat(manager) -> Dict[str, Any]:
    """
    Retourne ce que la base contient réellement.

    Le compte vit dans `stats()["store"]`, pas à la racine : le lire au mauvais
    endroit affichait « 0 élément » juste après en avoir versé cent — un rapport
    faux est pire qu'un rapport absent.
    """
    statistiques = manager.get_stats()
    magasin = statistiques.get("store", {})
    return {
        "total_items": magasin.get("total_items", 0),
        "average_content_length": magasin.get("average_content_length"),
        "content_type_distribution": magasin.get("content_type_distribution", {}),
    }


def main() -> int:
    """Point d'entrée."""
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    analyseur.add_argument("--manifeste", help="Manifeste YAML de documents à ingérer")
    analyseur.add_argument("--etat", action="store_true", help="Afficher l'état de la base")
    options = analyseur.parse_args()

    manager = _manager()

    if options.etat:
        statistiques = etat(manager)
        print(f"Éléments : {statistiques['total_items']}")
        if statistiques.get("average_content_length"):
            print(f"Taille moyenne d'un bloc : {statistiques['average_content_length']} caractères")
        if statistiques.get("content_type_distribution"):
            print(f"Types de contenu : {statistiques['content_type_distribution']}")
        return 0

    ingestor = DocumentIngestor(manager)

    if options.manifeste:
        print(f"Ingestion du manifeste {options.manifeste} :")
        semer_manifeste(manager, ingestor, options.manifeste)
    else:
        print("Ingestion de la documentation du projet :")
        semer_documentation(manager, ingestor)

    statistiques = etat(manager)
    print(f"\nBase de connaissances : {statistiques['total_items']} élément(s).")
    if os.getenv("GALSEN_STORAGE_BACKEND", "in-memory").strip().lower() != "sqlite":
        print(
            "\nAttention : GALSEN_STORAGE_BACKEND n'est pas 'sqlite'. Ce qui vient "
            "d'être versé vit en mémoire et disparaîtra à l'arrêt du processus."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
