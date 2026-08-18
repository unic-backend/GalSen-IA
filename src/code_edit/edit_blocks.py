"""
Blocs d'édition : le modèle propose, la plateforme applique (VOLET OSS, ch. 06).

L'agent `coder` sait lire le code mais pas le modifier. Lui faire réécrire un
fichier entier serait le pire des gestes : un modèle qui recopie deux cents
lignes en perd, en invente, et rien ne dit lesquelles. Le format de blocs
d'édition renverse la charge — le modèle **nomme le texte exact** à remplacer,
et le remplacement est mécanique :

```
src/exemple.py
<<<<<<< SEARCH
def ancienne():
    return 1
=======
def nouvelle():
    return 2
>>>>>>> REPLACE
```

Un bloc dont la partie SEARCH est vide **crée** un fichier.

La convention vient d'aider (Apache-2.0). Aucun code n'en a été recopié ; la
position exacte est écrite dans `third_party/aider/NOTICE.md`.

Quatre règles gouvernent l'application, et elles existent parce que ce module
écrit sur le disque à partir d'un texte produit par un modèle :

1. **Rien hors de la racine.** Chaque chemin est résolu — liens symboliques
   compris — et refusé s'il sort du dossier confié.
2. **Une seule correspondance.** Zéro : le modèle a inventé le texte. Deux ou
   plus : il ne dit pas laquelle. Dans les deux cas on refuse au lieu de
   deviner ; un remplacement au mauvais endroit est plus coûteux qu'un échec.
3. **Tout ou rien.** Un bloc invalide et rien n'est écrit. Une application
   partielle laisse un dépôt à moitié modifié, état dont personne ne sait
   revenir.
4. **Aucune création silencieuse par-dessus.** Un bloc de création dont le
   fichier existe déjà est une erreur, jamais un écrasement.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

MARQUEUR_RECHERCHE = "<<<<<<< SEARCH"
MARQUEUR_SEPARATEUR = "======="
MARQUEUR_REMPLACEMENT = ">>>>>>> REPLACE"

# Délimiteurs Markdown : un modèle enveloppe presque toujours ses blocs dedans.
FENCE = "```"


@dataclass(frozen=True)
class EditBlock:
    """
    Une modification proposée sur un fichier.

    Attributes:
        path: Chemin du fichier, relatif à la racine confiée.
        search: Texte exact à trouver. Vide signifie « créer le fichier ».
        replace: Texte qui prend sa place.
    """

    path: str
    search: str
    replace: str

    @property
    def creates_file(self) -> bool:
        """Vrai si le bloc crée un fichier au lieu d'en modifier un."""
        return self.search == ""


@dataclass(frozen=True)
class EditOutcome:
    """
    Ce qu'il est advenu d'un bloc.

    Les deux drapeaux disent des choses différentes, et les confondre serait un
    mensonge utile à personne : `would_apply` dit que le bloc est valide,
    `applied` dit que le fichier a réellement changé sur le disque. Une
    vérification à blanc, ou un lot annulé parce qu'un autre bloc a échoué,
    laisse le premier vrai et le second faux.

    Attributes:
        block: Le bloc concerné.
        would_apply: Vrai si le bloc est applicable tel quel.
        applied: Vrai si le fichier a effectivement été écrit.
        reason: Le motif, en français, quand le bloc n'a pas été écrit.
        created: Vrai si le fichier est créé plutôt que modifié.
    """

    block: EditBlock
    would_apply: bool
    applied: bool = False
    reason: str = ""
    created: bool = False


@dataclass(frozen=True)
class EditReport:
    """
    Le résultat d'une application.

    Attributes:
        outcomes: Un résultat par bloc, dans l'ordre reçu.
        parse_errors: Les fautes de forme relevées à la lecture du texte.
        dry_run: Vrai si rien n'a été écrit volontairement.
    """

    outcomes: List[EditOutcome] = field(default_factory=list)
    parse_errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        """
        Vrai si le texte était bien formé et si tous les blocs sont applicables.

        Une vérification à blanc réussie rend `ok` vrai sans qu'aucun fichier
        n'ait changé : c'est bien ce qu'on lui demande.
        """
        return not self.parse_errors and all(r.would_apply for r in self.outcomes)

    @property
    def applied_paths(self) -> List[str]:
        """Chemins effectivement écrits."""
        return [r.block.path for r in self.outcomes if r.applied]

    @property
    def failures(self) -> List[EditOutcome]:
        """Les blocs refusés, avec leur motif."""
        return [r for r in self.outcomes if not r.would_apply]

    def summary(self) -> Dict[str, Any]:
        """
        Résume le résultat pour un appelant qui ne lira pas le détail.

        Returns:
            Le décompte, les chemins touchés et les motifs de refus.
        """
        return {
            "ok": self.ok,
            "applied": len(self.applied_paths),
            "failed": len(self.failures),
            "paths": self.applied_paths,
            "errors": self.parse_errors + [r.reason for r in self.failures],
            "dry_run": self.dry_run,
        }


# ----------------------------------------------------------------------
# Lecture du texte du modèle
# ----------------------------------------------------------------------

def parse_edit_blocks(text: str) -> Tuple[List[EditBlock], List[str]]:
    """
    Extrait les blocs d'édition d'une réponse de modèle.

    Le texte autour des blocs est ignoré : un modèle explique presque toujours
    ce qu'il fait avant de le faire.

    Args:
        text: La réponse du modèle.

    Returns:
        Les blocs trouvés, et les fautes de forme relevées. Un bloc mal fermé
        ne devient jamais un bloc partiel : il devient une faute.
    """
    lignes = (text or "").splitlines()
    blocs: List[EditBlock] = []
    fautes: List[str] = []

    index = 0
    while index < len(lignes):
        if not lignes[index].startswith(MARQUEUR_RECHERCHE):
            index += 1
            continue

        depart = index
        chemin = _chemin_avant(lignes, depart)
        if not chemin:
            fautes.append(
                f"Ligne {depart + 1} : bloc sans chemin de fichier au-dessus du "
                f"marqueur {MARQUEUR_RECHERCHE}."
            )
            index += 1
            continue

        section = _lire_bloc(lignes, depart)
        if section is None:
            fautes.append(
                f"Ligne {depart + 1} : bloc non terminé — il manque "
                f"« {MARQUEUR_SEPARATEUR} » ou « {MARQUEUR_REMPLACEMENT} »."
            )
            index += 1
            continue

        recherche, remplacement, fin = section
        blocs.append(EditBlock(path=chemin, search=recherche, replace=remplacement))
        index = fin + 1

    return blocs, fautes


def _lire_bloc(lignes: Sequence[str], depart: int) -> Optional[Tuple[str, str, int]]:
    """
    Lit un bloc à partir de son marqueur d'ouverture.

    Returns:
        Le texte cherché, le texte de remplacement et l'index de la ligne de
        fermeture ; `None` si le bloc n'est pas fermé correctement.
    """
    recherche: List[str] = []
    remplacement: List[str] = []
    dans_le_remplacement = False

    for index in range(depart + 1, len(lignes)):
        ligne = lignes[index]

        if ligne.startswith(MARQUEUR_REMPLACEMENT):
            if not dans_le_remplacement:
                return None
            return _joindre(recherche), _joindre(remplacement), index

        if not dans_le_remplacement and ligne.rstrip() == MARQUEUR_SEPARATEUR:
            dans_le_remplacement = True
            continue

        # Un second marqueur d'ouverture signale le bloc précédent non fermé.
        if ligne.startswith(MARQUEUR_RECHERCHE):
            return None

        (remplacement if dans_le_remplacement else recherche).append(ligne)

    return None


def _joindre(lignes: List[str]) -> str:
    """Recompose un fragment, avec sa nouvelle ligne finale s'il n'est pas vide."""
    return "\n".join(lignes) + "\n" if lignes else ""


def _chemin_avant(lignes: Sequence[str], depart: int) -> str:
    """
    Retrouve le chemin déclaré juste avant un marqueur d'ouverture.

    Les lignes vides et les délimiteurs Markdown sont sautés : un modèle place
    couramment le chemin avant l'ouverture de son bloc de code.
    """
    for index in range(depart - 1, -1, -1):
        candidat = lignes[index].strip()
        if not candidat or candidat.startswith(FENCE):
            continue
        return _nettoyer_chemin(candidat)
    return ""


def _nettoyer_chemin(ligne: str) -> str:
    """Retire les décorations Markdown fréquentes autour d'un chemin."""
    # Un seul `strip` par décoration ne suffit pas : les modèles les empilent
    # (`**`src/a.py`**`), donc on retire l'ensemble d'un coup.
    candidat = ligne.strip("`*# \t\r\n")
    # Un chemin ne contient pas d'espace dans ce dépôt ; une phrase, si. Cela
    # évite de prendre « Voici le fichier à modifier : » pour un chemin.
    return "" if not candidat or " " in candidat else candidat


# ----------------------------------------------------------------------
# Application
# ----------------------------------------------------------------------

def apply_edit_blocks(
    blocks: Sequence[EditBlock],
    root: Any,
    dry_run: bool = False,
    parse_errors: Optional[Sequence[str]] = None,
) -> EditReport:
    """
    Applique des blocs d'édition sous une racine donnée.

    L'application est **atomique** : tous les blocs sont vérifiés avant que
    quoi que ce soit ne soit écrit. Si l'un échoue, aucun fichier n'est touché.

    Plusieurs blocs peuvent viser le même fichier : ils s'appliquent dans
    l'ordre, chacun cherchant dans le résultat du précédent.

    Args:
        blocks: Les blocs à appliquer.
        root: Dossier hors duquel rien ne sera écrit.
        dry_run: Vérifie tout sans écrire.
        parse_errors: Fautes déjà relevées à la lecture ; leur présence suffit
            à tout refuser, car un texte mal formé peut cacher un bloc perdu.

    Returns:
        Le compte rendu, un résultat par bloc.
    """
    fautes_de_lecture = list(parse_errors or [])
    racine = Path(root).resolve()

    resultats: List[EditOutcome] = []
    # Contenu en cours par fichier : c'est ce qui permet à deux blocs de se
    # suivre sur le même fichier sans que le second cherche dans l'ancien texte.
    en_cours: Dict[Path, str] = {}
    a_creer: set = set()

    for bloc in blocks:
        try:
            cible = _chemin_sur(racine, bloc.path)
        except ValueError as erreur:
            resultats.append(
                EditOutcome(block=bloc, would_apply=False, reason=str(erreur))
            )
            continue
        resultats.append(_preparer(bloc, cible, en_cours, a_creer))

    applicable = not fautes_de_lecture and all(r.would_apply for r in resultats)

    if dry_run or not applicable:
        # Rien n'est écrit : soit l'appelant ne voulait qu'une vérification,
        # soit un bloc a échoué et l'application est atomique. Les blocs
        # valides ne doivent surtout pas se dire appliqués dans ce cas.
        motif = "" if dry_run else "annulé : un autre bloc du lot a échoué."
        return EditReport(
            outcomes=[
                r if not r.would_apply else EditOutcome(
                    block=r.block, would_apply=True, applied=False,
                    reason=motif, created=r.created,
                )
                for r in resultats
            ],
            parse_errors=fautes_de_lecture,
            dry_run=dry_run,
        )

    for chemin, contenu in en_cours.items():
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(chemin, "w", encoding="utf-8", newline="") as fichier:
            fichier.write(contenu)

    return EditReport(
        outcomes=[
            EditOutcome(block=r.block, would_apply=True, applied=True, created=r.created)
            for r in resultats
        ],
        parse_errors=fautes_de_lecture,
        dry_run=False,
    )


def apply_response(text: str, root: Any, dry_run: bool = False) -> EditReport:
    """
    Lit une réponse de modèle et applique les blocs qu'elle contient.

    C'est le point d'entrée attendu par un agent : une réponse entre, un compte
    rendu sort.

    Args:
        text: La réponse du modèle.
        root: Dossier hors duquel rien ne sera écrit.
        dry_run: Vérifie tout sans écrire.

    Returns:
        Le compte rendu.
    """
    blocs, fautes = parse_edit_blocks(text)
    return apply_edit_blocks(blocs, root, dry_run=dry_run, parse_errors=fautes)


# ----------------------------------------------------------------------
# Vérifications
# ----------------------------------------------------------------------

def _chemin_sur(racine: Path, chemin_relatif: str) -> Path:
    """
    Résout un chemin et refuse tout ce qui sort de la racine.

    Args:
        racine: Dossier confié, déjà résolu.
        chemin_relatif: Chemin déclaré par le modèle.

    Returns:
        Le chemin absolu, garanti sous la racine.

    Raises:
        ValueError: Chemin absolu, remontée par `..`, ou lien symbolique
            menant dehors. C'est la garde la plus importante du module : le
            texte vient d'un modèle, et un chemin est vite forgé.
    """
    if not chemin_relatif:
        raise ValueError("Chemin de fichier vide.")
    if os.path.isabs(chemin_relatif) or chemin_relatif.startswith("~"):
        raise ValueError(f"« {chemin_relatif} » : chemin absolu refusé.")

    resolu = (racine / chemin_relatif).resolve()
    if resolu != racine and racine not in resolu.parents:
        raise ValueError(
            f"« {chemin_relatif} » sort du dossier de travail — refusé."
        )
    return resolu


def _preparer(
    bloc: EditBlock,
    cible: Path,
    en_cours: Dict[Path, str],
    a_creer: set,
) -> EditOutcome:
    """
    Vérifie un bloc et prépare le contenu résultant, sans rien écrire.

    Returns:
        Le résultat du bloc ; `would_apply` vaut vrai quand il est applicable.
        L'écriture, elle, n'a lieu qu'après la validation de tout le lot.
    """
    if bloc.creates_file:
        if cible in en_cours or cible.exists():
            return EditOutcome(
                block=bloc, would_apply=False,
                reason=f"« {bloc.path} » existe déjà : un bloc de création ne "
                       f"l'écrase pas. Utilisez un bloc SEARCH/REPLACE.",
            )
        en_cours[cible] = bloc.replace
        a_creer.add(cible)
        return EditOutcome(block=bloc, would_apply=True, created=True)

    if cible in en_cours:
        contenu = en_cours[cible]
    else:
        if not cible.is_file():
            return EditOutcome(
                block=bloc, would_apply=False,
                reason=f"« {bloc.path} » n'existe pas. Pour le créer, laissez la "
                       f"section SEARCH vide.",
            )
        try:
            with open(cible, encoding="utf-8", newline="") as fichier:
                contenu = fichier.read()
        except (OSError, UnicodeDecodeError) as erreur:
            return EditOutcome(
                block=bloc, would_apply=False,
                reason=f"« {bloc.path} » illisible : {erreur}",
            )

    cherche, remplace = _adapter_aux_fins_de_ligne(contenu, bloc)
    occurrences = contenu.count(cherche)
    if occurrences == 0:
        return EditOutcome(
            block=bloc, would_apply=False,
            reason=f"« {bloc.path} » : le texte cherché est introuvable. "
                   f"L'indentation et les espaces doivent correspondre exactement.",
        )
    if occurrences > 1:
        return EditOutcome(
            block=bloc, would_apply=False,
            reason=f"« {bloc.path} » : le texte cherché apparaît {occurrences} fois. "
                   f"Ajoutez des lignes de contexte pour désigner laquelle.",
        )

    en_cours[cible] = contenu.replace(cherche, remplace, 1)
    return EditOutcome(block=bloc, would_apply=True, created=cible in a_creer)


def _adapter_aux_fins_de_ligne(contenu: str, bloc: EditBlock) -> Tuple[str, str]:
    """
    Aligne les fins de ligne du bloc sur celles du fichier.

    Un modèle écrit toujours en `\\n`. Un fichier venu de Windows est en
    `\\r\\n` : sans cette adaptation, aucune recherche n'aboutirait jamais sur
    un tel fichier, et le motif rendu — « texte introuvable » — enverrait
    chercher une faute d'indentation qui n'existe pas.

    Args:
        contenu: Le contenu actuel du fichier.
        bloc: Le bloc à appliquer.

    Returns:
        Le texte à chercher et celui à écrire, dans les fins de ligne du fichier.
    """
    if "\r\n" not in contenu or "\r\n" in bloc.search:
        return bloc.search, bloc.replace
    return (
        bloc.search.replace("\n", "\r\n"),
        bloc.replace.replace("\n", "\r\n"),
    )
