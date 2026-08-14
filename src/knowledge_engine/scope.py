"""
Les deux axes de la connaissance : d'où elle vaut, et de quoi elle parle
(VOLET 35, ch. 01).

Le brief du propriétaire : *« une IA internationale avec une base de connaissance
de classe mondiale et une expertise exceptionnelle sur le Sénégal »*. Le Sénégal
comme **force et identité**, jamais comme limite.

## Pourquoi une seule base, et deux axes

La tentation est de faire deux bases : « la mondiale » et « la sénégalaise ».
**Refusé**, pour une raison qui ne changera pas : une question sur le mil à
Kaolack a besoin des deux — l'agronomie du mil (mondiale) et les variétés, les
pluies et les prix du Sénégal (locale). Deux bases forceraient le récupérateur à
choisir, et il choisirait mal.

Une base, et chaque élément porte **deux étiquettes indépendantes** :

```
scope   : global | country:sn        — d'où cette connaissance vaut
subject : agriculture, law, health…  — de quoi elle parle
```

`KnowledgeDomain` reste ce qu'il est : il classe la documentation **de la
plateforme** (métier, technique, juridique…), ce qui est une autre question.
Fondre les deux donnerait une énumération à deux sens.

## Ce qui ne retombe jamais sur le mondial

Certains sujets ne se transportent pas d'un pays à l'autre. Répondre le droit
français à une question sur le foncier sénégalais serait **pire** que de ne pas
répondre : la réponse serait fluide, plausible, et fausse là où elle coûte cher.
`NATIONAL_SUBJECTS` les nomme, et le chapitre 04 les fera refuser plutôt que
compléter.

## Ce que ce module ne fait pas

Il n'embarque **pas** le registre ISO des pays. La forme du code est vérifiée —
deux lettres — et rien de plus : livrer une liste incomplète refuserait des pays
valides, ce qui est le défaut le plus difficile à voir. Une portée mal
orthographiée reste visible autrement : `scopes_report()` la montre comme une
portée à un seul élément.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

#: Forme d'un code pays ISO-3166 alpha-2. La forme est vérifiée, pas l'existence.
CODE_PAYS = re.compile(r"^[A-Z]{2}$")

#: Séparateur de la forme textuelle : `country:sn`.
SEPARATEUR = ":"

GLOBAL = "global"
PAYS = "country"


class ScopeRefused(ValueError):
    """Une portée malformée a été proposée."""


@dataclass(frozen=True)
class KnowledgeScope:
    """
    D'où une connaissance vaut.

    Attributes:
        kind: `global` ou `country`.
        country: Code ISO-3166 alpha-2 en majuscules, pour une portée nationale.

    Exemple:
        KnowledgeScope.parse("country:sn")   # KnowledgeScope('country', 'SN')
        str(KnowledgeScope.global_())        # 'global'
    """

    kind: str = GLOBAL
    country: Optional[str] = None

    def __post_init__(self) -> None:
        """Vérifie la cohérence de la portée à la construction."""
        if self.kind not in (GLOBAL, PAYS):
            raise ScopeRefused(
                f"Portée « {self.kind} » inconnue : attendu « {GLOBAL} » ou « {PAYS} »."
            )
        if self.kind == PAYS:
            if not self.country or not CODE_PAYS.match(self.country):
                raise ScopeRefused(
                    f"Portée nationale sans code pays valide : « {self.country} ». "
                    "Attendu deux lettres majuscules (ISO-3166 alpha-2), par "
                    "exemple « SN »."
                )
        elif self.country:
            # Une portée mondiale qui nomme un pays est une contradiction, et la
            # laisser passer ferait deux vérités sur le même élément.
            raise ScopeRefused(
                f"Portée mondiale et pays « {self.country} » à la fois : "
                "choisir l'un ou l'autre."
            )

    @classmethod
    def global_(cls) -> "KnowledgeScope":
        """Retourne la portée mondiale."""
        return cls(kind=GLOBAL)

    @classmethod
    def country_(cls, code: str) -> "KnowledgeScope":
        """Retourne la portée d'un pays."""
        return cls(kind=PAYS, country=(code or "").strip().upper())

    @classmethod
    def parse(cls, valeur: Any) -> "KnowledgeScope":
        """
        Lit une portée depuis sa forme textuelle.

        Args:
            valeur: `global`, `country:sn`, ou une `KnowledgeScope`.

        Raises:
            ScopeRefused: Forme inconnue. **Rien n'est deviné** : une portée mal
                écrite qui retomberait sur « mondial » ferait passer une
                connaissance locale pour universelle, ce qui est exactement
                l'erreur que ce VOLET existe pour empêcher.
        """
        if isinstance(valeur, cls):
            return valeur
        texte = str(valeur or "").strip().lower()
        if not texte:
            raise ScopeRefused("Portée vide : déclarer « global » ou « country:xx ».")
        if texte == GLOBAL:
            return cls.global_()
        if texte.startswith(PAYS + SEPARATEUR):
            return cls.country_(texte.split(SEPARATEUR, 1)[1])
        raise ScopeRefused(
            f"Portée « {valeur} » non reconnue : attendu « {GLOBAL} » ou "
            f"« {PAYS}{SEPARATEUR}xx »."
        )

    @property
    def is_global(self) -> bool:
        """Vraie pour la portée mondiale."""
        return self.kind == GLOBAL

    def __str__(self) -> str:
        """Rend la forme textuelle stockée en base."""
        return GLOBAL if self.is_global else f"{PAYS}{SEPARATEUR}{(self.country or '').lower()}"

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la portée."""
        return {"scope": str(self), "kind": self.kind, "country": self.country}


class KnowledgeSubject(Enum):
    """
    De quoi une connaissance parle.

    Fermée volontairement, comme `KnowledgeDomain` : un sujet que personne ne
    peut nommer ne peut recevoir ni propriétaire, ni cycle de revue, ni registre
    de sources. L'étendre est une modification de ce fichier — donc une décision
    relue, pas une chaîne libre qui apparaît un jour dans un manifeste.

    `UNSPECIFIED` dit « pas encore classé » et ne doit jamais passer pour un
    classement.
    """

    SCIENCE = "science"
    TECHNOLOGY = "technology"
    ENGINEERING = "engineering"
    HEALTH = "health"
    ECONOMICS = "economics"
    HISTORY = "history"
    CULTURE = "culture"
    EDUCATION = "education"
    LAW = "law"
    ADMINISTRATION = "administration"
    AGRICULTURE = "agriculture"
    FISHERIES = "fisheries"
    ENVIRONMENT = "environment"
    #: Architecture et construction (VOLET 55). Ajouté après relecture, comme
    #: l'exige cette énumération. Ce n'est pas un doublon d'`engineering` : la
    #: physique d'une poutre est universelle, ce qu'il est **permis** de bâtir
    #: ne l'est pas — voir `NORMATIVE_SUBJECTS` ci-dessous.
    CONSTRUCTION = "construction"
    #: Sport (VOLET 56). Ajouté après relecture, comme l'exige cette
    #: énumération. Sa particularité n'est pas le territoire mais le **temps** :
    #: un résultat est daté et définitif, un classement est daté et périme —
    #: voir `src/knowledge_engine/perishable.py`.
    SPORTS = "sports"
    GEOGRAPHY = "geography"
    LANGUAGES = "languages"
    BUSINESS = "business"
    SOCIETY = "society"
    GENERAL = "general"
    UNSPECIFIED = "unspecified"


#: Sujets qui **ne se transportent pas** d'un pays à l'autre. Pour eux, une
#: absence de source nationale se rend en « je n'ai pas cette information pour ce
#: pays » — jamais en connaissance mondiale déguisée en réponse locale.
#:
#: La liste est courte et chaque entrée porte sa raison :
#: - `law` : un texte de loi n'a d'existence que sur son territoire ;
#: - `administration` : les démarches, les pièces et les délais sont nationaux ;
#: - `languages` : le wolof ne s'explique pas par une grammaire générale.
NATIONAL_SUBJECTS = frozenset({
    KnowledgeSubject.LAW,
    KnowledgeSubject.ADMINISTRATION,
    KnowledgeSubject.LANGUAGES,
})

#: Sujets dont **une partie seulement** est territoriale (VOLET 55). Ils ne sont
#: pas dans `NATIONAL_SUBJECTS` : les couper du savoir mondial priverait d'une
#: physique qui, elle, est universelle. Mais leur part **normative** — ce qui est
#: prescrit, autorisé, exigé — est fixée par un territoire, et une norme
#: étrangère appliquée ici n'est pas une approximation, c'est une autre règle.
#:
#: La valeur dit ce qu'une source mondiale peut légitimement porter, et ce
#: qu'elle ne peut pas.
NORMATIVE_SUBJECTS: Dict[KnowledgeSubject, Dict[str, str]] = {
    KnowledgeSubject.CONSTRUCTION: {
        "universal": (
            "Matériaux, méthodes, comportement des structures : cela ne change "
            "pas de pays."
        ),
        "territorial": (
            "Règles de construction, normes parasismiques, permis, coefficients "
            "réglementaires : fixés par un territoire, souvent par décret. Une "
            "norme étrangère appliquée ici n'est pas une approximation, c'est "
            "une autre règle."
        ),
    },
}


def normative_split(subject: Any) -> Optional[Dict[str, str]]:
    """
    Ce qu'une source mondiale peut porter sur un sujet, et ce qu'elle ne peut pas.

    Args:
        subject: Le sujet.

    Returns:
        La part universelle et la part territoriale, ou `None` si le sujet n'est
        pas de ceux qui se coupent en deux.
    """
    try:
        sujet = parse_subject(subject)
    except ScopeRefused:
        return None
    return NORMATIVE_SUBJECTS.get(sujet)

#: En dessous de ce total, aucune portée n'est dite suspecte : sur une base
#: jeune, « une seule connaissance pour ce pays » est l'état normal, pas une
#: faute de frappe. Signaler dès le premier élément ferait crier au loup à chaque
#: nouveau pays, et le signal deviendrait invisible quand il compterait vraiment.
SEUIL_DE_SUSPICION = 20

#: Sujets où une réponse fausse coûte une santé. Le chapitre 10 y ajoutera un
#: plancher de fiabilité et des refus ; le sujet est nommé ici pour que les deux
#: chapitres parlent de la même chose.
SAFETY_CRITICAL_SUBJECTS = frozenset({KnowledgeSubject.HEALTH})


def parse_subject(valeur: Any) -> KnowledgeSubject:
    """
    Lit un sujet depuis sa forme textuelle.

    Un sujet inconnu **est refusé**, il ne retombe pas sur `UNSPECIFIED` : une
    faute de frappe dans un manifeste rendrait la connaissance introuvable par
    son sujet, et le silence la rendrait introuvable aussi par son auteur.
    """
    if isinstance(valeur, KnowledgeSubject):
        return valeur
    texte = str(valeur or "").strip().lower()
    if not texte:
        return KnowledgeSubject.UNSPECIFIED
    try:
        return KnowledgeSubject(texte)
    except ValueError:
        connus = ", ".join(sujet.value for sujet in KnowledgeSubject)
        raise ScopeRefused(f"Sujet « {valeur} » inconnu. Sujets déclarés : {connus}.")


def requires_national_source(subject: KnowledgeSubject) -> bool:
    """Indique si ce sujet interdit de répondre avec de la connaissance mondiale."""
    return subject in NATIONAL_SUBJECTS


def scopes_report(items: Iterable[Any]) -> Dict[str, Any]:
    """
    Décrit les portées et sujets réellement présents dans un ensemble d'éléments.

    C'est la mesure qui rend une portée mal orthographiée visible : elle
    apparaît comme une portée à un seul élément, au lieu de se fondre
    silencieusement dans « mondial ».
    """
    par_portee: Dict[str, int] = {}
    par_sujet: Dict[str, int] = {}
    for element in items:
        portee = str(getattr(element, "scope", GLOBAL) or GLOBAL)
        sujet = getattr(element, "subject", KnowledgeSubject.UNSPECIFIED)
        sujet = getattr(sujet, "value", str(sujet))
        par_portee[portee] = par_portee.get(portee, 0) + 1
        par_sujet[sujet] = par_sujet.get(sujet, 0) + 1

    total = sum(par_portee.values())
    nationaux = {portee: n for portee, n in par_portee.items() if portee != GLOBAL}
    return {
        "total": total,
        "by_scope": dict(sorted(par_portee.items())),
        "by_subject": dict(sorted(par_sujet.items())),
        "countries": sorted(nationaux),
        "unspecified_subject": par_sujet.get(KnowledgeSubject.UNSPECIFIED.value, 0),
        # Une portée seule au milieu d'une base fournie est très probablement
        # une faute de frappe. Le module la signale ; il ne la corrige pas.
        "suspicious_scopes": sorted(
            portee for portee, n in nationaux.items()
            if n == 1 and total >= SEUIL_DE_SUSPICION
        ),
        "suspicion_threshold": SEUIL_DE_SUSPICION,
    }


def known_subjects() -> List[str]:
    """Retourne les sujets déclarés, pour un manifeste ou une documentation."""
    return [sujet.value for sujet in KnowledgeSubject]
