"""
Reframing is not cropping, and translating does not re-time.

Directive §22 lists the formats and ends on the instruction that carries the
work: *do not simply crop the original video.* A centre crop is one line of
code, produces a file of the right shape, and silently removes whatever was near
the edges — which in practice is the logo, the lower-third, and the speaker's
head when they sit off-centre. The output passes every dimensional check.

So adaptation here recomputes **positions** inside the new safe area rather than
cutting pixels, and reports what a naive centre crop *would* have lost. That
second part is what makes the rule checkable instead of merely stated: a test
can assert that the logo survives reframing and would not have survived a crop.

Directive §23 asks for language versions that preserve timing, visual identity
and scene structure. The temptation there is symmetrical and just as quiet: a
translated line runs long, so the cue is stretched to fit. It now drifts from
the picture it captions, and every later cue inherits the drift. **Timing is
preserved exactly**; a translation that will not fit its window is *flagged*,
because shortening a sentence is a translator's decision and stretching a cue is
a decision nobody made.

An untranslated cue stays untranslated and is named. Falling back to the source
language silently gives a viewer of the Arabic version a French line with no way
to tell whether that was intentional.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

#: Les formats déclarés (§22), en rapport largeur/hauteur.
FORMATS: Dict[str, Tuple[int, int]] = {
    "16:9": (16, 9),
    "9:16": (9, 16),
    "1:1": (1, 1),
    "4:5": (4, 5),
    "4:3": (4, 3),
    "2.39:1": (239, 100),
}

#: Marge de sécurité par défaut, en part de la plus petite dimension. Une
#: incrustation posée au bord disparaît sur un téléviseur qui surbalaye.
MARGE_SECURITE = 0.05


class AdaptationRefused(ValueError):
    """Une adaptation qui ne peut pas être faite telle qu'elle est demandée."""


@dataclass(frozen=True)
class Placement:
    """
    Un élément placé, en coordonnées **relatives** au cadre.

    Les positions vont de 0 à 1 : c'est ce qui permet de reposer un élément dans
    un autre format sans le rogner. Des pixels absolus n'ont de sens que dans la
    taille où ils ont été écrits.

    Attributes:
        element_id: Son identité.
        x: Bord gauche, de 0 à 1.
        y: Bord haut, de 0 à 1.
        width: Largeur, de 0 à 1.
        height: Hauteur, de 0 à 1.
        anchor: Où l'élément doit rester — `center`, `top_left`, `bottom_left`,
            `top_right`, `bottom_right`, `bottom_center`, `top_center`.
        protected: Si l'élément ne doit jamais sortir du cadre (logo, visage).
    """

    element_id: str
    x: float
    y: float
    width: float
    height: float
    anchor: str = "center"
    protected: bool = False

    def __post_init__(self) -> None:
        for nom in ("x", "y", "width", "height"):
            valeur = getattr(self, nom)
            if not 0.0 <= valeur <= 1.0:
                raise AdaptationRefused(
                    f"« {self.element_id} » : {nom}={valeur} hors de [0, 1]. "
                    "Les coordonnées sont relatives au cadre — des pixels "
                    "absolus n'ont de sens que dans la taille où ils ont été "
                    "écrits."
                )
        if self.width <= 0 or self.height <= 0:
            raise AdaptationRefused(
                f"« {self.element_id} » n'a pas de surface."
            )

    @property
    def center(self) -> Tuple[float, float]:
        """Le centre de l'élément."""
        return (self.x + self.width / 2, self.y + self.height / 2)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "element_id": self.element_id, "x": round(self.x, 4),
            "y": round(self.y, 4), "width": round(self.width, 4),
            "height": round(self.height, 4), "anchor": self.anchor,
            "protected": self.protected,
        }


def aspect_of(format_name: str) -> float:
    """
    Le rapport largeur/hauteur d'un format déclaré.

    Raises:
        AdaptationRefused: Pour un format inconnu — en deviner un produirait
            un fichier d'une forme que personne n'a demandée.
    """
    if format_name not in FORMATS:
        raise AdaptationRefused(
            f"Format « {format_name} » non déclaré. Déclarés : "
            f"{sorted(FORMATS)}."
        )
    largeur, hauteur = FORMATS[format_name]
    return largeur / hauteur


def centre_crop_survivors(
    placements: Sequence[Placement], source: str, target: str,
) -> Dict[str, Any]:
    """
    Ce qu'un simple recadrage centré garderait — et ce qu'il perdrait.

    Args:
        placements: Les éléments placés dans le format source.
        source: Le format d'origine.
        target: Le format visé.

    Returns:
        Les éléments perdus et conservés. Cette fonction n'adapte rien : elle
        **mesure le coût** de la solution en une ligne que la directive §22
        refuse, pour que ce refus soit vérifiable au lieu d'être affirmé.
    """
    rapport_source = aspect_of(source)
    rapport_cible = aspect_of(target)

    if rapport_cible < rapport_source:
        # Cadre plus étroit : on coupe sur les côtés.
        part = rapport_cible / rapport_source
        gauche, droite = (1 - part) / 2, 1 - (1 - part) / 2
        haut, bas = 0.0, 1.0
    else:
        # Cadre plus haut : on coupe en haut et en bas.
        part = rapport_source / rapport_cible
        haut, bas = (1 - part) / 2, 1 - (1 - part) / 2
        gauche, droite = 0.0, 1.0

    perdus, gardes = [], []
    for element in placements:
        dedans = (
            element.x >= gauche and element.x + element.width <= droite
            and element.y >= haut and element.y + element.height <= bas
        )
        (gardes if dedans else perdus).append(element.element_id)

    return {
        "kept": gardes,
        "lost": perdus,
        "crop_box": {"left": round(gauche, 4), "right": round(droite, 4),
                     "top": round(haut, 4), "bottom": round(bas, 4)},
        "reason": (
            f"Un recadrage centré perdrait {len(perdus)} élément(s) : "
            f"{', '.join(perdus)}. En pratique c'est le logo, le bandeau bas et "
            "la tête du locuteur quand il n'est pas centré — et le fichier "
            "produit passe tous les contrôles de dimension."
            if perdus else
            "Un recadrage centré ne perdrait rien ici."
        ),
    }


def adapt(
    placements: Sequence[Placement], source: str, target: str,
    safe_margin: float = MARGE_SECURITE,
) -> Dict[str, Any]:
    """
    Repose les éléments dans le format visé, sans rien rogner.

    Args:
        placements: Les éléments placés dans le format source.
        source: Le format d'origine.
        target: Le format visé.
        safe_margin: La marge de sécurité, en part de cadre.

    Returns:
        Les nouveaux placements, ce qu'un recadrage aurait perdu, et les
        éléments protégés qui **ne tiennent pas** même après repositionnement.
        Ces derniers sont rapportés et non écrasés : un logo qui ne rentre pas
        est une décision de mise en page, pas un arrondi.

    Raises:
        AdaptationRefused: Format inconnu, ou marge hors de [0, 0.4].
    """
    if not 0.0 <= safe_margin <= 0.4:
        raise AdaptationRefused(
            f"Marge {safe_margin} hors de [0, 0.4] : au-delà, la zone utile "
            "disparaît."
        )
    aspect_of(source)
    aspect_of(target)

    bord_min, bord_max = safe_margin, 1 - safe_margin
    utile = bord_max - bord_min

    adaptes: List[Placement] = []
    ne_tiennent_pas: List[Dict[str, Any]] = []

    for element in placements:
        # Un élément plus grand que la zone utile est **rapporté**, jamais
        # réduit en silence : réduire un logo change une identité de marque.
        largeur = element.width
        hauteur = element.height
        if largeur > utile or hauteur > utile:
            ne_tiennent_pas.append({
                "element_id": element.element_id,
                "protected": element.protected,
                "reason": (
                    f"Occupe {round(max(largeur, hauteur), 3)} du cadre alors "
                    f"que la zone utile en fait {round(utile, 3)}. Le réduire "
                    "en silence changerait une mise en page que quelqu'un a "
                    "décidée."
                ),
            })

        centre_x, centre_y = element.center
        nouveau_x, nouveau_y = _reposer(
            element.anchor, centre_x, centre_y, largeur, hauteur,
            bord_min, bord_max,
        )
        adaptes.append(Placement(
            element_id=element.element_id,
            x=round(min(max(nouveau_x, 0.0), 1.0), 4),
            y=round(min(max(nouveau_y, 0.0), 1.0), 4),
            width=largeur, height=hauteur,
            anchor=element.anchor, protected=element.protected,
        ))

    recadrage = centre_crop_survivors(placements, source, target)
    return {
        "source": source, "target": target,
        "safe_margin": safe_margin,
        "placements": [element.as_dict() for element in adaptes],
        "objects": adaptes,
        "does_not_fit": ne_tiennent_pas,
        "crop_would_lose": recadrage["lost"],
        "note": (
            "Les éléments sont **reposés** dans la zone utile du format visé, "
            "pas rognés. Le coût d'un recadrage centré est mesuré à côté pour "
            "que le refus de la directive §22 soit vérifiable."
        ),
    }


def _reposer(
    anchor: str, centre_x: float, centre_y: float,
    largeur: float, hauteur: float, bord_min: float, bord_max: float,
) -> Tuple[float, float]:
    """Le coin haut-gauche d'un élément reposé selon son ancrage."""
    horizontales = {
        "left": bord_min,
        "right": bord_max - largeur,
        "center": centre_x - largeur / 2,
    }
    verticales = {
        "top": bord_min,
        "bottom": bord_max - hauteur,
        "center": centre_y - hauteur / 2,
    }

    parties = anchor.split("_")
    vertical = parties[0] if parties[0] in verticales else "center"
    horizontal = parties[1] if len(parties) > 1 and parties[1] in horizontales \
        else ("center" if anchor == "center" else "center")

    x = horizontales.get(horizontal, centre_x - largeur / 2)
    y = verticales.get(vertical, centre_y - hauteur / 2)
    return (min(max(x, bord_min), bord_max - largeur),
            min(max(y, bord_min), bord_max - hauteur))


def localise_cues(
    cues: Sequence[Any], translations: Dict[int, str], language: str,
) -> Dict[str, Any]:
    """
    Produit une version linguistique **au même minutage** (§23).

    Args:
        cues: Les sous-titres du master.
        translations: Le texte traduit, par index de sous-titre.
        language: La langue de la version.

    Returns:
        Les sous-titres traduits, ceux qui restent **non traduits et nommés**,
        et ceux dont la traduction ne tient pas dans sa fenêtre.

        Le minutage est repris **exactement**. Étirer un sous-titre trop long le
        ferait dériver de l'image qu'il légende, et chaque sous-titre suivant
        hériterait de la dérive : raccourcir une phrase est une décision de
        traducteur, étirer une fenêtre est une décision que personne n'a prise.

    Raises:
        AdaptationRefused: Langue non déclarée par le moteur de sous-titres.
    """
    from ..subtitles.cues import LANGUES, Cue, check_cue

    if language not in LANGUES:
        raise AdaptationRefused(
            f"Langue « {language} » non déclarée : son sens de lecture serait "
            "deviné."
        )

    traduits: List[Cue] = []
    manquants: List[Dict[str, Any]] = []
    trop_longs: List[Dict[str, Any]] = []

    for cue in cues:
        texte = translations.get(cue.index)
        if not texte or not str(texte).strip():
            manquants.append({
                "index": cue.index, "source_text": cue.text,
                "reason": (
                    "Non traduit. Retomber sur la langue source donnerait au "
                    "spectateur de la version " + language + " une ligne dans "
                    "une autre langue, sans moyen de savoir si c'est voulu."
                ),
            })
            continue

        # Minutage identique : c'est la garantie de la directive §23.
        traduit = Cue(index=cue.index, start=cue.start, end=cue.end,
                      text=str(texte), language=language,
                      emphasis=cue.emphasis)
        traduits.append(traduit)

        defauts = [p for p in check_cue(traduit)["problems"]
                   if p["kind"] == "too_fast"]
        if defauts:
            trop_longs.append({
                "index": cue.index, "cps": traduit.cps,
                "reason": (
                    "La traduction ne tient pas dans sa fenêtre. Elle n'est ni "
                    "étirée ni retimée : raccourcir la phrase est une décision "
                    "de traducteur."
                ),
            })

    return {
        "language": language,
        "direction": LANGUES[language]["direction"],
        "cues": [cue.as_dict() for cue in traduits],
        "objects": traduits,
        "untranslated": manquants,
        "too_long": trop_longs,
        "timing_preserved": True,
        "note": (
            "Le minutage du master est repris **exactement**. Étirer une "
            "fenêtre ferait dériver le sous-titre de l'image, et chaque "
            "sous-titre suivant hériterait de la dérive."
        ),
    }


def adaptation_report() -> Dict[str, Any]:
    """
    Ce que l'adaptation garantit, et ce qu'elle refuse.

    Returns:
        Les formats déclarés et les règles tenues.
    """
    return {
        "formats": {nom: list(rapport) for nom, rapport in sorted(FORMATS.items())},
        "safe_margin": MARGE_SECURITE,
        "rules": [
            "Les positions sont **relatives** au cadre : c'est ce qui permet "
            "de reposer un élément dans un autre format sans le rogner.",
            "Un recadrage centré est une ligne de code qui produit un fichier "
            "de la bonne forme et supprime le logo, le bandeau bas et la tête "
            "du locuteur décentré — le coût est **mesuré** à côté de chaque "
            "adaptation.",
            "Un élément plus grand que la zone utile est rapporté, jamais "
            "réduit : réduire un logo change une identité de marque.",
            "Une version linguistique reprend le minutage **exactement** : "
            "étirer une fenêtre ferait dériver le sous-titre de l'image, et "
            "chaque suivant hériterait de la dérive.",
            "Un sous-titre non traduit reste **non traduit et nommé** : "
            "retomber sur la langue source donne une ligne étrangère sans "
            "moyen de savoir si c'est voulu.",
        ],
        "does_not": [
            "Rogner la vidéo d'origine pour changer de format.",
            "Réduire un élément qui ne tient pas.",
            "Étirer ou retimer un sous-titre trop long.",
            "Remplacer une traduction manquante par la langue source.",
        ],
    }
