"""
Acquisition et traitement du corpus wolof UD_Wolof-WTB.

    python scripts/ingest_wolof.py                 # télécharge, traite, écrit
    python scripts/ingest_wolof.py --offline       # retraite ce qui est déjà là
    python scripts/ingest_wolof.py --json          # rapport brut

## Deux ressources, deux rôles

- **CLAD / décret n° 2005-992** : l'autorité **orthographique**. C'est lui qui
  dit comment le wolof s'écrit (`src/wolof/clad.py`).
- **UD_Wolof-WTB** : le **corpus de travail**, publié sous licence CC BY-SA 4.0
  par le projet Universal Dependencies. Il n'a pas été produit par le CLAD, et
  le fichier de sortie ne prétend pas le contraire : chaque enregistrement porte
  sa vraie source.

## Le texte brut n'est jamais détruit

Chaque phrase est conservée telle qu'elle a été écrite (`text`) **et** sous sa
forme normalisée (`normalized_text`). Une normalisation qui écrase l'original
est irréversible, et une erreur de règle deviendrait alors définitive.

## La barrière de confiance s'applique ici comme ailleurs

Un fichier téléchargé est une **donnée externe**, quelle que soit la réputation
du dépôt qui l'héberge. Il passe par `src/security/trust.py` au niveau
`EXTERNAL`, et les motifs suspects sont relevés — une phrase d'un corpus
linguistique reste du texte, jamais une consigne.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.security.trust import TrustLevel, wrap  # noqa: E402
from src.wolof.clad import STANDARD, VERSION, normalize  # noqa: E402

#: Le corpus, et sa licence. Les trois fichiers sont publics.
SOURCE = "UD_Wolof-WTB"
LICENCE = "CC BY-SA 4.0"
BASE = (
    "https://raw.githubusercontent.com/UniversalDependencies/UD_Wolof-WTB/master/"
)
FICHIERS = {
    "train": "wo_wtb-ud-train.conllu",
    "dev": "wo_wtb-ud-dev.conllu",
    "test": "wo_wtb-ud-test.conllu",
}

#: Où les fichiers bruts et le corpus traité sont écrits.
DOSSIER_BRUT = os.path.join("data", "raw_wolof")
DOSSIER_TRAITE = os.path.join("data", "processed_wolof")
SORTIE = "official_wolof_corpus.json"

#: Ligne de commentaire CoNLL-U portant la phrase.
_TEXTE = re.compile(r"^#\s*text\s*=\s*(.*)$")
_SENT_ID = re.compile(r"^#\s*sent_id\s*=\s*(.*)$")


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _empreinte(donnees: bytes) -> str:
    """Retourne l'empreinte SHA-256 d'un contenu."""
    return hashlib.sha256(donnees).hexdigest()


def download(split: str, nom: str, dossier: str) -> Dict[str, Any]:
    """
    Télécharge un fichier du corpus et le conserve tel quel.

    Le contenu passe par la barrière de confiance : un corpus est une donnée
    externe, et sa réputation ne change pas ce qu'il est.

    Returns:
        Le chemin, l'empreinte, la taille et l'URL. En cas d'échec, `ok: False`
        avec **l'erreur exacte** — jamais un fichier vide qui ressemblerait à un
        corpus téléchargé.
    """
    from src.acquisition.fetcher import FetchRefused, fetch

    url = BASE + nom
    cible = os.path.join(dossier, nom)
    try:
        resultat = fetch(
            url,
            allowed_content_types=["text", "html"],
            rate_limit_rps=2.0,
            max_bytes=32 * 1024 * 1024,
        )
    except (FetchRefused, OSError) as erreur:
        return {"split": split, "url": url, "ok": False, "error": f"{type(erreur).__name__}: {erreur}"}

    enveloppe = wrap(
        resultat.body.decode("utf-8", errors="replace"), TrustLevel.EXTERNAL, origin=url
    )
    os.makedirs(dossier, exist_ok=True)
    with open(cible, "wb") as fichier:
        fichier.write(resultat.body)

    return {
        "split": split,
        "url": url,
        "path": cible,
        "ok": True,
        "bytes": len(resultat.body),
        "content_hash": _empreinte(resultat.body),
        "trust_level": enveloppe.level.value,
        "suspicious_patterns": len(enveloppe.suspicions),
    }


def parse_conllu(contenu: str) -> List[Dict[str, str]]:
    """
    Extrait les phrases d'un fichier CoNLL-U.

    Seules les lignes `# text = …` portent la phrase telle qu'elle se lit ;
    reconstruire depuis les colonnes de mots perdrait la ponctuation collée et
    les contractions. `# sent_id = …` est conservé : c'est l'identifiant amont,
    et il permet de retrouver la phrase dans le corpus d'origine.
    """
    phrases: List[Dict[str, str]] = []
    identifiant = ""
    for ligne in (contenu or "").splitlines():
        depouillee = ligne.strip()
        marque = _SENT_ID.match(depouillee)
        if marque:
            identifiant = marque.group(1).strip()
            continue
        marque = _TEXTE.match(depouillee)
        if marque:
            texte = marque.group(1).strip()
            if texte:
                phrases.append({"sent_id": identifiant, "text": texte})
            identifiant = ""
    return phrases


def build_records(
    phrases: List[Dict[str, str]], split: str, url: str
) -> List[Dict[str, Any]]:
    """
    Construit les enregistrements du corpus traité, un par phrase.

    Chaque enregistrement porte sa provenance réelle : ce fichier est le corpus
    **de GalSen**, normalisé selon le standard CLAD, et non un produit du CLAD.
    """
    enregistrements = []
    for phrase in phrases:
        verdict = normalize(phrase["text"])
        enregistrements.append({
            "text": verdict["raw"],
            "normalized_text": verdict["normalized"],
            "language": "wo",
            "source": SOURCE,
            "sent_id": phrase["sent_id"],
            "split": split,
            "source_url": url,
            "licence": LICENCE,
            "content_hash": _empreinte(verdict["normalized"].encode("utf-8")),
            "normalization_standard": STANDARD,
            "normalization_version": VERSION,
            "letters_outside_alphabet": verdict["letters_outside_alphabet"],
            "special_letters": verdict["special_letters"],
            "suspected_miscodings": verdict["suspected_miscodings"],
        })
    return enregistrements


def deduplicate(enregistrements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Écarte les phrases rigoureusement identiques, et **dit combien**.

    Le premier exemplaire est conservé avec son découpage d'origine : un doublon
    silencieusement supprimé fausserait toute mesure faite sur ce corpus.
    """
    vues: Dict[str, int] = {}
    uniques, doublons = [], []
    for enregistrement in enregistrements:
        empreinte = enregistrement["content_hash"]
        if empreinte in vues:
            doublons.append({
                "sent_id": enregistrement["sent_id"],
                "split": enregistrement["split"],
                "duplicate_of": vues[empreinte],
            })
            continue
        vues[empreinte] = len(uniques)
        uniques.append(enregistrement)
    return {"records": uniques, "duplicates": doublons}


def statistics(enregistrements: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mesure ce que la normalisation a réellement fait."""
    modifies = sum(1 for e in enregistrements if e["text"] != e["normalized_text"])
    par_lettre = {
        lettre: sum(1 for e in enregistrements if lettre in e["special_letters"])
        for lettre in ("ë", "ñ", "ŋ")
    }
    hors_alphabet: Dict[str, int] = {}
    suspects: Dict[str, int] = {}
    for enregistrement in enregistrements:
        for lettre in enregistrement["letters_outside_alphabet"]:
            hors_alphabet[lettre] = hors_alphabet.get(lettre, 0) + 1
        for lettre in enregistrement.get("suspected_miscodings", {}):
            suspects[lettre] = suspects.get(lettre, 0) + 1

    return {
        "records": len(enregistrements),
        "normalized_changed": modifies,
        "normalized_unchanged": len(enregistrements) - modifies,
        "sentences_with": par_lettre,
        "letters_outside_alphabet": dict(sorted(hors_alphabet.items())),
        # Signalés, jamais corrigés : changer une lettre sans qu'une personne
        # l'ait vu est exactement ce que la normalisation refuse.
        "suspected_miscodings": dict(sorted(suspects.items())),
        "by_split": {
            split: sum(1 for e in enregistrements if e["split"] == split)
            for split in FICHIERS
        },
    }


def run(
    dossier_brut: Optional[str] = None,
    dossier_traite: Optional[str] = None,
    offline: bool = False,
) -> Dict[str, Any]:
    """
    Télécharge, traite et écrit le corpus. Rend le rapport complet.

    Args:
        dossier_brut: Où conserver les fichiers d'origine.
        dossier_traite: Où écrire le corpus traité.
        offline: Ne télécharge pas ; retraite ce qui est déjà présent. Un
            fichier absent est **dit absent**, jamais remplacé par du vide.
    """
    racine = _racine()
    brut = dossier_brut or os.path.join(racine, DOSSIER_BRUT)
    traite = dossier_traite or os.path.join(racine, DOSSIER_TRAITE)
    os.makedirs(brut, exist_ok=True)
    os.makedirs(traite, exist_ok=True)

    telechargements, enregistrements, echecs = [], [], []
    for split, nom in FICHIERS.items():
        chemin = os.path.join(brut, nom)
        if offline or os.path.isfile(chemin):
            if not os.path.isfile(chemin):
                echecs.append({"split": split, "error": f"Fichier absent : {chemin}"})
                continue
            with open(chemin, "rb") as fichier:
                donnees = fichier.read()
            telechargements.append({
                "split": split, "url": BASE + nom, "path": chemin, "ok": True,
                "bytes": len(donnees), "content_hash": _empreinte(donnees),
                "from_cache": True,
            })
        else:
            resultat = download(split, nom, brut)
            telechargements.append(resultat)
            if not resultat["ok"]:
                echecs.append(resultat)
                continue
            with open(chemin, "rb") as fichier:
                donnees = fichier.read()

        phrases = parse_conllu(donnees.decode("utf-8", errors="replace"))
        enregistrements.extend(build_records(phrases, split, BASE + nom))

    tri = deduplicate(enregistrements)
    stats = statistics(tri["records"])

    corpus = {
        "corpus": "official_wolof_corpus",
        "meaning": (
            "Corpus wolof **de GalSen**, normalisé selon le standard orthographique "
            "CLAD. UD_Wolof-WTB n'a pas été produit par le CLAD ; chaque "
            "enregistrement porte sa source réelle."
        ),
        "language": "wo",
        "source": SOURCE,
        "licence": LICENCE,
        "normalization_standard": STANDARD,
        "normalization_version": VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "statistics": stats,
        "duplicates": len(tri["duplicates"]),
        "records": tri["records"],
    }

    sortie = os.path.join(traite, SORTIE)
    with open(sortie, "w", encoding="utf-8") as fichier:
        json.dump(corpus, fichier, ensure_ascii=False, indent=1)

    return {
        "downloads": telechargements,
        "downloaded": sum(1 for t in telechargements if t.get("ok")),
        "failures": echecs,
        "sentences": len(enregistrements),
        "records": len(tri["records"]),
        "duplicates": len(tri["duplicates"]),
        "statistics": stats,
        "output": sortie,
        "ok": not echecs and bool(tri["records"]),
    }


def main(argv: Optional[List[str]] = None) -> int:
    """Exécute l'ingestion et rend le code de sortie."""
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--offline", action="store_true", help="Ne rien télécharger.")
    analyseur.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    arguments = analyseur.parse_args(argv)

    rapport = run(offline=arguments.offline)

    if arguments.json:
        print(json.dumps(rapport, ensure_ascii=False, indent=2))
        return 0 if rapport["ok"] else 1

    print(f"Fichiers téléchargés : {rapport['downloaded']} / {len(FICHIERS)}")
    for echec in rapport["failures"]:
        print(f"  [échec] {echec.get('split')} — {echec.get('error')}")
    print(f"Phrases extraites    : {rapport['sentences']}")
    print(f"Enregistrements      : {rapport['records']} ({rapport['duplicates']} doublon(s) écarté(s))")
    stats = rapport["statistics"]
    print(f"Normalisation        : {stats['normalized_changed']} texte(s) modifié(s)")
    print(f"  ë / ñ / ŋ          : {stats['sentences_with']}")
    if stats["letters_outside_alphabet"]:
        print(f"  hors alphabet      : {stats['letters_outside_alphabet']}")
    if stats["suspected_miscodings"]:
        print(f"  ŋ mal encodé ?     : {stats['suspected_miscodings']} (signalé, non corrigé)")
    print(f"Sortie               : {rapport['output']}")
    return 0 if rapport["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
