"""
MoneyPrinterTurbo, déclaré et sondé — jamais exécuté à l'aveugle (ADR-030).

## Ce que ce fournisseur est, et ce qu'il n'est pas

**Il ne génère pas de vidéo.** Lu dans sa source, pas dans son README
(`docs/providers/moneyprinterturbo-research.md`) : `material.py` cherche des
rushes sur Pexels et Pixabay et les télécharge, `video.py` les assemble avec
moviepy en déléguant à `ffmpeg`. Aucun modèle ne produit un pixel.

D'où la tâche `stock_assembly` plutôt que `text_to_video`. Les confondre serait
une erreur de catégorie aux conséquences réelles : un routeur choisirait cet
assembleur pour « génère une scène avec mon ami » et rendrait des rushes d'un
inconnu — la substitution silencieuse que `src/creative/routing.py` refuse.

## Pourquoi il est appelé par HTTP et jamais importé

MoneyPrinterTurbo expose un service FastAPI. GalSen IA l'appelle ; il ne
l'importe pas. Deux raisons, la première étant juridique :

- **`edge-tts` est LGPL-3.0** (audit M03). ADR-024 avait déjà tranché que lancer
  un outil copyleft comme processus isolé n'est pas le même acte que le lier à ce
  dépôt, et que la différence a des conséquences légales. `API` rend la
  distinction structurelle au lieu de la laisser à la mémoire de quelqu'un.
- **Aucune dépendance n'est ajoutée.** L'importer amènerait moviepy, streamlit,
  redis, edge-tts, le SDK Azure et une dizaine de clients dans cette plateforme.

## Ce que ce module fait aujourd'hui : refuser en disant quoi installer

Rien ne peut s'exécuter ici — pas de `ffmpeg`, pas de service configuré, pas de
clé d'API. `generate()` **refuse**, comme `wangp.generate()`, et pour la même
raison : un résultat bouché est indiscernable d'une composition qui a
silencieusement échoué.

Ce que la déclaration apporte quand même : le graphe de capacités enregistre
qu'un chemin **sans GPU** existe, la fiche de licence fait refuser le
fournisseur pour tout travail commercial, et `health()` dit à un exploitant les
trois gestes exacts qui le rendraient utilisable.

## Les droits sur la sortie sont inconnus, et c'est déclaré

Les rushes viennent de Pexels et de Pixabay. Savoir si la vidéo produite peut
être **vendue** dépend de leurs conditions d'API, que personne dans ce dépôt n'a
lues. Le statut commercial est donc `UNKNOWN` — et le sélecteur créatif refusera
ce fournisseur pour un travail commercial, sans une ligne de code de plus.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base import ProviderCapability

#: Le dépôt, pour qu'un lecteur puisse vérifier ce que ce module affirme.
DEPOT = "https://github.com/harry0703/MoneyPrinterTurbo"

#: L'état d'intégration, repris tel quel de `wangp.py` : le vocabulaire existe,
#: et en inventer un second ferait diverger deux fournisseurs du même registre.
NON_INTEGRE = "ADAPTER_ONLY"

#: L'adresse du service, quand un exploitant en fait tourner un.
VARIABLE_URL = "GALSEN_MPT_URL"

#: Les clés de banques d'images. Sans au moins une, MPT n'a aucun rush à
#: assembler — c'est une configuration de MPT, jamais lue ni relayée par nous.
VARIABLES_MATERIEL = ("GALSEN_MPT_PEXELS_CONFIGURED",
                      "GALSEN_MPT_PIXABAY_CONFIGURED")

#: Ce qui manque, et ce que chaque manque empêche. Un blocage sans geste de
#: réparation fait chercher au mauvais endroit.
BLOCAGES = {
    "service": (
        f"Aucun service MoneyPrinterTurbo déclaré. Poser {VARIABLE_URL} vers "
        "une instance en fonctionnement — ce dépôt n'en démarre aucune et "
        "n'importe pas le projet (ADR-030 : appel par API, pas par lien)."
    ),
    "ffmpeg": (
        "MoneyPrinterTurbo compose avec moviepy et délègue à `ffmpeg`. Le "
        "`ffmpeg` de cette machine est construit `--disable-everything` : il "
        "répond à `-version` comme un complet et n'encode rien. C'est le même "
        "blocage que quatre étapes du moteur média."
    ),
    "material": (
        "Aucune banque d'images déclarée configurée. Sans Pexels ni Pixabay, "
        "MoneyPrinterTurbo n'a aucun rush à assembler."
    ),
}

#: Ce que le fournisseur **déclare** savoir faire. Une déclaration n'est pas une
#: disponibilité : `health()` mesure, ceci annonce.
CAPACITE_ATTENDUE = ProviderCapability(
    provider_id="moneyprinterturbo",
    tasks=frozenset({"stock_assembly"}),
    max_width=1920,
    max_height=1080,
    max_duration_s=600.0,
    # `None` et non `0` : MoneyPrinterTurbo ne demande **pas** de GPU, et c'est
    # sa seule vraie supériorité ici. Écrire `0` laisserait croire qu'un besoin
    # a été mesuré à zéro plutôt qu'inexistant.
    min_vram_gb=None,
)


def _service_declare() -> Optional[str]:
    """L'adresse du service, ou `None` si personne n'en a déclaré."""
    valeur = os.environ.get(VARIABLE_URL, "").strip()
    return valeur or None


def _materiel_declare() -> bool:
    """Vrai si au moins une banque d'images est déclarée configurée."""
    return any(os.environ.get(nom, "").strip().lower() in ("1", "true", "yes")
               for nom in VARIABLES_MATERIEL)


def _ffmpeg_utilisable() -> bool:
    """
    Si `ffmpeg` peut réellement encoder ici.

    La sonde du moteur média est réutilisée plutôt que refaite : elle
    interroge l'outil au lieu de vérifier qu'un binaire existe, ce que ce dépôt
    a appris à ses dépens — le `ffmpeg` de cette machine répond à `-version`
    comme un complet et n'encode rien.
    """
    from ...integration.degradation import DISPONIBLE
    from ..core.capabilities import probe
    return probe("video_encode")["state"] == DISPONIBLE


def health() -> Dict[str, Any]:
    """
    Ce qui manque pour que ce fournisseur serve, mesuré maintenant.

    Returns:
        L'état et, pour chaque manque, le geste qui le répare. Trois conditions
        indépendantes : un service joignable, un `ffmpeg` qui encode, et au
        moins une banque d'images configurée. Elles sont rapportées **toutes**,
        pas seulement la première — un exploitant qui répare l'une pour
        découvrir la suivante fait trois allers-retours au lieu d'un.
    """
    service = _service_declare()
    encode = _ffmpeg_utilisable()
    materiel = _materiel_declare()

    manques = []
    if service is None:
        manques.append("service")
    if not encode:
        manques.append("ffmpeg")
    if not materiel:
        manques.append("material")

    return {
        "provider_id": CAPACITE_ATTENDUE.provider_id,
        "integration": NON_INTEGRE,
        "available": not manques,
        "missing": manques,
        "actions": {nom: BLOCAGES[nom] for nom in manques},
        "service_declared": service is not None,
        "repository": DEPOT,
        "note": (
            "Prêt à servir." if not manques else
            f"{len(manques)} condition(s) non remplie(s). Aucune n'est un "
            "défaut de ce dépôt : ce sont des gestes d'exploitation."
        ),
    }


def is_available() -> bool:
    """Vrai seulement si les trois conditions sont réunies."""
    return health()["available"]


def generate(request: Any, output_path: str,
             options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Refuse, en disant exactement ce qui manque.

    Args:
        request: La demande d'assemblage.
        output_path: Où le montage devrait être écrit.
        options: Réglages éventuels.

    Raises:
        NotImplementedError: Toujours, tant que les conditions ne sont pas
            réunies. **Rendre un fichier bouché serait pire que refuser** : un
            bouchon est indiscernable d'une composition qui a silencieusement
            échoué, et c'est déjà la raison pour laquelle `wangp.generate()`
            lève.

            Quand un exploitant aura rempli les trois conditions, le chemin
            d'exécution sera un ajout court et relisible — pas une intégration
            à refaire.
    """
    etat = health()
    if etat["available"]:
        raise NotImplementedError(
            "Les conditions sont réunies mais le chemin d'exécution n'est pas "
            "écrit (ADR-030, décision 5). Il appellera le service par HTTP ; "
            "aucun code de MoneyPrinterTurbo n'est importé ici."
        )
    raise NotImplementedError(
        "MoneyPrinterTurbo ne peut pas servir : "
        + " | ".join(f"{nom} — {BLOCAGES[nom]}" for nom in etat["missing"])
    )


def integration_report() -> Dict[str, Any]:
    """
    Ce que ce fournisseur est, ce qu'il n'est pas, et ce qui reste ouvert.

    Returns:
        De quoi juger sans lire ni ce module ni le dépôt distant.
    """
    return {
        "provider_id": CAPACITE_ATTENDUE.provider_id,
        "repository": DEPOT,
        "integration": NON_INTEGRE,
        "invocation": "API",
        "tasks": sorted(CAPACITE_ATTENDUE.tasks),
        "needs_gpu": False,
        "health": health(),
        "is": [
            "Un assembleur de rushes : il cherche sur Pexels et Pixabay, "
            "télécharge, et compose avec moviepy + ffmpeg.",
            "Le seul chemin vidéo des deux programmes qui **n'exige pas de "
            "GPU**.",
            "Porteur d'un TTS et d'un ASR, les deux capacités que cette "
            "plateforme mesure `ABSENT` et `UNAVAILABLE`.",
        ],
        "is_not": [
            "Un générateur vidéo : aucun modèle ne produit de pixel.",
            "Une préservation d'identité, une continuité, un contrôle de "
            "caméra ou une synchronisation labiale — il n'en a aucun.",
            "Un remplacement de `wangp.py`, qui répond à une autre question.",
        ],
        "open_questions": {
            "output_rights": (
                "Les rushes viennent de Pexels et Pixabay. Savoir si la vidéo "
                "produite peut être vendue dépend de leurs conditions d'API, "
                "non lues. Statut commercial déclaré `UNKNOWN` en conséquence."
            ),
            "edge_tts_licence": (
                "Le chemin TTS de MoneyPrinterTurbo est `edge-tts`, LGPL-3.0. "
                "L'appel par API garde la distinction structurelle ; intégrer "
                "ce TTS **ici** serait une décision distincte, et M04 a mesuré "
                "que `kokoro-tts` est MIT et local."
            ),
        },
    }
