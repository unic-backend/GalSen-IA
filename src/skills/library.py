"""
Une bibliothèque de compétences qui grandit avec l'exécution.

## D'où vient l'idée

Du dépôt **Odyssey** (`zju-vipa/Odyssey`, MIT, © 2023 MineDojo Team), lui-même
bâti sur **Voyager**. Son `SkillManager` fait trois choses qu'aucun agent de
cette plateforme ne faisait : il **garde** une procédure qui a servi, lui fait
**écrire une description**, et la **retrouve par le sens** quand une demande
proche revient.

## Ce qui n'est pas repris, et pourquoi

Aucune ligne d'Odyssey n'est copiée. Son `SkillManager` importe `langchain`,
`Chroma` et les embeddings d'OpenAI, plus des primitives Minecraft. Trois de ces
quatre choses sont interdites ici :

- **ADR-017** — un second cadre d'orchestration n'est pas adopté ;
- **ADR-014** — aucune requête ne part vers un modèle tiers à l'exécution ;
- **ADR-015** — les embeddings sont un fournisseur local, et la récupération dit
  quel chemin elle a pris.

Cette plateforme avait déjà tout le substrat : `SemanticIndex`,
`SQLiteVectorStore`, un fournisseur d'embeddings. Il manquait la chose à ranger
dedans.

## Ce que cette version ajoute à l'idée d'Odyssey

**Odyssey range ce que l'agent a écrit. Ici on range ce qui a marché.**

Une compétence entre avec son origine et son verdict de vérification. Sans
preuve, elle entre quand même — mais marquée `verifiee=False`, et la
récupération ne la présentera jamais autrement. C'est la même règle que le
corpus : rien n'entre sans qu'on sache d'où ça vient.
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..embeddings.semantic_index import rank_or_fallback
from ..storage.paths import data_dir

#: Nom du fichier qui garde les compétences.
FICHIER = "competences.json"

#: Espace de noms des vecteurs, distinct de `memory` et `knowledge` : une
#: compétence n'est ni un souvenir ni un fait.
COLLECTION = "skills"


class CompetenceRefusee(ValueError):
    """Une compétence à laquelle il manque ce qui permettrait d'y revenir."""


@dataclass
class Competence:
    """
    Une procédure qui a servi, et ce qu'on sait d'elle.

    `origine` et `verifiee` ne sont pas décoratifs. Une bibliothèque qui garde
    tout ce qu'un modèle a produit devient un tas ; celle-ci sait dire, de
    chaque entrée, d'où elle vient et si quelqu'un l'a vue fonctionner.
    """

    nom: str
    description: str
    contenu: str
    #: Qui l'a produite — un agent, un outil, une personne. Jamais vide.
    origine: str
    #: Vrai seulement si son fonctionnement a été **constaté**.
    verifiee: bool = False
    #: Ce qui l'a prouvé : un identifiant d'exécution, un test. Vide si rien.
    preuve: str = ""
    creee_le: float = field(default_factory=time.time)
    #: Combien de fois elle a été retrouvée et réutilisée.
    reutilisations: int = 0

    def valider(self) -> None:
        """
        Refuse une compétence à laquelle il manque l'essentiel.

        Un nom vide la rend introuvable ; une description vide la rend
        irrécupérable par le sens ; une origine vide en fait une affirmation
        sans auteur. Les trois sont des refus, pas des avertissements.
        """
        if not self.nom.strip():
            raise CompetenceRefusee("Une compétence sans nom est introuvable.")
        if not self.description.strip():
            raise CompetenceRefusee(
                f"« {self.nom} » n'a pas de description : rien ne permettrait "
                "de la retrouver par le sens."
            )
        if not self.origine.strip():
            raise CompetenceRefusee(
                f"« {self.nom} » n'a pas d'origine. Rien n'entre ici sans "
                "qu'on sache d'où ça vient."
            )
        if self.verifiee and not self.preuve.strip():
            raise CompetenceRefusee(
                f"« {self.nom} » se dit vérifiée sans dire par quoi. "
                "Une vérification sans preuve est une affirmation."
            )


class BibliothequeCompetences:
    """
    Garde les compétences et les retrouve par le sens.

    Le fournisseur d'embeddings est **injecté** et peut être absent : dans ce
    cas la récupération retombe sur les mots et **le dit**, au lieu de laisser
    croire qu'elle a compris la demande.
    """

    def __init__(self, embedder: Optional[Any] = None, chemin: Optional[str] = None):
        """
        Args:
            embedder: fournisseur d'embeddings, ou `None` pour un classement
                lexical assumé.
            chemin: fichier de persistance ; celui du répertoire de données
                sinon (`GALSEN_DATA_DIR`).
        """
        self._embedder = embedder
        self._chemin = chemin or os.path.join(data_dir(), FICHIER)
        self._competences: Dict[str, Competence] = {}
        self._charger()

    # ------------------------------------------------------------------
    # Écriture
    # ------------------------------------------------------------------

    def ajouter(self, competence: Competence) -> Competence:
        """
        Range une compétence, en remplaçant celle du même nom.

        Le remplacement est délibéré : deux versions d'une même procédure sous
        le même nom rendraient la récupération imprévisible. La nouvelle hérite
        du compteur de réutilisations de l'ancienne — ce qui a servi a servi.
        """
        competence.valider()
        ancienne = self._competences.get(competence.nom)
        if ancienne is not None:
            competence.reutilisations = ancienne.reutilisations
        self._competences[competence.nom] = competence
        self._ecrire()
        return competence

    def oublier(self, nom: str) -> bool:
        """Retire une compétence. Retourne `False` si elle n'existait pas."""
        if nom not in self._competences:
            return False
        del self._competences[nom]
        self._ecrire()
        return True

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def retrouver(
        self,
        requete: str,
        limite: int = 5,
        verifiees_seulement: bool = False,
    ) -> Tuple[List[Competence], Dict[str, Any]]:
        """
        Retrouve les compétences les plus proches d'une demande.

        Returns:
            Le couple `(compétences, info)`. `info["method"]` dit **par quel
            chemin** le classement a été obtenu — `semantic`, `lexical`, ou
            `empty` quand il n'y a rien à classer. Le vocabulaire est celui de
            `rank_or_fallback` : en inventer un second garantirait qu'ils
            finissent par ne plus dire la même chose. Un appelant qui
            ignore ce second membre présentera un classement par mots comme une
            compréhension du sens, et c'est précisément ce que cette plateforme
            refuse ailleurs.
        """
        candidates = [
            c for c in self._competences.values()
            if not verifiees_seulement or c.verifiee
        ]
        if not candidates:
            return [], {
                "method": "empty",
                "reason": "Aucune compétence rangée pour l'instant.",
            }

        elements: Sequence[Tuple[str, str]] = [
            (c.nom, f"{c.nom}. {c.description}") for c in candidates
        ]

        classes, info = rank_or_fallback(
            requete=requete,
            elements=elements,
            repli=lambda: _classement_lexical(requete, elements),
            embedder=self._embedder,
            collection=COLLECTION,
            limit=limite,
        )
        trouvees = [self._competences[nom] for nom, _ in classes if nom in self._competences]
        for c in trouvees:
            c.reutilisations += 1
        if trouvees:
            self._ecrire()
        return trouvees, info

    def compter(self, verifiees_seulement: bool = False) -> int:
        """Combien de compétences sont rangées."""
        if not verifiees_seulement:
            return len(self._competences)
        return sum(1 for c in self._competences.values() if c.verifiee)

    def etat(self) -> Dict[str, Any]:
        """
        Ce que la bibliothèque contient, et ce qu'elle ne peut pas faire.

        `semantique` est faux quand aucun fournisseur d'embeddings n'est
        branché : la récupération marche encore, par les mots, et cet état le
        dit plutôt que de laisser le découvrir.
        """
        return {
            "total": self.compter(),
            "verifiees": self.compter(verifiees_seulement=True),
            "semantique": self._embedder is not None,
            "fichier": self._chemin,
        }

    # ------------------------------------------------------------------
    # Persistance
    # ------------------------------------------------------------------

    def _charger(self) -> None:
        """Relit le fichier. Un fichier illisible laisse la bibliothèque vide."""
        if not os.path.isfile(self._chemin):
            return
        try:
            with open(self._chemin, encoding="utf-8") as fichier:
                brut = json.load(fichier)
        except (OSError, json.JSONDecodeError):
            # Une bibliothèque vide est un état ; une exception au démarrage en
            # est un autre, et le second empêcherait la plateforme de servir.
            return
        for entree in brut.get("competences", []):
            try:
                competence = Competence(**entree)
                competence.valider()
            except (TypeError, CompetenceRefusee):
                continue
            self._competences[competence.nom] = competence

    def _ecrire(self) -> None:
        """Écrit le fichier, en créant le répertoire s'il manque."""
        os.makedirs(os.path.dirname(self._chemin) or ".", exist_ok=True)
        charge = {"competences": [asdict(c) for c in self._competences.values()]}
        with open(self._chemin, "w", encoding="utf-8") as fichier:
            json.dump(charge, fichier, ensure_ascii=False, indent=2)


def _classement_lexical(
    requete: str, elements: Sequence[Tuple[str, str]]
) -> List[Tuple[str, float]]:
    """
    Classement de repli : combien de mots de la demande apparaissent.

    Grossier, et assumé comme tel. Il existe pour que l'absence d'embeddings
    dégrade la récupération au lieu de la supprimer.
    """
    mots = {m for m in requete.lower().split() if len(m) > 2}
    if not mots:
        return []
    scores = []
    for identifiant, texte in elements:
        presents = sum(1 for m in mots if m in texte.lower())
        if presents:
            scores.append((identifiant, presents / len(mots)))
    return sorted(scores, key=lambda p: -p[1])
