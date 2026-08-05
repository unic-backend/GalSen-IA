# -*- coding: utf-8 -*-
"""
Fusion des chapitres des manuels d'architecture (docs/architecture) en un seul
fichier Markdown par volet (VOLET_01.md ... VOLET_25.md).

Principe : concaténation binaire stricte, sans aucune modification du contenu.
L'ordre des chapitres est celui du numéro de chapitre encodé dans le nom de fichier.
"""

import re
import sys
from pathlib import Path

ARCH_DIR = Path(r"C:\GalSen IA\docs\architecture")

# (nom du dossier, numero de volet) — inventaire manuel des 26 dossiers de manuels
MANUAL_FOLDERS = [
    ("Master Constitution. Volet 1", 1),
    ("Architecture Manual. Volet 2", 2),
    ("Development Manual. Volet 3", 3),
    ("Roadmap. Volet 4", 4),
    ("Knowledge Engine. Volet 5", 5),
    ("Security Manual. Volet 6", 6),
    ("Connectors & Partners. Volet 7", 7),
    ("Country Expansion. Vo\u0302et 8", 8),
    ("Project Journal. Volet 9", 9),
    ("Future Vision. Volet 10", 10),
    ("SECURITY ENGINE MANUAL.  Volet 11", 11),
    ("Communication Enginte V12", 12),
    ("User Management Engine. V13", 13),
    ("Authentication & Identity Engine. V14", 14),
    ("API Gateway Engine. V15", 15),
    ("Automation Engine. V16", 16),
    ("Agent Framework Engine. V17", 17),
    ("Infrastructure & DevOps Engine. V18", 18),
    ("Monitoring & Observability Engine. V19", 19),
    ("Memory Engine. Volet 20", 20),
    ("Enterprise Governance & Operations Manual. V20", 20),  # vide — à signaler
    ("KNOWLEDGE ENGINE MANUAL VOLET 21", 21),
    ("DECISION ENGINE MANUAL. Volet 22", 22),
    ("LEARNING ENGINE MANUAL. Volet 23", 23),
    ("INTEGRATION ENGINE MANUAL. Volet 24", 24),
    ("ENTERPRISE GOVERNANCE & GLOBAL ARCHITECTURE MANUAL. Volet 25", 25),
]

# Regex pour extraire le numero de chapitre du nom de fichier
CHAPTER_RE = re.compile(r"(?:chapter|chapitre)\s*[_-]?\s*(\d{1,2})", re.IGNORECASE)

# Regex pour extraire le numero de volet du nom du dossier
VOLET_RE = re.compile(r"v[^\d]*[\s.]*(\d{1,2})\b", re.IGNORECASE)


def chapter_number(filename: str) -> int:
    """Retourne le numero de chapitre encode dans le nom, ou 999 si absent."""
    m = CHAPTER_RE.search(filename)
    return int(m.group(1)) if m else 999


def folder_volet(name: str):
    """Retourne le numero de volet du dossier, ou None."""
    m = VOLET_RE.search(name)
    return int(m.group(1)) if m else None


def main():
    report = {}
    invalid = []
    by_volet: dict[int, list] = {}

    # Regrouper les dossiers par numero de volet
    for folder_name, volet in MANUAL_FOLDERS:
        by_volet.setdefault(volet, []).append((folder_name, volet == folder_volet(folder_name)))

    for volet in sorted(by_volet):
        candidates = by_volet[volet]
        sources = []
        for folder_name, _ in candidates:
            folder = ARCH_DIR / folder_name
            if not folder.is_dir():
                invalid.append(f"[manquant] Dossier introuvable pour le volet {volet} : {folder_name}")
                continue
            files = sorted(
                (p for p in folder.iterdir() if p.is_file()),
                key=lambda p: (chapter_number(p.name), p.name),
            )
            sources.append((folder_name, files))

        # Choisir le dossier "source" : celui qui contient des fichiers de chapitres
        non_empty = [s for s in sources if s[1]]
        if not non_empty:
            names = ", ".join(folder_name for folder_name, _ in sources)
            invalid.append(f"[vide] Aucun chapitre pour le volet {volet} (dossiers : {names})")
            report[volet] = (names, [], "AUCUN CHAPITRE", 0)
            continue

        folder_name, files = non_empty[0]
        # Signaler les dossiers concurrents non vides
        if len(non_empty) > 1:
            extra = ", ".join(n for n, f in sources if f and n != folder_name)
            invalid.append(f"[conflit] Volet {volet} : plus d'un dossier non vide ({extra}) — dossier utilise : {folder_name}")
        for empty_name, empty_files in sources:
            if not empty_files:
                invalid.append(f"[vide] Volet {volet} : dossier sans chapitre ignore : {empty_name}")

        # Concaténation binaire stricte. Le contenu de chaque fichier reste
        # byte-pour-byte identique ; un saut de ligne de séparation est inséré
        # uniquement quand le fichier précédent ne se termine pas par \n,
        # afin de ne pas coller l'en-tête du chapitre suivant à la fin du précédent.
        parts = []
        separators = 0
        for p in files:
            raw = p.read_bytes()
            if parts and not parts[-1].endswith(b"\n"):
                parts[-1] = parts[-1] + b"\n"
                separators += 1
            parts.append(raw)
        merged = b"".join(parts)

        out_path = ARCH_DIR / f"VOLET_{volet:02d}.md"
        out_path.write_bytes(merged)

        report[volet] = (folder_name, [p.name for p in files], len(files), separators)

        print(f"VOlet {volet:02d} -> {out_path.name} ({len(files)} chapitres, {len(merged)} octets)")

    print("\n=== VERIFICATION ===")
    for volet in sorted(report):
        folder_name, files, n, separators = report[volet]
        if n == "AUCUN CHAPITRE":
            continue
        out_path = ARCH_DIR / f"VOLET_{volet:02d}.md"
        merged = out_path.read_bytes()
        ok = True
        total_src = 0
        for fname in files:
            src = (ARCH_DIR / folder_name / fname).read_bytes()
            total_src += len(src)
            if src not in merged:
                ok = False
                print(f"  ERREUR volet {volet}: contenu absent de {fname}")
        expected = total_src + separators
        if len(merged) != expected:
            ok = False
            print(f"  ERREUR volet {volet}: taille {len(merged)} != sources {total_src} + separateurs {separators}")
        marker = "OK" if ok else "ECHEC"
        sep_info = f" (+{separators} saut(s) de ligne de separation)" if separators else ""
        print(f"  VOLET_{volet:02d}.md : {marker} — {n} chapitres, {len(merged)} octets{sep_info}")

    print("\n=== FICHIERS INVALIDES / MANQUANTS ===")
    if invalid:
        for line in invalid:
            print("  " + line)
    else:
        print("  Aucun.")

    print("\n=== FICHIERS GENERES ===")
    for volet in sorted(report):
        if report[volet][2] != "AUCUN CHAPITRE":
            print(f"  VOLET_{volet:02d}.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
