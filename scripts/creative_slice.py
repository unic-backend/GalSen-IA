#!/usr/bin/env python3
"""
Runs the creative vertical slice and prints what actually happened.

Same discipline as `scripts/demonstration.py`: walk the real chain, report each
stage's outcome, and make sure the final count cannot be read as a success. No
video is produced — the point of running this is to see *where* the chain stops
and why, on the machine it is run on.

Usage:
    python scripts/creative_slice.py
    python scripts/creative_slice.py "une conversation dans une boutique"

Exit code is 0 whenever the slice ran, including when generation is blocked:
a blocked stage is a measurement, not a failure of this script.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.creative.mvp import BLOQUE, NON_ATTEINT, NON_MESURABLE, OK, run_slice  # noqa: E402
from src.creative.voice.scene import AudioSegment  # noqa: E402

#: Un enregistrement fictif suffit : la tranche ne lit pas le fichier, elle
#: vérifie qu'il est encore là et qu'il n'est jamais remplacé.
CHEMIN_AUDIO = "/tmp/galsen-demo.wav"

SYMBOLES = {OK: "OK ", BLOQUE: "!! ", NON_MESURABLE: "?? ", NON_ATTEINT: ".. "}


def main() -> int:
    """Exécute la tranche et l'affiche."""
    demande = (sys.argv[1] if len(sys.argv) > 1
               else "une conversation dans une boutique à Dakar")

    # Deux segments, une alternance wolof → français chez un même locuteur.
    segments = [
        AudioSegment("s1", 0.0, 2.0, CHEMIN_AUDIO, language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
        AudioSegment("s2", 2.0, 3.0, CHEMIN_AUDIO, language="fr",
                     language_confidence=0.9, speaker_id="sp1"),
    ]

    resultat = run_slice(demande, audio_segments=segments,
                         references={"sp1": "awa"})

    print(f"\nTranche verticale créative — « {demande} »\n")
    for etape in resultat["stages"]:
        symbole = SYMBOLES.get(etape["outcome"], "   ")
        print(f"  {symbole} {etape['stage']:26} {etape['outcome']}")
        print(f"      {etape['detail']}")

    comptes = resultat["counts"]
    print(f"\n  {comptes[OK]} étapes ont réellement eu lieu sur "
          f"{resultat['total']}.")
    print(f"  Vidéo produite : {resultat['produced_video']}")
    print(f"\n{resultat['note']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
