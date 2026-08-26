"""
Les dix épreuves de GalSen IA, passées par le **vrai** chemin `/chat`.

## Ce qui distingue ce banc de `benchmark.py`

`src/model_engine/benchmark.py` interroge un fournisseur directement : il mesure
un modèle. Celui-ci passe par `POST /chat`, donc par **toute la chaîne** —
planner, agents, ancrage, rédaction, critique déterministe, reprise éventuelle.
Il ne mesure pas un modèle : il mesure ce qu'un utilisateur reçoit.

La différence compte pour six des dix épreuves. Un calcul faux n'est pas jugé
sur ce que le modèle a écrit d'abord, mais sur ce qui sort **après** la boucle
de délibération (ADR-041) — c'est-à-dire après qu'un contrôle arithmétique
déterministe a eu l'occasion de le renvoyer.

## Trois issues, jamais deux

`PASS`, `FAIL`, `NOT_CHECKED`. La troisième existe parce que quatre épreuves
n'ont pas de bonne réponse vérifiable par machine : une explication de l'IA en
français simple, une stratégie de chantier, un exemple d'entreprise, une version
wolof. Leur inventer un score serait fabriquer une mesure ; leur réponse est
**enregistrée pour lecture humaine**, et le rapport dit qu'elle ne l'a pas été.

Un banc qui rendrait `PASS`/`FAIL` sur ces quatre-là afficherait dix résultats
au lieu de six, et quatre d'entre eux seraient des inventions.

## Sans modèle, aucun chiffre

Chaque épreuve rend `NOT_EXECUTED` avec son motif si aucun modèle n'a rédigé.
Le taux global vaut alors `None`, jamais `0.0` : un taux nul se compare, une
absence non.
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

#: Les trois issues d'une épreuve.
PASS = "PASS"
FAIL = "FAIL"
NON_VERIFIE = "NOT_CHECKED"
NON_EXECUTE = "NOT_EXECUTED"


def _nombres(texte: str) -> List[int]:
    """
    Extrait les entiers d'un texte, séparateurs de milliers compris.

    « 1 440 000 », « 1.440.000 » et « 1440000 » désignent le même nombre ; ne
    reconnaître que le dernier ferait échouer une réponse correcte pour une
    question de typographie.
    """
    normalise = re.sub(r"(?<=\d)[  .,](?=\d{3}\b)", "", texte or "")
    return [int(n) for n in re.findall(r"\d+", normalise)]


def _contient_nombre(attendu: int) -> Callable[[str], bool]:
    """Contrôle : le nombre attendu apparaît dans la réponse."""
    return lambda texte: attendu in _nombres(texte)


def _contient(*termes: str) -> Callable[[str], bool]:
    """Contrôle : l'un des termes apparaît, casse ignorée."""
    def controle(texte: str) -> bool:
        minuscules = (texte or "").lower()
        return any(t.lower() in minuscules for t in termes)
    return controle


@dataclass(frozen=True)
class Epreuve:
    """
    Une des dix épreuves.

    Attributes:
        identifiant: `TEST-01` … `TEST-10`.
        titre: Ce que l'épreuve cherche.
        message: Envoyé tel quel à `/chat`.
        controle: Décide `PASS`/`FAIL`. `None` quand la réponse n'a pas de
            vérité vérifiable par machine — l'épreuve rend alors `NOT_CHECKED`.
        attendu: Ce que le contrôle cherche, pour le rapport.
    """

    identifiant: str
    titre: str
    message: str
    controle: Optional[Callable[[str], bool]] = None
    attendu: str = ""


#: Les dix épreuves, dans l'ordre du brief du propriétaire.
EPREUVES: tuple = (
    Epreuve(
        "TEST-01", "Général",
        "Explique ce qu'est l'intelligence artificielle, en français simple.",
        attendu="Aucune vérité vérifiable par machine : lecture humaine.",
    ),
    Epreuve(
        "TEST-02", "Logique",
        "Un père a 4 fils. Chaque fils a une sœur. Combien d'enfants "
        "y a-t-il au total ? Explique ton raisonnement.",
        _contient_nombre(5),
        "5 enfants — la sœur est commune aux quatre frères, elle ne se compte "
        "pas quatre fois.",
    ),
    Epreuve(
        "TEST-03", "Calcul",
        "Une entreprise achète 320 plaques de BA13 à 4 500 FCFA l'unité. "
        "Calcule le total et vérifie-le.",
        _contient_nombre(1440000),
        "1 440 000 FCFA.",
    ),
    Epreuve(
        "TEST-04", "Raisonnement complexe",
        "Une entreprise de construction reçoit un chantier de cloisons sèches "
        "de 800 m² avec un délai court, un budget limité et plusieurs "
        "contraintes. Construis une stratégie d'exécution étape par étape et "
        "identifie les risques majeurs.",
        attendu="Aucune vérité vérifiable par machine : lecture humaine.",
    ),
    Epreuve(
        "TEST-05", "Code",
        "Écris une fonction Python qui calcule le coût total de matériaux BA13. "
        "Vérifie le code avant de donner la réponse finale.",
        _contient("def "),
        "Une définition de fonction Python.",
    ),
    Epreuve(
        "TEST-06", "Connaissance",
        "Combien de régions administratives compte le Sénégal ? "
        "Indique la source utilisée.",
        _contient_nombre(14),
        "14 régions — la base de la plateforme les tient de geoBoundaries.",
    ),
    Epreuve(
        "TEST-07", "Auto-vérification",
        "Calcule 187 × 46, puis vérifie ton résultat de façon indépendante "
        "avant de présenter la réponse finale.",
        _contient_nombre(8602),
        "8 602.",
    ),
    Epreuve(
        "TEST-08", "Contexte sénégalais",
        "Donne un exemple professionnel impliquant une PME sénégalaise. "
        "Distingue clairement les faits vérifiés des hypothèses à vérifier.",
        attendu="Aucune vérité vérifiable par machine : lecture humaine.",
    ),
    Epreuve(
        "TEST-09", "Langue",
        "Réponds en français, puis donne une version en wolof. "
        "N'invente aucun vocabulaire que tu ne peux pas vérifier.",
        attendu="Aucune vérité vérifiable par machine : lecture humaine, et "
                "le wolof demande un locuteur.",
    ),
    Epreuve(
        "TEST-10", "Raisonnement difficile",
        "Un chantier avance de 45 m² par jour avec 3 ouvriers. Le client "
        "demande de finir 800 m² en 4 jours. Combien d'ouvriers faut-il ? "
        "Décompose, vérifie chaque étape, corrige toute erreur détectée, "
        "puis donne la conclusion vérifiée.",
        _contient_nombre(14),
        "14 ouvriers — 800/4 = 200 m²/jour, 45/3 = 15 m² par ouvrier, "
        "200/15 = 13,3 arrondi au supérieur.",
    ),
)


@dataclass
class ResultatEpreuve:
    """Ce qu'une épreuve a donné, avec de quoi la relire."""

    identifiant: str
    titre: str
    issue: str
    latence_secondes: float = 0.0
    reponse: str = ""
    modele: Optional[str] = None
    generee: bool = False
    ancrage: str = ""
    reprises: int = 0
    arret: str = ""
    constats: List[str] = field(default_factory=list)
    motif: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat, réponse complète comprise."""
        return {
            "id": self.identifiant,
            "title": self.titre,
            "outcome": self.issue,
            "latency_seconds": round(self.latence_secondes, 3),
            "model_used": self.modele,
            "generated": self.generee,
            "grounding": self.ancrage,
            "retries": self.reprises,
            "stop_reason": self.arret,
            "findings": list(self.constats),
            "reason": self.motif,
            "answer": self.reponse,
        }


@dataclass
class RapportEvaluation:
    """Un passage complet des dix épreuves."""

    modele: str
    backend: str = ""
    quantisation: str = "unknown"
    materiel: str = ""
    resultats: List[ResultatEpreuve] = field(default_factory=list)
    duree_totale_secondes: float = 0.0

    @property
    def verifiables(self) -> List[ResultatEpreuve]:
        """Les épreuves dont l'issue a pu être décidée."""
        return [r for r in self.resultats if r.issue in (PASS, FAIL)]

    @property
    def reussites(self) -> int:
        """Combien d'épreuves vérifiables sont réussies."""
        return sum(1 for r in self.verifiables if r.issue == PASS)

    @property
    def taux(self) -> Optional[float]:
        """
        Le taux sur les seules épreuves vérifiables, ou `None`.

        Rapporter un taux sur les dix épreuves compterait quatre `NOT_CHECKED`
        comme des échecs, ce qu'elles ne sont pas.
        """
        if not self.verifiables:
            return None
        return round(self.reussites / len(self.verifiables), 4)

    @property
    def executees(self) -> int:
        """Combien d'épreuves ont réellement atteint un modèle."""
        return sum(1 for r in self.resultats if r.issue != NON_EXECUTE)

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le rapport, avec tout ce qui permet de le comparer."""
        return {
            "model": self.modele,
            "backend": self.backend,
            "quantization": self.quantisation,
            "hardware": self.materiel,
            "trials": len(self.resultats),
            "executed": self.executees,
            "checkable": len(self.verifiables),
            "passed": self.reussites,
            "not_checked": sum(1 for r in self.resultats if r.issue == NON_VERIFIE),
            "not_executed": sum(1 for r in self.resultats if r.issue == NON_EXECUTE),
            "pass_rate": self.taux,
            "total_seconds": round(self.duree_totale_secondes, 3),
            "results": [r.to_dict() for r in self.resultats],
        }


def evaluer(
    appeler_chat: Callable[[str], Dict[str, Any]],
    modele: str = "inconnu",
    backend: str = "",
    quantisation: str = "unknown",
    materiel: str = "",
    epreuves: Sequence[Epreuve] = EPREUVES,
) -> RapportEvaluation:
    """
    Fait passer les épreuves par le vrai chemin de conversation.

    Args:
        appeler_chat: Reçoit un message, rend la charge de `ChatResponse` —
            `answer`, `generated`, `model_used`, `grounding`, `deliberation`.
            Injecté plutôt que construit ici : le harnais doit pouvoir viser
            une application en mémoire **ou** un serveur distant sans changer.
        modele: Nom du modèle attendu, pour la trace.
        backend: `ollama`, `vllm`… pour la trace.
        quantisation: `Q4_K_M`, `Q6_K`… quand elle est connue.
        materiel: Description de la machine.
        epreuves: Les épreuves ; les dix par défaut.

    Returns:
        Le rapport. Une épreuve dont la réponse n'a pas été **générée** rend
        `NOT_EXECUTED` avec son motif : la plateforme a peut-être composé un
        texte, mais aucun modèle ne l'a écrit, et le juger mesurerait le repli.
    """
    rapport = RapportEvaluation(
        modele=modele, backend=backend, quantisation=quantisation, materiel=materiel,
    )
    debut = time.perf_counter()

    for epreuve in epreuves:
        depart = time.perf_counter()
        try:
            charge = appeler_chat(epreuve.message)
        except Exception as erreur:  # noqa: BLE001 — une panne est un résultat
            rapport.resultats.append(ResultatEpreuve(
                identifiant=epreuve.identifiant, titre=epreuve.titre,
                issue=NON_EXECUTE, latence_secondes=time.perf_counter() - depart,
                motif=f"{type(erreur).__name__}: {erreur}",
            ))
            continue

        latence = time.perf_counter() - depart
        resultat = _resultat(epreuve, charge, latence)
        rapport.resultats.append(resultat)

    rapport.duree_totale_secondes = time.perf_counter() - debut
    return rapport


def _resultat(epreuve: Epreuve, charge: Dict[str, Any], latence: float) -> ResultatEpreuve:
    """Traduit une réponse de `/chat` en résultat d'épreuve."""
    reponse = str(charge.get("answer") or "")
    generee = bool(charge.get("generated"))
    deliberation = charge.get("deliberation") or {}
    ancrage = charge.get("grounding") or {}

    resultat = ResultatEpreuve(
        identifiant=epreuve.identifiant, titre=epreuve.titre, issue=NON_EXECUTE,
        latence_secondes=latence, reponse=reponse,
        modele=charge.get("model_used"), generee=generee,
        ancrage=str(ancrage.get("status") or "") if isinstance(ancrage, dict) else "",
        reprises=int(deliberation.get("retries") or 0),
        arret=str(deliberation.get("stop_reason") or ""),
        constats=[
            str(c.get("code")) for c in (deliberation.get("remaining_findings") or [])
            if isinstance(c, dict)
        ],
    )

    if not generee:
        # La plateforme a peut-être composé un texte à partir de ce que les
        # agents ont rapporté. Le juger mesurerait le repli, pas le modèle.
        resultat.motif = str(
            charge.get("generation_unavailable") or "aucun modèle n'a rédigé"
        )
        return resultat

    if epreuve.controle is None:
        resultat.issue = NON_VERIFIE
        resultat.motif = epreuve.attendu
        return resultat

    resultat.issue = PASS if epreuve.controle(reponse) else FAIL
    if resultat.issue == FAIL:
        resultat.motif = f"attendu : {epreuve.attendu}"
    return resultat


def rapport_lisible(rapport: RapportEvaluation) -> str:
    """
    Rend le rapport pour un humain.

    Args:
        rapport: Le rapport à mettre en forme.

    Returns:
        Un texte court. Le taux n'est affiché que s'il existe.
    """
    lignes = [
        "Évaluation GalSen IA — dix épreuves, par le vrai chemin /chat",
        f"  modèle       : {rapport.modele}",
        f"  backend      : {rapport.backend or 'inconnu'}"
        f"   quantisation : {rapport.quantisation}",
        f"  matériel     : {rapport.materiel or 'non déclaré'}",
        f"  exécutées    : {rapport.executees}/{len(rapport.resultats)}",
    ]
    taux = rapport.taux
    lignes.append(
        f"  vérifiables  : {rapport.reussites}/{len(rapport.verifiables)}"
        + (f" ({taux:.0%})" if taux is not None else " (NON MESURABLE)")
    )
    lignes.append(f"  durée totale : {rapport.duree_totale_secondes:.1f} s")
    lignes.append("")

    for resultat in rapport.resultats:
        marque = {PASS: "OK ", FAIL: "ÉCHEC", NON_VERIFIE: "—  ", NON_EXECUTE: "N/A"}
        lignes.append(
            f"  {resultat.identifiant}  {marque.get(resultat.issue, '?'):5s} "
            f"{resultat.titre:24s} {resultat.latence_secondes:6.2f} s"
            + (f"  {resultat.reprises} reprise(s)" if resultat.reprises else "")
        )
        if resultat.motif:
            lignes.append(f"          {resultat.motif}")
    return "\n".join(lignes)
