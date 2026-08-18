"""
Les vingt-cinq scénarios de la directive, exécutés pour de vrai (C17, §62–§64).

## Ce qu'un scénario d'or peut honnêtement affirmer ici

§63 énumère vingt-cinq scénarios, du « texte → scène cinématographique » au
« provenance d'une référence ». La tentation est d'écrire vingt-cinq tests qui
affirment un résultat — *la vidéo est cohérente*, *l'identité est préservée*.
Aucun ne pourrait s'exécuter : rien ne génère sur cette machine. Et les écrire
quand même en figeant une valeur plausible est la faute que ce dépôt a déjà
payée quatre fois — `test_calendar_tool.py` affirmait le titre d'une réunion que
personne n'avait planifiée.

Alors chaque scénario porte ici **l'invariant qu'il protège**, et un seul de
deux verdicts :

| Verdict | Ce qu'il affirme |
|---|---|
| `VERIFIED` | L'invariant est vérifié **contre le code vivant**, maintenant |
| `BLOCKED` | La capacité manque — et la plateforme **le rapporte** au lieu d'inventer |

Un `BLOCKED` n'est donc pas un test sauté. C'est une assertion : *quand la
capacité manque, rien de plausible n'est rendu*. C'est précisément le
comportement qu'une plateforme d'IA perd en premier, et le seul que ces
scénarios peuvent réellement défendre avant qu'un GPU existe.

## Ce qu'ils ne sont pas

Ce ne sont pas des exécutions de bout en bout. Aucune vidéo n'est produite,
aucune identité mesurée, aucune parole transcrite. Le dire ici évite qu'un
lecteur pressé prenne « 25 scénarios, 0 échec » pour « la chaîne créative
fonctionne ».

## §62 et la consigne qui ne se négocie pas

*« Large model downloads must NOT be required for ordinary unit tests. »* Aucun
scénario ici ne télécharge, ne contacte le réseau, ni n'attend un service
externe. Ils lisent des registres, appellent des fonctions pures et
interrogent des sondes locales — tous se terminent en millisecondes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List

#: Les deux verdicts. Deux, jamais trois : « ignoré » n'existe pas ici, parce
#: qu'un scénario ignoré ne défend rien.
VERIFIE = "VERIFIED"
BLOQUE = "BLOCKED"
VERDICTS = (VERIFIE, BLOQUE)


@dataclass(frozen=True)
class GoldenScenario:
    """
    Un scénario de §63 et l'invariant qu'il défend.

    Attributes:
        number: Son numéro dans la directive.
        title: Ce que la directive en dit.
        invariant: Ce qui est réellement affirmé ici.
        check: La fonction qui l'éprouve, sans réseau ni modèle.
    """

    number: int
    title: str
    invariant: str
    check: Callable[[], Dict[str, Any]]


def _verifie(**preuve: Any) -> Dict[str, Any]:
    """Un invariant tenu, avec ce qui l'atteste."""
    return {"verdict": VERIFIE, "evidence": preuve}


def _bloque(missing: str, reported: Any, **preuve: Any) -> Dict[str, Any]:
    """Une capacité absente, **rapportée** au lieu d'être comblée."""
    return {"verdict": BLOQUE, "missing": missing, "reported": reported,
            "evidence": preuve}


# --- 1 à 3 : génération, et ce qu'elle répond quand elle ne peut pas ---------

def _registre_declare():
    """Le registre des fournisseurs réellement déclarés."""
    from .providers import ProviderRegistry, adapt_declared
    from .research import load_research
    registre = ProviderRegistry()
    for fournisseur in adapt_declared(load_research().get("candidates") or []):
        registre.register(fournisseur)
    return registre


def _s01() -> Dict[str, Any]:
    """Texte → scène : aucun fournisseur dégagé, et rien n'est rendu."""
    from .providers import AUCUN, CreativeRequest
    from .routing import route
    resultat = route(_registre_declare(), CreativeRequest(task="text_to_video"))
    assert resultat["status"] == AUCUN, "Un fournisseur aurait été retenu."
    return _bloque("un fournisseur de génération vidéo", resultat["status"],
                   reason=resultat["reason"][:80])


def _s02() -> Dict[str, Any]:
    """Entités non humaines : le type n'est pas restreint à la personne."""
    from .reference.entity import reference_report
    types = reference_report()["entity_types"]
    assert len(types) > 3 and "human" in types
    non_humains = [t for t in types if t != "human"]
    assert non_humains, "Seul l'humain serait représentable."
    return _verifie(entity_types=len(types), non_human=len(non_humains))


def _s03() -> Dict[str, Any]:
    """Audio multi-locuteurs : aucun locuteur n'est inventé."""
    from .voice.scene import pipeline_state
    etat = pipeline_state()
    bloquees = {e["stage"]: e for e in etat["stages"] if e["state"] == "BLOCKED"}
    assert "speaker_diarization" in bloquees
    return _bloque("séparation de locuteurs",
                   bloquees["speaker_diarization"]["state"],
                   first_block=etat["first_block"])


# --- 4 à 7 : les langues, et l'enregistrement d'origine ----------------------

def _langue_preservee(code: str) -> Dict[str, Any]:
    """Un enregistrement dans cette langue est nommable et jamais remplacé."""
    from .language.registry import is_declared
    from .voice.scene import AudioSegment, build_scene, voice_plan
    assert is_declared(code), f"« {code} » n'est pas nommable."
    scene = build_scene([AudioSegment("s1", 0.0, 2.0, "/tmp/parole.wav",
                                      language=code, language_confidence=0.9)])
    plan = voice_plan(scene)
    assert plan["path"] == "PRESERVE_ORIGINAL", "La voix aurait été remplacée."
    synthese = voice_plan(scene, synthesise=True)
    assert synthese["status"] == "NOT_AVAILABLE", "Une voix aurait été inventée."
    return _verifie(language=code, path=plan["path"],
                    synthesis=synthese["status"])


def _s07() -> Dict[str, Any]:
    """Wolof + français : l'alternance est structurée, jamais réduite."""
    from .language.switching import switching_report
    from .voice.scene import AudioSegment
    rapport = switching_report([
        AudioSegment("s1", 0.0, 2.0, "/tmp/a.wav", language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
        AudioSegment("s2", 2.0, 3.0, "/tmp/a.wav", language="fr",
                     language_confidence=0.9, speaker_id="sp1"),
        AudioSegment("s3", 3.0, 5.0, "/tmp/a.wav", language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
    ])
    assert rapport["code_switching"] is True
    assert "dominant_language" not in rapport, "Une langue dominante réduirait."
    assert rapport["intra_segment_switching"] == "UNKNOWN"
    return _verifie(switches=rapport["switch_count"],
                    languages=rapport["languages"])


# --- 8 à 13 : références, entités, monde, foule -----------------------------

def _s08() -> Dict[str, Any]:
    """Plusieurs images pour une entité : l'analyse déclare ce qu'elle sait."""
    from .reference.ingestion import ingestion_report
    rapport = ingestion_report()
    assert rapport["rules"], "Aucune règle d'ingestion déclarée."
    if not rapport["image_analysis_available"]:
        return _bloque("analyse d'image", rapport["image_analysis_available"])
    # Ce qui est mesurable est déclaré, et ce qui ne l'est pas porte son motif.
    assert rapport["measurable"], "Rien ne serait mesurable, sans le dire."
    return _verifie(measurable=len(list(rapport["measurable"])),
                    blocked=len(list(rapport["blocked"])))


def _s09() -> Dict[str, Any]:
    """Référence vidéo : le décodage vidéo manque, et c'est dit."""
    from .reference.ingestion import ingestion_report
    sondes = ingestion_report()["probes"]
    indisponibles = [nom for nom, etat in sondes.items() if etat != "AVAILABLE"]
    assert indisponibles, "Toutes les sondes seraient disponibles."
    return _bloque("décodage et analyse vidéo", indisponibles)


def _s10() -> Dict[str, Any]:
    """Plusieurs personnes réelles : la génération manque, le consentement non."""
    from .reference.consent import consent_report
    rapport = consent_report()
    assert rapport["scopes"] and rapport["states"]
    return _bloque("génération multi-entités", "NO_PROVIDER",
                   consent_scopes=len(rapport["scopes"]))


def _s11() -> Dict[str, Any]:
    """Entité récurrente : la mémoire sépare privé et partagé."""
    from .reference.memory import reference_memory_report
    niveaux = reference_memory_report()["privacy_levels"]
    assert "PRIVATE" in niveaux, "Le privé ne serait pas un niveau déclaré."
    return _verifie(privacy_levels=niveaux)


def _s12() -> Dict[str, Any]:
    """Environnement récurrent : mémoire de monde distincte du personnage."""
    from .world import world_report
    rapport = world_report()
    assert rapport["rules"] and rapport["origins"]
    return _verifie(fidelities=rapport["fidelities"], origins=rapport["origins"])


def _s13() -> Dict[str, Any]:
    """Entités principales + activité de fond : la fidélité est hiérarchisée."""
    from .crowd import crowd_report
    fidelites = crowd_report()["allowed_fidelities"]
    assert len(fidelites) > 1, "Une foule au même niveau que les héros."
    return _verifie(fidelities=fidelites)


# --- 14 à 18 : continuité, dérive, plans, caméra, format --------------------

def _s14() -> Dict[str, Any]:
    """Continuité multi-plans : trois issues, jamais deux."""
    from .verification import identity_dimensions_here
    dimensions = identity_dimensions_here()
    issues = {d.outcome for d in dimensions}
    assert issues, "Aucune dimension déclarée."
    assert all(d.value is None for d in dimensions
               if d.outcome == "NOT_MEASURABLE"), \
        "Une dimension non mesurable porterait une valeur."
    return _verifie(dimensions=len(dimensions), outcomes=sorted(issues))


def _s15() -> Dict[str, Any]:
    """Dérive d'identité : aucune mesure, donc aucun score."""
    from .verification import identity_dimensions_here
    dimensions = identity_dimensions_here()
    non_mesurables = [d for d in dimensions if d.outcome == "NOT_MEASURABLE"]
    assert non_mesurables, "Une dimension serait mesurable sans mesure."
    assert all(d.missing_capability for d in non_mesurables), \
        "Une dimension non mesurable ne dirait pas ce qui manque."
    return _bloque("une mesure d'identité",
                   [d.dimension for d in non_mesurables][:3],
                   dimensions=len(dimensions))


def _s16() -> Dict[str, Any]:
    """Régénération d'un plan : le plan est une unité adressable."""
    from .direction import direction_report
    etats = direction_report()["shot_states"]
    assert len(etats) > 1, "Un plan n'aurait pas d'état propre."
    return _verifie(shot_states=etats)


def _s17() -> Dict[str, Any]:
    """Mouvement de caméra : structuré, jamais un adjectif ajouté au prompt."""
    from .direction import check_intent, direction_report
    rapport = direction_report()
    assert rapport["movements"] and rapport["shot_sizes"]
    refus = check_intent("une scène cinématographique et dramatique")
    assert refus, "Un adjectif serait passé sans remarque."
    return _verifie(movements=len(rapport["movements"]),
                    shot_sizes=len(rapport["shot_sizes"]))


def _s18() -> Dict[str, Any]:
    """Format vertical : le média porte déjà les formats de diffusion."""
    from .pipelines import PIPELINE_A, plan_pipeline
    plan = plan_pipeline(_registre_declare(), PIPELINE_A)
    assert plan["preserves_original_audio"] is True
    return _bloque("génération vidéo", plan["first_block"],
                   preserves_original_audio=True)


# --- 19 à 22 : repli, langue inconnue, correction, vie privée ---------------

def _s19() -> Dict[str, Any]:
    """Panne de fournisseur : aucun repli silencieux sur le plus proche."""
    from .providers import AUCUN, CreativeRequest
    from .routing import route
    resultat = route(_registre_declare(),
                     CreativeRequest(task="text_to_video", commercial=True))
    assert resultat["status"] == AUCUN
    assert "substitution silencieuse" in resultat["reason"]
    return _verifie(status=resultat["status"], fallback=None)


def _s20() -> Dict[str, Any]:
    """Langue inconnue : aucune interprétation fabriquée."""
    from .voice.scene import AudioSegment, build_scene
    scene = build_scene([AudioSegment("s1", 0.0, 2.0, "/tmp/a.wav")])
    assert scene["segments_without_language"] == ["s1"]
    assert scene["segments"][0]["transcript"] is None, "Un texte aurait été mis."
    assert scene["original_audio_preserved"] is True
    return _verifie(without_language=scene["segments_without_language"],
                    transcript=None)


def _s21() -> Dict[str, Any]:
    """Correction d'utilisateur : une observation, pas un fait global."""
    from .language.knowledge import LanguageKnowledgeBase, merge_correction
    from .language.loop import observe_from_interaction
    base = LanguageKnowledgeBase()
    origine = observe_from_interaction(base, "wo", "dëkk", by="awa",
                                       meaning="habiter")
    correction = merge_correction(base, origine.observation_id, by="ndeye",
                                  meaning="village")
    assert base.get(origine.observation_id).meaning == "habiter", \
        "L'entrée d'origine aurait été écrasée."
    assert correction.status == "OBSERVED", "La correction serait déjà un fait."
    return _verifie(original_intact=True, correction_status=correction.status)


def _s22() -> Dict[str, Any]:
    """Conversation privée : rien ne rejoint le global tout seul."""
    from .language.knowledge import LanguageKnowledgeBase
    from .language.loop import observe_from_interaction
    base = LanguageKnowledgeBase()
    for observateur in ("awa", "moussa", "fatou", "ibou"):
        observe_from_interaction(base, "wo", "dëkk", by=observateur,
                                 meaning="habiter")
    assert base.hypotheses("wo", "dëkk") == [], "Le privé aurait fui."
    prives = base.private_entries()
    assert prives and prives[0].status == "CORROBORATED"
    return _verifie(global_visible=0, private=len(prives),
                    status=prives[0].status)


# --- 23 à 25 : consentement, suppression, provenance ------------------------

def _s23() -> Dict[str, Any]:
    """Restriction de consentement : la plateforme ne consent pour personne."""
    from .reference.consent import consent_report, is_platform_identity
    assert is_platform_identity("galsen"), "La plateforme pourrait consentir."
    rapport = consent_report()
    assert "REVOKED" in rapport["states"]
    return _verifie(scopes=rapport["scopes"], states=rapport["states"])


def _s24() -> Dict[str, Any]:
    """Suppression d'une référence : les travaux concernés sont retrouvables."""
    from .jobs import CreativeJobBook
    registre = CreativeJobBook()
    vise = registre.submit(user="awa", task="text_to_video", provider_id="p",
                           references=("ref-1",), uses_references=True)
    registre.submit(user="awa", task="text_to_video", provider_id="p",
                    references=("ref-2",), uses_references=True)
    trouves = registre.jobs_using("ref-1")
    assert trouves == [vise.job_id], "La révocation ne trouverait pas sa cible."
    return _verifie(jobs_found=len(trouves))


def _s25() -> Dict[str, Any]:
    """Provenance : un artefact nomme ce qui l'a conditionné."""
    from .jobs import CreativeJobBook, fingerprint
    registre = CreativeJobBook()
    travail = registre.submit(user="awa", task="text_to_video",
                              provider_id="wan", references=("ref-1",),
                              uses_references=True, model="wan-2.1")
    scelle = registre.record_artifact(travail.job_id, "/out/a.webm",
                                      sha256=fingerprint("prompt"))
    provenance = scelle.provenance.as_dict()
    assert provenance["references"] == ["ref-1"]
    assert provenance["inputs_sha256"], "L'artefact n'aurait pas d'empreinte."
    assert provenance["seed"] is None, "Une graine aurait été inventée."
    return _verifie(references=provenance["references"],
                    has_fingerprint=True, seed=None)


#: Les vingt-cinq scénarios de §63, dans l'ordre du texte.
SCENARIOS: List[GoldenScenario] = [
    GoldenScenario(1, "Text → realistic cinematic scene",
                   "Sans fournisseur dégagé, rien n'est rendu.", _s01),
    GoldenScenario(2, "Text → non-human entities",
                   "Une entité n'est pas nécessairement une personne.", _s02),
    GoldenScenario(3, "Audio → multi-speaker scene",
                   "Aucun locuteur n'est inventé faute de diarisation.", _s03),
    GoldenScenario(4, "Wolof audio → original audio preserved",
                   "La voix d'origine est le chemin par défaut.",
                   lambda: _langue_preservee("wo")),
    GoldenScenario(5, "Serer audio → original audio preserved",
                   "Le sérère est nommable, et sa voix préservée.",
                   lambda: _langue_preservee("srr")),
    GoldenScenario(6, "Lingala audio → original audio preserved",
                   "Le lingala est nommable, et sa voix préservée.",
                   lambda: _langue_preservee("ln")),
    GoldenScenario(7, "Wolof + French → code switching",
                   "L'alternance est structurée, jamais réduite.", _s07),
    GoldenScenario(8, "Multiple reference images → one entity",
                   "L'analyse déclare ce qu'elle sait et ce qui manque.", _s08),
    GoldenScenario(9, "Video reference → entity recreation",
                   "Le décodage vidéo manque, et c'est rapporté.", _s09),
    GoldenScenario(10, "Multiple real-person references → multi-entity scene",
                   "Le consentement existe ; la génération non.", _s10),
    GoldenScenario(11, "Recurring reference entity",
                   "Le privé est un niveau déclaré, pas un défaut tacite.",
                   _s11),
    GoldenScenario(12, "Recurring environment",
                   "La mémoire de monde est distincte du personnage.", _s12),
    GoldenScenario(13, "Main entities + background activity",
                   "La fidélité est hiérarchisée, pas uniforme.", _s13),
    GoldenScenario(14, "Multi-shot continuity",
                   "Une dimension non mesurable ne porte pas de valeur.", _s14),
    GoldenScenario(15, "Identity drift detection",
                   "Aucune mesure d'identité, donc aucun score.", _s15),
    GoldenScenario(16, "Shot-level regeneration",
                   "Un plan a son propre état, donc il est adressable.", _s16),
    GoldenScenario(17, "Camera movement",
                   "La direction est structurée, pas un adjectif ajouté.",
                   _s17),
    GoldenScenario(18, "Vertical social video",
                   "La voix d'origine survit au format ; la vidéo manque.",
                   _s18),
    GoldenScenario(19, "Provider failure → fallback",
                   "Aucun repli silencieux sur le fournisseur voisin.", _s19),
    GoldenScenario(20, "Unknown language → no fabricated interpretation",
                   "Sans langue identifiée, rien n'est transcrit.", _s20),
    GoldenScenario(21, "User correction → candidate observation",
                   "Une correction n'écrase pas l'entrée d'origine.", _s21),
    GoldenScenario(22, "Private conversation → not global knowledge",
                   "Rien ne rejoint le global sans consentement.", _s22),
    GoldenScenario(23, "Reference consent restriction",
                   "La plateforme ne consent pour personne.", _s23),
    GoldenScenario(24, "Reference deletion",
                   "Les travaux d'une référence sont retrouvables.", _s24),
    GoldenScenario(25, "Reference provenance",
                   "Un artefact nomme ce qui l'a conditionné.", _s25),
]


def run_scenario(number: int) -> Dict[str, Any]:
    """
    Exécute un scénario et rend son verdict.

    Args:
        number: Son numéro dans §63.

    Returns:
        Le verdict, l'invariant défendu et ce qui l'atteste.

    Raises:
        KeyError: Numéro inconnu.
    """
    par_numero = {scenario.number: scenario for scenario in SCENARIOS}
    scenario = par_numero[number]
    resultat = scenario.check()
    return {"number": scenario.number, "title": scenario.title,
            "invariant": scenario.invariant, **resultat}


def run_all() -> Dict[str, Any]:
    """
    Exécute les vingt-cinq scénarios.

    Returns:
        Les verdicts et leur répartition. **Aucun n'est ignoré** : un scénario
        sauté ne défend rien, et un compte qui inclut des sauts se lit comme
        une couverture.

    Note:
        Ce ne sont pas des exécutions de bout en bout. Aucune vidéo n'est
        produite, aucune identité mesurée, aucune parole transcrite — le
        rappeler ici évite qu'un lecteur prenne « 25 scénarios, 0 échec » pour
        « la chaîne créative fonctionne ».
    """
    resultats = [run_scenario(scenario.number) for scenario in SCENARIOS]
    verifies = [r["number"] for r in resultats if r["verdict"] == VERIFIE]
    bloques = [r["number"] for r in resultats if r["verdict"] == BLOQUE]
    return {
        "scenarios": resultats,
        "total": len(resultats),
        "verified": verifies,
        "blocked": bloques,
        "skipped": [],
        "note": (
            "`VERIFIED` veut dire « l'invariant est vérifié contre le code "
            "vivant ». `BLOCKED` veut dire « la capacité manque et la "
            "plateforme le rapporte au lieu d'inventer » — c'est une "
            "assertion, pas un test sauté. Aucun scénario ne produit de "
            "vidéo : la chaîne complète attend un GPU et un fournisseur "
            "dégagé."
        ),
    }


def language_coverage() -> Dict[str, Any]:
    """
    §64 : la même architecture porte-t-elle toutes ces langues ?

    Returns:
        Pour chaque langue de validation, le fait qu'elle est **nommable** —
        et le rappel que nommable n'est ni comprise ni parlée. Aucune
        architecture par langue n'existe : c'est une ligne de données, et la
        vérification consiste à montrer qu'aucune n'est traitée à part.
    """
    from .language.registry import coverage_report, language_matrix
    couverture = coverage_report()
    matrice = language_matrix()
    return {
        "validation_languages": couverture["count"],
        "all_nameable": all(ligne["nameable"]
                            for ligne in couverture["validation_languages"]),
        "fully_carried": couverture["fully_carried"],
        "understood": matrice["understood"],
        "speakable": matrice["speakable"],
        "per_language_architecture": False,
        "note": (
            "Toutes les langues passent par le même registre et le même "
            "chemin de code : §64 demande qu'aucune n'ait d'architecture "
            "propre, et ce qui le prouve est qu'aucune n'apparaît dans le "
            "code. Nommable n'est ni comprise ni parlée — les deux dernières "
            "colonnes sont vides ici."
        ),
    }
