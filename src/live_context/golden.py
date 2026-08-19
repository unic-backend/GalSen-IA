"""
Les scénarios du §35, exécutés contre le code vivant (L14.1).

## Pourquoi un exécuteur en plus des tests

`tests/live_context/` contient plus de trois cents tests. Ils passent en
intégration continue et disparaissent ensuite : personne ne peut demander à la
plateforme **ce qu'elle tient**, seulement lancer sa suite.

`creative/golden.py` puis `research/golden.py` ont résolu cela pour leurs
programmes. Ce module fait la même chose pour le contexte live, avec le même
vocabulaire de verdicts — deux programmes qui nommeraient différemment la même
chose finiraient par ne plus être comparables.

## Trois verdicts, pas deux

| Verdict | Ce qu'il dit |
|---|---|
| `VERIFIED` | L'invariant est vérifié **contre le code vivant**, maintenant |
| `BLOCKED` | La capacité manque, et la plateforme le **rapporte** au lieu d'inventer |
| `NOT_APPLICABLE` | Le cas ne peut pas exister ici, et la raison est dite |

**`BLOCKED` est une assertion, pas un test sauté.** Il affirme que la
plateforme rapporte son incapacité — ce qui est exactement ce qu'on veut
vérifier d'un programme dont la moitié des étapes ne peut pas tourner ici.

## Ce qu'aucun cas ne fait

Aucun n'ouvre de périphérique, aucun n'écrit sur le disque, aucun n'atteint le
réseau. Un scénario qui aurait besoin de l'un des trois rendrait `BLOCKED` en
nommant ce qui manque.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

VERIFIE = "VERIFIED"
BLOQUE = "BLOCKED"
SANS_OBJET = "NOT_APPLICABLE"
VERDICTS = (VERIFIE, BLOQUE, SANS_OBJET)


def _verifie(**preuve: Any) -> Dict[str, Any]:
    """Un invariant tenu, avec ce qui le prouve."""
    return {"verdict": VERIFIE, "evidence": preuve}


def _bloque(missing: str, reported: str, **preuve: Any) -> Dict[str, Any]:
    """Une capacité absente, **rapportée** plutôt qu'inventée."""
    return {"verdict": BLOQUE, "missing": missing, "reported": reported,
            "evidence": preuve}


def _sans_objet(reason: str, **preuve: Any) -> Dict[str, Any]:
    """Un cas qui ne peut pas exister ici, et pourquoi."""
    return {"verdict": SANS_OBJET, "reason": reason, "evidence": preuve}


@dataclass(frozen=True)
class GoldenCase:
    """Un scénario du §35, son invariant, et la fonction qui l'exécute."""

    number: int
    title: str
    invariant: str
    run: Callable[[], Dict[str, Any]]


# ---------------------------------------------------------------------------
# 1 à 4 : l'observation et ses statuts
# ---------------------------------------------------------------------------

def _c01() -> Dict[str, Any]:
    """ABSENT n'est pas UNKNOWN, et l'un des deux exige son constat."""
    from .state import ABSENT, INCONNU, ObservationRefused, absent, unknown
    assert absent("microphone", "audio", "/dev/snd cherché").status == ABSENT
    assert unknown("language", "audio").status == INCONNU
    try:
        absent("microphone", "audio", "   ")
    except ObservationRefused:
        pass
    else:                                              # pragma: no cover
        raise AssertionError("Une absence sans constat aurait été acceptée.")
    return _verifie(absent_requires_finding=True, unknown_does_not=True)


def _c02() -> Dict[str, Any]:
    """Une confiance sans base est refusée, et l'inverse aussi."""
    from .state import MESURE, Observation, ObservationRefused
    for kwargs in ({"confidence": 0.9}, {"confidence_basis": "au jugé"}):
        try:
            Observation(subject="s", status=MESURE, modality="audio",
                        value="v", **kwargs)
        except ObservationRefused:
            continue
        raise AssertionError(f"Accepté à tort : {kwargs}")  # pragma: no cover
    return _verifie(confidence_requires_basis=True, basis_requires_value=True)


def _c03() -> Dict[str, Any]:
    """Un désaccord est enregistré, jamais moyenné."""
    from .state import MESURE, LiveContextState, Observation
    etat = LiveContextState("s1").add(
        Observation(subject="speaker", status=MESURE, modality="audio",
                    value=0.2, provider="p1"),
        Observation(subject="speaker", status=MESURE, modality="audio",
                    value=0.8, provider="p2"))
    conflits = etat.conflicts()
    assert len(conflits) == 1 and conflits[0]["resolved"] is False
    assert {o.value for o in etat.by_subject("speaker")} == {0.2, 0.8}
    return _verifie(conflict_recorded=True, averaged=False,
                    values_survive=[0.2, 0.8])


def _c04() -> Dict[str, Any]:
    """Une observation répétée n'est jamais promue."""
    from .state import MESURE, LiveContextState, Observation
    etat = LiveContextState("s1")
    for _ in range(10):
        etat = etat.add(Observation(subject="speaker", status=MESURE,
                                    modality="audio", value="A"))
    assert etat.as_dict()["promoted"] is False
    assert all(o.status == MESURE for o in etat.observations)
    return _verifie(repetitions=10, promoted=False)


# ---------------------------------------------------------------------------
# 5 à 7 : la surface d'entrée, mesurée
# ---------------------------------------------------------------------------

def _c05() -> Dict[str, Any]:
    """Les huit entrées de §7 sont sondées, et chaque absence porte son constat."""
    from .capture import ENTREES, capture_surface
    surface = capture_surface()
    assert surface["available_count"] + surface["absent_count"] == len(ENTREES)
    for manquante in surface["absent"]:
        assert manquante["reason"].strip()
    if surface["absent"]:
        return _bloque(
            missing=", ".join(m["input"] for m in surface["absent"]),
            reported="chaque absence porte le chemin ou la variable cherchée",
            available=surface["available"])
    return _verifie(all_inputs_present=True)          # pragma: no cover


def _c06() -> Dict[str, Any]:
    """Aucun score et aucun booléen global ne remplace le détail."""
    from .capture import capture_surface
    surface = capture_surface()
    assert surface["score"] is None
    assert not any(isinstance(v, bool) for v in surface.values())
    return _verifie(score=None, global_boolean=False)


def _c07() -> Dict[str, Any]:
    """Les modalités disponibles sont déterminées dynamiquement (§7)."""
    from .capture import available_modalities, probe
    modalites = available_modalities()
    assert modalites == sorted(set(modalites))
    return _verifie(modalities=modalites,
                    microphone_state=probe("microphone").status)


# ---------------------------------------------------------------------------
# 8 à 11 : la fusion
# ---------------------------------------------------------------------------

def _c08() -> Dict[str, Any]:
    """Un flux muet contribue ABSENT, jamais du silence."""
    from .fusion import FLUX, fuse
    from .state import ABSENT
    etat = fuse("s1", {})
    absents = [o for o in etat.observations if o.status == ABSENT]
    assert len(absents) == len(FLUX)
    assert all(o.detail.strip() for o in absents)
    return _verifie(streams=len(FLUX), silent_streams_recorded=len(absents))


def _c09() -> Dict[str, Any]:
    """Non branché et branché-muet sont deux absences distinctes."""
    from .fusion import missing_streams
    manquants = {m["stream"]: m for m in missing_streams({"screen": []})}
    assert manquants["screen"]["declared"] is True
    assert manquants["audio"]["declared"] is False
    assert manquants["screen"]["reason"] != manquants["audio"]["reason"]
    return _verifie(declared_but_silent="screen", never_wired="audio")


def _c10() -> Dict[str, Any]:
    """Une observation versée dans le mauvais flux est refusée."""
    from .fusion import FusionRefused, fuse
    from .state import MESURE, Observation
    ecran = Observation(subject="screen_text", status=MESURE,
                        modality="screen", value="Slack")
    try:
        fuse("s1", {"audio": [ecran]})
    except FusionRefused:
        return _verifie(mismatched_stream_refused=True)
    raise AssertionError("Un flux mal branché a été accepté.")  # pragma: no cover


def _c11() -> Dict[str, Any]:
    """La corroboration compte les voix sans classer par nombre."""
    from .fusion import corroboration, fuse
    from .state import MESURE, Observation

    def _o(valeur, fournisseur):
        return Observation(subject="speaker", status=MESURE, modality="audio",
                           value=valeur, provider=fournisseur)

    etat = fuse("s1", {"speakers": [_o("ZZZ", "p1"), _o("ZZZ", "p2"),
                                    _o("AAA", "p3")]})
    resultat = corroboration(etat, "speaker")
    assert resultat["ranked_by_count"] is False
    assert [v["value"] for v in resultat["values"]] == ["'AAA'", "'ZZZ'"]
    assert resultat["confidence"] is None
    return _verifie(ranked_by_count=False, confidence_derived=False)


# ---------------------------------------------------------------------------
# 12 à 15 : locuteurs et langues
# ---------------------------------------------------------------------------

def _c12() -> Dict[str, Any]:
    """Aucun locuteur n'est numéroté, et la diarisation dit son état."""
    from .speakers import diarization_state, speakers_report
    import src.live_context.speakers as speakers
    exposees = [n for n in dir(speakers) if not n.startswith("_")]
    assert not any("number" in n or "assign" in n for n in exposees)
    assert speakers_report()["numbers_speakers"] is False
    etat = diarization_state()
    if etat["state"] == "ABSENT":
        return _bloque(missing="diarisation",
                       reported=etat["measured_reason"],
                       numbers_speakers=False,
                       declared_reason=etat["declared_reason"][:80])
    return _verifie(diarization=etat["modules_found"])  # pragma: no cover


def _c13() -> Dict[str, Any]:
    """Zéro tour de parole n'existe pas : sans locuteur, `turns` vaut None."""
    from src.creative.voice.scene import AudioSegment
    from .speakers import turn_taking
    segments = [AudioSegment(segment_id=f"s{i}", start=i, end=i + 1,
                             original_audio_path="/tmp/a.wav")
                for i in range(3)]
    resultat = turn_taking(segments)
    assert resultat["turns"] is None
    assert resultat["state"] == "NOT_MEASURED"
    return _verifie(turns=None, zero_never_returned=True,
                    coverage=resultat["coverage"])


def _c14() -> Dict[str, Any]:
    """Une langue sans confiance est DECLARED, jamais MEASURED."""
    from src.creative.voice.scene import AudioSegment
    from .languages import language_observation
    from .state import DECLARE, MESURE
    sans = AudioSegment(segment_id="s1", start=0, end=1,
                        original_audio_path="/tmp/a.wav", language="wo")
    avec = AudioSegment(segment_id="s2", start=1, end=2,
                        original_audio_path="/tmp/a.wav", language="wo",
                        language_confidence=0.9)
    assert language_observation(sans).status == DECLARE
    assert language_observation(avec).status == MESURE
    return _verifie(without_confidence=DECLARE, with_confidence=MESURE)


def _c15() -> Dict[str, Any]:
    """Aucune traduction n'est fabriquée : l'absence est rendue, pas une phrase."""
    from src.creative.voice.scene import AudioSegment
    from .languages import languages_report, translation_observation
    from .state import ABSENT
    segment = AudioSegment(segment_id="s1", start=0, end=1,
                           original_audio_path="/tmp/a.wav")
    observation = translation_observation(segment, "fr")
    assert observation.status == ABSENT and observation.value is None
    assert languages_report()["translation_available"] is False
    return _bloque(missing="traduction d'énoncé",
                   reported=observation.detail[:120],
                   sentence_returned=False)


CAS: List[GoldenCase] = [
    GoldenCase(1, "ABSENT n'est pas UNKNOWN",
               "Une absence porte son constat ; une inconnue n'a pas à se "
               "justifier.", _c01),
    GoldenCase(2, "Une confiance porte sa base",
               "Un chiffre sans méthode se comporte comme une mesure sans en "
               "être une.", _c02),
    GoldenCase(3, "Un désaccord est enregistré",
               "Une moyenne effacerait l'information qui compte.", _c03),
    GoldenCase(4, "Rien n'est promu",
               "Une observation répétée reste ce qu'elle est.", _c04),
    GoldenCase(5, "Les huit entrées sont sondées",
               "Chaque absence nomme le chemin ou la variable cherchée.", _c05),
    GoldenCase(6, "Aucun score de capture",
               "Un booléen global n'apprend pas quelle entrée manque.", _c06),
    GoldenCase(7, "Les modalités sont dynamiques",
               "§7 demande de les déterminer, pas de les déclarer.", _c07),
    GoldenCase(8, "Un flux muet contribue ABSENT",
               "Le silence se lirait comme « rien à signaler ».", _c08),
    GoldenCase(9, "Deux absences distinctes",
               "Non branché et branché-muet n'appellent pas la même action.",
               _c09),
    GoldenCase(10, "Un flux mal branché est refusé",
               "Il produirait un état crédible et faux.", _c10),
    GoldenCase(11, "La corroboration ne classe pas",
               "Classer par nombre de voix serait arbitrer sans le dire.",
               _c11),
    GoldenCase(12, "Aucun locuteur n'est numéroté",
               "SPEAKER_1 découpé au hasard a la forme d'une diarisation.",
               _c12),
    GoldenCase(13, "Zéro tour n'existe pas",
               "None dit que personne n'a compté ; zéro affirmerait le "
               "silence.", _c13),
    GoldenCase(14, "Une langue affirmée n'est pas mesurée",
               "0,3 rapporté comme un fait ferait traduire depuis la mauvaise "
               "langue.", _c14),
    GoldenCase(15, "Aucune traduction fabriquée",
               "Ce dépôt ne traduit pas d'énoncé, et le dit.", _c15),
]


def run_all() -> Dict[str, Any]:
    """
    Exécute les scénarios contre le code vivant.

    Returns:
        Un résultat par cas, les comptes par verdict, et la note qui dit ce que
        `BLOCKED` signifie. **Aucun cas n'est sauté** : un cas qui ne peut pas
        aboutir rend `BLOCKED` ou `NOT_APPLICABLE` en le disant.
    """
    resultats: List[Dict[str, Any]] = []
    for cas in CAS:
        try:
            issue = cas.run()
        except AssertionError as erreur:               # pragma: no cover
            issue = {"verdict": "FAILED", "error": str(erreur)}
        resultats.append({"number": cas.number, "title": cas.title,
                          "invariant": cas.invariant, **issue})

    comptes = {verdict: sum(1 for r in resultats if r["verdict"] == verdict)
               for verdict in VERDICTS}
    echecs = [r["number"] for r in resultats if r["verdict"] == "FAILED"]
    return {
        "cases": resultats,
        "count": len(resultats),
        "counts": comptes,
        "failed": echecs,
        "note": (
            "`VERIFIED` veut dire « l'invariant est vérifié contre le code "
            "vivant ». `BLOCKED` veut dire « la capacité manque et la "
            "plateforme le rapporte au lieu d'inventer » — c'est une "
            "assertion, pas un test sauté. Aucun cas n'ouvre de périphérique, "
            "n'écrit sur le disque ni n'atteint le réseau."
        ),
    }
