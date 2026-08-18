"""
Le passage qui regarde, et ce qu'il rend.

`scan()` exécute les détecteurs, écarte ce que quelqu'un a déjà refusé de
revoir, et rend le reste trié. Il **n'agit sur rien** : la découverte proactive
de ce dépôt propose, elle n'exécute pas.

## Ce qui déclenche un passage

Rien, tout seul, dans le processus de l'API — et c'est écrit plutôt que masqué
derrière un fil d'exécution que personne n'aurait vérifié. Trois déclencheurs
existent, tous explicites :

- `python scripts/proactive_scan.py`, qu'un opérateur peut mettre en `cron` ;
- `GET /proactive/suggestions`, quand quelqu'un regarde ;
- `due(last_run, now)`, pour un appelant qui veut respecter une cadence.

Un fil de fond qui tourne dans l'API demanderait de décider ce qu'il se passe
quand deux instances existent (ADR-009 n'en autorise qu'une), et de le tester
sans horloge. Le faire à moitié donnerait la pire des situations : une
découverte qu'on croit active et qui ne tourne pas.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .detectors import DETECTEURS, run_detector
from .journal import SuggestionJournal
from .observations import Observation, sort_observations

logger = logging.getLogger(__name__)

#: Cadence par défaut : une fois par jour. Une plateforme dont l'état bouge
#: lentement n'a rien de neuf à dire toutes les heures, et le dire quand même
#: est la première étape vers un assistant qu'on ignore.
CADENCE_SECONDES = 24 * 3600


def scan(
    journal: Optional[SuggestionJournal] = None,
    detectors: Optional[List[str]] = None,
    record: bool = True,
) -> Dict[str, Any]:
    """
    Exécute les détecteurs et rend ce qui mérite d'être dit.

    Args:
        journal: Journal des suggestions ; celui du répertoire de données sinon.
        detectors: Détecteurs à exécuter ; tous par défaut.
        record: Inscrire au journal ce qui a été montré.

    Returns:
        Les observations retenues, celles qui ont été tues, et les détecteurs en
        panne — un détecteur muet et un détecteur cassé ne se confondent pas.
    """
    carnet = journal if journal is not None else SuggestionJournal()
    noms = detectors if detectors is not None else list(DETECTEURS)

    trouvees: List[Observation] = []
    en_panne: List[Dict[str, str]] = []
    for nom in noms:
        resultat = run_detector(nom)
        if resultat["status"] == "failed":
            en_panne.append({"detector": nom, "reason": resultat["reason"]})
            continue
        trouvees.extend(resultat["observations"])

    retenues = sort_observations(carnet.filter(trouvees))
    if record and retenues:
        carnet.record_surfaced(retenues)

    return {
        "observations": [observation.to_dict() for observation in retenues],
        "count": len(retenues),
        "silenced": len(trouvees) - len(retenues),
        "detectors_run": len(noms),
        "detectors_failed": en_panne,
        # Dit explicitement : ce passage n'a rien changé.
        "acted": False,
        "note": (
            "Aucune action n'a été exécutée. Chaque observation nomme qui doit "
            "décider."
        ),
    }


def due(last_run: Optional[float], now: Optional[float] = None,
        cadence: int = CADENCE_SECONDES) -> bool:
    """
    Indique si un passage est dû.

    Args:
        last_run: Instant du dernier passage, ou None s'il n'y en a jamais eu.
        now: Instant courant ; l'heure système sinon.
        cadence: Intervalle minimal entre deux passages.

    Returns:
        Vrai si la cadence est écoulée. **Un premier passage est toujours dû** :
        une plateforme qui n'a jamais regardé n'a rien à taire.
    """
    if last_run is None:
        return True
    instant = now if now is not None else time.time()
    return instant - last_run >= cadence


def dismiss(observation_id: str, fingerprint: str, by: str = "operator",
            reason: str = "", journal: Optional[SuggestionJournal] = None) -> Dict[str, Any]:
    """
    Écarte une observation par son identifiant.

    Args:
        observation_id: Identifiant rendu par `scan()`.
        fingerprint: Empreinte au moment où elle a été vue — elle est exigée
            pour que l'écart porte sur **cette situation**, pas sur le sujet en
            général. Sans elle, écarter « 3 fichiers sans test » masquerait
            « 300 fichiers sans test » plus tard.
        by: Qui écarte.
        reason: Motif, s'il est donné.
    """
    if not observation_id or not fingerprint:
        return {
            "status": "refused",
            "reason": "L'identifiant et l'empreinte sont requis.",
        }

    carnet = journal if journal is not None else SuggestionJournal()

    class _Vue:
        """Vue minimale d'une observation, pour l'inscrire au journal."""

        id = observation_id
        fingerprint = ""
        finding = ""

    vue = _Vue()
    vue.fingerprint = fingerprint
    carnet.dismiss(vue, by=by, reason=reason)
    return {"status": "dismissed", "id": observation_id, "fingerprint": fingerprint}
