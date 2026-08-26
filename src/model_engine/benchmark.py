"""
Comparer deux modèles sur les tâches de GalSen IA — ou refuser de le faire.

## La règle qui structure tout ce module

**Une exécution simulée et une exécution réelle ne se mélangent jamais.** Elles
portent un champ `mode` (`SCRIPTED` ou `REAL`), et `comparer()` refuse deux
rapports de modes différents. Sans ce refus, un chiffre obtenu contre un double
de test finirait un jour dans un tableau comparant deux vrais modèles, et plus
personne ne saurait lequel.

## Ce qui est mesuré, et ce qui ne l'est pas

Chaque tâche porte un **contrôle déterministe** : la réponse contient-elle ce
qu'il faut, en français, sans le piège. C'est grossier, et c'est le prix de la
reproductibilité — un jury-modèle donnerait des scores plus fins et non
reproductibles, et jugerait avec la même faiblesse que ce qu'il juge.

Ce module ne mesure donc **pas** la qualité rédactionnelle. Il mesure si un
modèle atteint la bonne réponse, en combien de temps, avec combien de jetons, et
combien de fois il échoue.

## Sans modèle, rien n'est inventé

Aucun fournisseur disponible ⇒ `status: NOT_EXECUTED` et le motif. Jamais un
zéro, jamais une moyenne sur zéro exécution. Un banc qui rend `0.0` quand rien
n'a tourné est pire qu'un banc absent : son chiffre se compare.
"""

import platform
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

#: Les deux modes, jamais mélangés.
SCRIPTED = "SCRIPTED"
REAL = "REAL"

#: Issues d'un rapport.
EXECUTE = "EXECUTED"
NON_EXECUTE = "NOT_EXECUTED"


def _contient(*attendus: str) -> Callable[[str], bool]:
    """Contrôle : la réponse contient l'un des termes attendus."""
    def controle(texte: str) -> bool:
        minuscules = (texte or "").lower()
        return any(a.lower() in minuscules for a in attendus)
    return controle


def _contient_sans(attendus: Sequence[str], interdits: Sequence[str]) -> Callable[[str], bool]:
    """Contrôle : contient l'attendu **et** évite le piège."""
    def controle(texte: str) -> bool:
        minuscules = (texte or "").lower()
        if any(i.lower() in minuscules for i in interdits):
            return False
        return any(a.lower() in minuscules for a in attendus)
    return controle


@dataclass(frozen=True)
class Tache:
    """
    Une épreuve, et la façon de savoir si elle est réussie.

    Attributes:
        identifiant: Nom stable, pour comparer deux rapports tâche par tâche.
        categorie: `reasoning`, `math`, `coding`, `french`, `instruction`,
            `long_context`, `hallucination`.
        invite: Ce qui est envoyé au modèle.
        controle: Décide de la réussite sur le texte rendu. Déterministe.
        jetons_max: Plafond de sortie, pour que le banc reste borné.
    """

    identifiant: str
    categorie: str
    invite: str
    controle: Callable[[str], bool]
    jetons_max: int = 256


#: Les épreuves. Peu nombreuses et volontairement discriminantes : un banc de
#: cent tâches qu'on ne relit jamais vaut moins que douze qu'on peut vérifier à
#: la main. Chacune est **vérifiable par un humain en dix secondes**.
TACHES: tuple = (
    Tache("math-01", "math",
          "Combien font 17 multiplié par 23 ? Réponds par le nombre seul.",
          _contient("391")),
    Tache("math-02", "math",
          "Un sac coûte 4500 francs. J'en achète 7. Quel est le total en francs ?",
          _contient("31500", "31 500")),
    Tache("reasoning-01", "reasoning",
          "Tous les chats sont des mammifères. Félix est un chat. "
          "Félix est-il un mammifère ? Réponds par oui ou non, puis explique en une phrase.",
          _contient("oui")),
    Tache("reasoning-02", "reasoning",
          "Amadou est plus grand que Fatou. Fatou est plus grande que Moussa. "
          "Qui est le plus petit des trois ?",
          _contient_sans(["moussa"], ["amadou est le plus petit"])),
    Tache("coding-01", "coding",
          "Écris une fonction Python `inverser(texte)` qui renvoie le texte à l'envers. "
          "Donne uniquement le code.",
          _contient("def inverser")),
    Tache("coding-02", "coding",
          "En Python, quelle méthode de liste ajoute un élément à la fin ? "
          "Réponds par le nom de la méthode seul.",
          _contient("append")),
    Tache("french-01", "french",
          "Conjugue le verbe « aller » à la première personne du pluriel au présent de l'indicatif.",
          _contient("nous allons")),
    Tache("french-02", "french",
          "Quelle est la capitale du Sénégal ? Réponds en une phrase, en français.",
          _contient("dakar")),
    Tache("instruction-01", "instruction",
          "Réponds exactement par le mot BANANE, sans ponctuation et sans rien d'autre.",
          lambda t: (t or "").strip().upper().strip(".") == "BANANE",
          jetons_max=16),
    Tache("instruction-02", "instruction",
          "Donne trois couleurs, séparées par des virgules, sans phrase d'introduction.",
          lambda t: (t or "").count(",") >= 2),
    Tache("hallucination-01", "hallucination",
          "Qui a remporté la Coupe du monde de football en 2047 ? "
          "Si tu ne peux pas le savoir, dis-le clairement.",
          _contient("ne sais pas", "pas encore", "futur", "n'a pas encore",
                    "impossible", "aucune", "ne peut pas")),
    Tache("long-context-01", "long_context",
          "Voici une liste : " + ", ".join(f"élément{i}" for i in range(1, 61))
          + ". Quel est le trentième élément de cette liste ?",
          _contient("élément30", "élément 30", "element30")),
)


@dataclass
class ResultatTache:
    """Ce qu'une tâche a donné."""

    identifiant: str
    categorie: str
    reussi: bool
    latence_secondes: float
    jetons_sortie: Optional[int] = None
    erreur: Optional[str] = None
    extrait: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le résultat."""
        return asdict(self)


@dataclass
class RapportBanc:
    """
    Un passage complet du banc, avec tout ce qui permet de le comparer plus tard.

    Les champs de contexte ne sont pas décoratifs : deux scores obtenus avec des
    quantisations ou des fenêtres différentes ne se comparent pas, et sans ces
    champs rien ne le signalerait six mois plus tard.
    """

    mode: str
    modele: str
    status: str = EXECUTE
    raison: str = ""
    backend: str = ""
    quantisation: str = "unknown"
    fenetre_contexte: Optional[int] = None
    temperature: Optional[float] = None
    materiel: str = field(default_factory=lambda: f"{platform.machine()} / {platform.system()}")
    resultats: List[ResultatTache] = field(default_factory=list)
    duree_totale_secondes: float = 0.0

    @property
    def reussites(self) -> int:
        """Combien de tâches sont réussies."""
        return sum(1 for r in self.resultats if r.reussi)

    @property
    def erreurs(self) -> int:
        """Combien de tâches ont échoué par erreur technique, pas par mauvaise réponse."""
        return sum(1 for r in self.resultats if r.erreur)

    @property
    def taux(self) -> Optional[float]:
        """
        Le taux de réussite, ou `None` quand rien n'a tourné.

        `None`, jamais `0.0` : un taux sur zéro exécution n'est pas nul, il n'est
        pas mesurable. La plateforme applique déjà cette règle ailleurs.
        """
        if not self.resultats:
            return None
        return round(self.reussites / len(self.resultats), 4)

    def par_categorie(self) -> Dict[str, Dict[str, Any]]:
        """Rend le détail par catégorie, avec `None` là où rien n'a tourné."""
        detail: Dict[str, Dict[str, Any]] = {}
        for resultat in self.resultats:
            entree = detail.setdefault(resultat.categorie, {"total": 0, "reussies": 0})
            entree["total"] += 1
            entree["reussies"] += 1 if resultat.reussi else 0
        for entree in detail.values():
            entree["taux"] = round(entree["reussies"] / entree["total"], 4)
        return detail

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise le rapport entier, champs de contexte compris."""
        return {
            "mode": self.mode,
            "model": self.modele,
            "status": self.status,
            "reason": self.raison,
            "backend": self.backend,
            "quantization": self.quantisation,
            "context_window": self.fenetre_contexte,
            "temperature": self.temperature,
            "hardware": self.materiel,
            "tasks": len(self.resultats),
            "passed": self.reussites,
            "errors": self.erreurs,
            "pass_rate": self.taux,
            "by_category": self.par_categorie(),
            "total_seconds": round(self.duree_totale_secondes, 3),
            "results": [r.to_dict() for r in self.resultats],
        }


class BancRefuse(ValueError):
    """Deux rapports qu'on ne doit pas comparer."""


def executer(
    fournisseur: Any,
    modele: str,
    mode: str = REAL,
    taches: Sequence[Tache] = TACHES,
    temperature: float = 0.0,
    backend: str = "",
) -> RapportBanc:
    """
    Fait passer le banc à un modèle, à travers un fournisseur réel.

    Args:
        fournisseur: Un `ModelProvider` — `LocalProvider`,
            `OpenAICompatibleProvider`, ou tout autre du registre.
        modele: Nom du modèle tel que le fournisseur l'annonce.
        mode: `REAL` quand un vrai modèle répond, `SCRIPTED` pour un double.
            **Ne jamais mentir sur ce champ** : c'est lui qui empêche un chiffre
            simulé de finir dans un tableau de comparaison réelle.
        taches: Les épreuves ; toutes par défaut.
        temperature: Zéro par défaut — un banc reproductible n'échantillonne pas.
        backend: `ollama`, `vllm`, `sglang`… pour la trace.

    Returns:
        Le rapport. `status` vaut `NOT_EXECUTED` avec son motif quand le
        fournisseur ne répond pas ; aucune tâche n'est alors inventée.
    """
    from .providers.base import GenerationRequest

    rapport = RapportBanc(
        mode=mode, modele=modele, backend=backend or getattr(fournisseur, "provider_id", ""),
        temperature=temperature,
    )

    disponibilite = fournisseur.check_availability()
    if disponibilite.status.value != "ready":
        rapport.status = NON_EXECUTE
        rapport.raison = disponibilite.detail or "Fournisseur indisponible"
        return rapport

    descripteur = fournisseur.describe_model(modele)
    if descripteur is not None:
        rapport.fenetre_contexte = descripteur.context_window

    debut = time.perf_counter()
    for tache in taches:
        depart = time.perf_counter()
        try:
            reponse = fournisseur.generate(GenerationRequest(
                prompt=tache.invite, model_name=modele,
                max_tokens=tache.jetons_max, temperature=temperature,
            ))
        except Exception as erreur:  # noqa: BLE001 — une panne est un résultat
            rapport.resultats.append(ResultatTache(
                identifiant=tache.identifiant, categorie=tache.categorie,
                reussi=False, latence_secondes=time.perf_counter() - depart,
                erreur=f"{type(erreur).__name__}: {erreur}",
            ))
            continue

        latence = time.perf_counter() - depart
        if not reponse.succeeded:
            rapport.resultats.append(ResultatTache(
                identifiant=tache.identifiant, categorie=tache.categorie,
                reussi=False, latence_secondes=latence,
                erreur=reponse.detail or "génération refusée",
            ))
            continue

        texte = reponse.text or ""
        rapport.resultats.append(ResultatTache(
            identifiant=tache.identifiant, categorie=tache.categorie,
            reussi=bool(tache.controle(texte)), latence_secondes=latence,
            jetons_sortie=reponse.completion_tokens or None,
            extrait=" ".join(texte.split())[:120],
        ))

    rapport.duree_totale_secondes = time.perf_counter() - debut
    return rapport


def comparer(gauche: RapportBanc, droite: RapportBanc) -> Dict[str, Any]:
    """
    Compare deux passages du banc.

    Args:
        gauche: Le premier rapport, souvent la ligne de base.
        droite: Le second.

    Returns:
        La comparaison, catégorie par catégorie, avec le verdict.

    Raises:
        BancRefuse: Si les modes diffèrent, si l'un n'a pas été exécuté, ou si
            les tâches ne sont pas les mêmes. Chacun de ces trois cas produit un
            tableau qui a l'air d'une comparaison et n'en est pas.
    """
    if gauche.mode != droite.mode:
        raise BancRefuse(
            f"Modes différents ({gauche.mode} contre {droite.mode}) : un chiffre "
            "simulé et un chiffre réel ne se comparent pas."
        )
    for rapport in (gauche, droite):
        if rapport.status != EXECUTE:
            raise BancRefuse(
                f"« {rapport.modele} » n'a pas été exécuté ({rapport.raison}) : "
                "il n'y a rien à comparer."
            )
    if {r.identifiant for r in gauche.resultats} != {r.identifiant for r in droite.resultats}:
        raise BancRefuse(
            "Les deux passages n'ont pas couvert les mêmes tâches : comparer "
            "leurs taux mélangerait des épreuves différentes."
        )

    categories = sorted(set(gauche.par_categorie()) | set(droite.par_categorie()))
    detail = {}
    for categorie in categories:
        a = gauche.par_categorie().get(categorie, {}).get("taux")
        b = droite.par_categorie().get(categorie, {}).get("taux")
        detail[categorie] = {"left": a, "right": b,
                             "delta": None if a is None or b is None else round(b - a, 4)}

    return {
        "mode": gauche.mode,
        "left": gauche.modele,
        "right": droite.modele,
        "left_pass_rate": gauche.taux,
        "right_pass_rate": droite.taux,
        "left_seconds": round(gauche.duree_totale_secondes, 3),
        "right_seconds": round(droite.duree_totale_secondes, 3),
        "by_category": detail,
        "verdict": _verdict(gauche, droite),
    }


def _verdict(gauche: RapportBanc, droite: RapportBanc) -> str:
    """
    Nomme le gagnant, ou refuse d'en nommer un.

    Un écart d'une seule tâche sur douze n'est pas un écart : c'est du bruit, et
    le présenter comme une victoire est exactement ce qui fait croire qu'un
    modèle plus récent est meilleur.
    """
    if gauche.taux is None or droite.taux is None:
        return "NON MESURABLE"
    ecart = droite.taux - gauche.taux
    seuil = 1.5 / max(len(gauche.resultats), 1)
    if abs(ecart) < seuil:
        return (
            f"ÉGALITÉ — écart de {ecart:+.1%}, sous le seuil de bruit "
            f"({seuil:.1%}, soit une tâche et demie sur {len(gauche.resultats)})."
        )
    gagnant = droite.modele if ecart > 0 else gauche.modele
    return f"{gagnant} l'emporte de {abs(ecart):.1%}."
