"""
Un banc d'essai qui tourne **ici**, sans serveur de modèles.

## Pourquoi celui-ci plutôt qu'un banc de modèles

Un banc qui compare des modèles ne peut pas tourner sur cette machine : aucun
GPU, aucun serveur d'inférence, `huggingface.co` refusé par le mandataire. En
écrire un ne produirait que des `NOT_EXECUTED` — un fichier qui décrit une
mesure au lieu de la faire.

Celui-ci mesure la moitié qui est présente : **les critiques**. Ils sont
déterministes, ils tournent en millisecondes, et ce qu'ils attrapent ou laissent
passer décide de ce qu'une reprise peut corriger. Un critique qui rate 40 % des
calculs faux plafonne la boucle entière, quel que soit le modèle branché
derrière.

## Les deux chiffres, et pourquoi les deux

- **Détection** — parmi les cas qui portent un défaut, combien sont attrapés.
- **Fausse alerte** — parmi les cas sains, combien sont signalés à tort.

Le second est le plus important, et c'est celui qu'on oublie de mesurer. Un
critique qui signale tout atteint 100 % de détection et rend la boucle
inutilisable : chaque réponse coûterait une reprise. Rapporter la détection
seule serait donc trompeur, et ce module refuse de le faire.

## Ce qu'il ne mesure pas

La qualité d'une réponse, la qualité d'un modèle, la latence d'une génération.
Il mesure des contrôles sur des cas écrits à la main. C'est peu, et c'est dit.

## Le biais, nommé plutôt que caché

**Les cas et les contrôles sortent de la même main.** Un banc écrit par l'auteur
de ce qu'il mesure se donne facilement 100 %, et la première version de
celui-ci l'a fait — 8 détections sur 8, ce qui ne disait rien du tout.

Quatre cas ont donc été ajoutés que les contrôles **ratent réellement** :
un calcul en toutes lettres, un calcul sans signe égal, un pourcentage, et une
contradiction reformulée. Ils font tomber la détection à environ deux tiers, et
chacun porte le motif de son échec. C'est ce chiffre-là qui est utile : il dit
où sont les trous, et il baissera encore quand quelqu'un ajoutera un cas
auquel personne n'avait pensé. Un banc dont le score ne peut que monter n'est
pas un banc, c'est une décoration.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .critics import critiquer

#: Les cas. Chacun porte le code attendu, ou `None` pour un cas sain.
#:
#: Écrits à la main, et c'est leur limite : ils éprouvent ce que les contrôles
#: visent, pas ce que le monde produit. Un cas qui n'est pas ici n'est pas
#: mesuré — l'ajouter est une ligne.
CAS: tuple = (
    # --- Calculs -----------------------------------------------------------
    {"id": "calc-faux-simple", "texte": "Le total est 2 + 2 = 5.",
     "attendu": "arithmetic_error"},
    {"id": "calc-faux-multiplication", "texte": "Donc 12 × 12 = 148 unités.",
     "attendu": "arithmetic_error"},
    {"id": "calc-faux-soustraction", "texte": "Il reste 100 - 30 = 60 francs.",
     "attendu": "arithmetic_error"},
    {"id": "calc-faux-division", "texte": "On obtient 10 / 4 = 3.",
     "attendu": "arithmetic_error"},
    {"id": "calc-juste-simple", "texte": "Le total est 2 + 2 = 4.", "attendu": None},
    {"id": "calc-juste-decimal", "texte": "On obtient 0.1 + 0.2 = 0.3.", "attendu": None},
    {"id": "calc-juste-grand", "texte": "Cela fait 1250 + 750 = 2000 francs.",
     "attendu": None},
    {"id": "calc-non-calcul", "texte": "Posons que x = 3 et que y = 4 ensuite.",
     "attendu": None},

    # --- Réponse vide ------------------------------------------------------
    {"id": "vide", "texte": "   ", "attendu": "empty_answer"},
    {"id": "breve-mais-valide", "texte": "42", "attendu": None},
    {"id": "breve-mais-valide-2", "texte": "Oui, à Dakar.", "attendu": None},

    # --- Certitude sans appui ---------------------------------------------
    {"id": "certitude-sans-ancrage",
     "texte": "Il est certain que ce chiffre est exact.",
     "ancrage": "UNGROUNDED", "attendu": "unsupported_certainty"},
    {"id": "certitude-sans-verification",
     "texte": "Il est prouvé que la récolte a doublé.",
     "ancrage": "NOT_CHECKED", "attendu": "unsupported_certainty"},
    {"id": "certitude-ancree",
     "texte": "Il est certain que ce chiffre est exact.",
     "ancrage": "GROUNDED", "attendu": None},
    {"id": "prudence-sans-ancrage",
     "texte": "D'après ce que je sais, ce chiffre semble proche de la réalité.",
     "ancrage": "UNGROUNDED", "attendu": None},

    # --- Contradiction avec un constat ------------------------------------
    {"id": "contredit-un-constat",
     "texte": "Le Sénégal compte quatorze régions administratives.",
     "constats": [{"content": "Le Sénégal ne compte pas quatorze régions administratives.",
                   "source": "corpus", "verified": True}],
     "attendu": "contradicted_by_evidence"},
    {"id": "conforme-au-constat",
     "texte": "Le Sénégal compte quatorze régions administratives.",
     "constats": [{"content": "Le Sénégal compte quatorze régions administratives.",
                   "source": "corpus", "verified": True}],
     "ancrage": "GROUNDED", "attendu": None},
    {"id": "au-dela-du-constat",
     "texte": "Le climat y est sahélien au nord.",
     "constats": [{"content": "Le Sénégal compte quatorze régions.",
                   "source": "corpus", "verified": True}],
     "ancrage": "GROUNDED", "attendu": None},

    # --- Ce que les contrôles ratent, et qui est ici pour le dire ----------
    #
    # Un banc qui se donne 100 % ne mesure rien. Ces cas portent de vraies
    # erreurs qu'aucun contrôle actuel n'attrape : ils font baisser le taux de
    # détection, et c'est exactement leur rôle. Les retirer pour embellir le
    # chiffre serait la fabrication que ce dépôt refuse partout ailleurs.
    {"id": "calc-faux-en-toutes-lettres",
     "texte": "Trois fois quatre font treize.",
     "attendu": "arithmetic_error",
     "connu_rate": "Les nombres écrits en lettres ne sont pas analysés."},
    {"id": "calc-faux-sans-signe-egal",
     "texte": "Le tiers de 90 vaut 35.",
     "attendu": "arithmetic_error",
     "connu_rate": "Seule la forme « a op b = c » est reconnue."},
    {"id": "calc-faux-en-pourcentage",
     "texte": "20 % de 200 donne 60.",
     "attendu": "arithmetic_error",
     "connu_rate": "Le pourcentage n'est pas un opérateur reconnu."},
    {"id": "contradiction-reformulee",
     "texte": "La récolte a fortement augmenté cette année.",
     "constats": [{"content": "La récolte a chuté de moitié cette année.",
                   "source": "corpus", "verified": True}],
     "attendu": "contradicted_by_evidence",
     "connu_rate": "La contradiction est sémantique ; la mesure est lexicale."},
)


@dataclass
class Resultat:
    """Ce qu'un cas a donné, comparé à ce qu'il attendait."""

    identifiant: str
    attendu: Optional[str]
    obtenus: List[str] = field(default_factory=list)

    @property
    def porte_un_defaut(self) -> bool:
        """Vrai si ce cas est censé déclencher un contrôle."""
        return self.attendu is not None

    @property
    def reussi(self) -> bool:
        """
        Vrai quand le résultat correspond à l'attente.

        Pour un cas sain, **aucun** constat bloquant ne doit apparaître : c'est
        la fausse alerte, et elle compte autant qu'une détection manquée.
        """
        if self.porte_un_defaut:
            return self.attendu in self.obtenus
        return not self.obtenus

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat du cas."""
        return {
            "id": self.identifiant,
            "expected": self.attendu,
            "found": list(self.obtenus),
            "passed": self.reussi,
        }


def executer(cas: Sequence[Dict[str, Any]] = CAS) -> Dict[str, Any]:
    """
    Fait tourner tous les cas et rend les deux taux.

    Args:
        cas: Les cas à éprouver ; ceux du module par défaut.

    Returns:
        Le rapport. `detection_rate` et `false_alarm_rate` valent `None` — et
        non `0` — quand aucun cas de la catégorie n'existe : un taux sur zéro
        cas n'est pas nul, il n'est pas mesurable. C'est la règle que le moteur
        média applique déjà (`NOT_MEASURABLE`, jamais 100 %).
    """
    resultats: List[Resultat] = []
    for entree in cas:
        constats = critiquer(
            entree["texte"],
            evidence=entree.get("constats"),
            grounding_status=entree.get("ancrage", ""),
        )
        resultats.append(Resultat(
            identifiant=entree["id"],
            attendu=entree.get("attendu"),
            obtenus=[c.code for c in constats if c.bloquant],
        ))

    avec_defaut = [r for r in resultats if r.porte_un_defaut]
    sains = [r for r in resultats if not r.porte_un_defaut]

    return {
        "cases": len(resultats),
        "with_defect": len(avec_defaut),
        "clean": len(sains),
        "detected": sum(1 for r in avec_defaut if r.reussi),
        "false_alarms": sum(1 for r in sains if not r.reussi),
        "detection_rate": _taux(sum(1 for r in avec_defaut if r.reussi), len(avec_defaut)),
        "false_alarm_rate": _taux(sum(1 for r in sains if not r.reussi), len(sains)),
        "failures": [r.to_dict() for r in resultats if not r.reussi],
        "results": [r.to_dict() for r in resultats],
    }


def _taux(numerateur: int, denominateur: int) -> Optional[float]:
    """Rend le taux, ou `None` quand il n'y a rien à diviser."""
    if denominateur == 0:
        return None
    return round(numerateur / denominateur, 4)


def rapport(cas: Sequence[Dict[str, Any]] = CAS) -> str:
    """
    Rend le rapport sous forme lisible, pour un exploitant.

    Args:
        cas: Les cas à éprouver.

    Returns:
        Un texte court. Les deux taux y figurent **ensemble** : publier la
        détection seule laisserait croire à un contrôle sans coût.
    """
    mesure = executer(cas)
    detection = mesure["detection_rate"]
    fausses = mesure["false_alarm_rate"]
    lignes = [
        "Banc d'essai des critiques — GalSen IA",
        f"  cas                 : {mesure['cases']}",
        f"  avec défaut         : {mesure['with_defect']}",
        f"  sains               : {mesure['clean']}",
        f"  détection           : {_pourcent(detection)} ({mesure['detected']}/{mesure['with_defect']})",
        f"  fausses alertes     : {_pourcent(fausses)} ({mesure['false_alarms']}/{mesure['clean']})",
    ]
    if mesure["failures"]:
        lignes.append("  échecs :")
        for echec in mesure["failures"]:
            lignes.append(
                f"    - {echec['id']} : attendu {echec['expected']}, obtenu {echec['found']}"
            )
    return "\n".join(lignes)


def _pourcent(taux: Optional[float]) -> str:
    """Formate un taux, ou dit qu'il n'est pas mesurable."""
    return "NON MESURABLE" if taux is None else f"{taux * 100:.1f} %"


if __name__ == "__main__":  # pragma: no cover - point d'entrée manuel
    print(rapport())
