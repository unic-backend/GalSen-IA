"""
Où va la requête, et ce que le contenu récupéré a le droit d'être
(R06, STEP 6 et STEP 10).

## La décision que R03 a laissée à cette phase

Trois implémentations de récupération de page coexistent, et **aucune n'est la
meilleure sur toutes les dimensions** :

| | Schéma | IP privées | robots.txt | Agent déguisé refusé | Redirection hors domaine |
|---|---|---|---|---|---|
| `tools/browser` | non | non | non | **non — il se déguise** | non |
| `web-search-mcp` `fetch_page` | oui | **littérales seulement** | non | non | non |
| `acquisition/fetcher.py` | oui | boucle locale seule | **oui** | **oui** | **oui** |

Copier `fetch_page` aurait importé un garde plus faible que l'existant sur une
dimension et plus fort sur une autre — c'est ainsi qu'une plateforme se retrouve
avec deux demi-gardes.

**La décision : le contrôle d'adresse vit ici, une fois, et les appelants y
passent.** Ce module ne récupère rien. Il répond à une question — *cette URL
a-t-elle le droit d'être appelée ?* — et laisse la récupération à qui la fait
déjà.

## Ce que ce garde ajoute à ce qui existait

`acquisition/fetcher.py` refuse la boucle locale par une règle d'exception à
HTTPS ; il ne bloque ni `10.0.0.1`, ni `169.254.169.254`, l'adresse de
métadonnées des fournisseurs de nuage. `web-search-mcp` les bloque, et **sa
propre docstring nomme son trou** : *« les noms de domaine sont résolus par le
système, pas ici »*, donc un hôte qui résout vers `127.0.0.1` passe.

Ce module bloque les deux : les adresses littérales **et** les noms qui
résolvent vers une plage interdite.

## Ce qu'il ne prétend pas faire

**Il ne ferme pas la fenêtre de re-résolution.** Entre la vérification et la
connexion, le DNS peut répondre autre chose — c'est le *DNS rebinding*, et
seule une connexion à l'adresse déjà vérifiée le fermerait, ce qui appartient au
client HTTP et non à un garde d'URL. La fenêtre est **réduite**, pas supprimée,
et le dire vaut mieux que laisser croire l'inverse.

**Il ne remplace pas `robots.txt`.** La politesse reste dans
`acquisition/fetcher.py`, où elle est déjà tenue.

## Le contenu récupéré est une donnée (STEP 6)

Rien de neuf n'est construit pour cela : `security/trust.py` porte déjà sept
niveaux, `wrap()`, `inspect()` et la neutralisation des balises. Ce module s'y
branche et **refuse** de rendre un résultat de recherche autrement qu'enveloppé.

Une page web, un README, une issue, un post ou un résultat de recherche ne
peuvent pas passer devant une consigne système. Ils entrent comme `EXTERNAL` —
*hostile par défaut*, dans les mots de `trust.py`.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..security.trust import TrustLevel, wrap

#: Les seuls schémas appelables. `file:`, `gopher:` et les autres ne servent ici
#: qu'à lire ce qui n'est pas sur le web.
SCHEMES_AUTORISES = ("http", "https")

#: Les motifs de refus d'une URL. Séparés, parce qu'ils ne se corrigent pas de
#: la même façon.
SCHEMA_REFUSE = "SCHEME_NOT_ALLOWED"
HOTE_ABSENT = "NO_HOST"
ADRESSE_INTERNE = "INTERNAL_ADDRESS"
IDENTIFIANTS_DANS_L_URL = "CREDENTIALS_IN_URL"
RESOLUTION_IMPOSSIBLE = "RESOLUTION_FAILED"
MOTIFS_DE_REFUS = (SCHEMA_REFUSE, HOTE_ABSENT, ADRESSE_INTERNE,
                   IDENTIFIANTS_DANS_L_URL, RESOLUTION_IMPOSSIBLE)


class UrlRefused(ValueError):
    """Une URL qui n'a pas le droit d'être appelée."""


def _est_interne(adresse: ipaddress._BaseAddress) -> bool:
    """
    Dit si une adresse appartient à une plage qu'un appel sortant ne doit pas
    atteindre.

    Couvre la boucle locale, les plages privées, le lien-local — dont
    `169.254.169.254`, l'adresse de métadonnées des fournisseurs de nuage —, les
    plages réservées, le multicast et l'adresse non spécifiée.
    """
    if isinstance(adresse, ipaddress.IPv6Address) and adresse.ipv4_mapped:
        adresse = adresse.ipv4_mapped
    return bool(
        adresse.is_private or adresse.is_loopback or adresse.is_link_local
        or adresse.is_reserved or adresse.is_multicast
        or adresse.is_unspecified
    )


def _resoudre(hote: str) -> Tuple[List[str], Optional[str]]:
    """
    Résout un nom d'hôte en adresses.

    Returns:
        Les adresses trouvées, et l'erreur quand la résolution échoue. Une
        résolution impossible n'est **pas** traitée comme une autorisation.
    """
    try:
        infos = socket.getaddrinfo(hote, None)
    except (socket.gaierror, UnicodeError, ValueError) as erreur:
        return [], f"{type(erreur).__name__}: {erreur}"
    return sorted({info[4][0] for info in infos}), None


@dataclass(frozen=True)
class UrlVerdict:
    """
    Ce que le garde a décidé d'une URL, et pourquoi.

    Attributes:
        url: L'URL examinée, telle qu'elle a été fournie.
        allowed: Si l'appel est permis.
        refusals: Les motifs, chacun avec son explication.
        resolved: Les adresses obtenues, quand la résolution a eu lieu.
        resolved_checked: Si la résolution a été faite. `False` veut dire que
            seule la forme littérale a été vérifiée.
    """

    url: str
    allowed: bool
    refusals: Tuple[Dict[str, str], ...] = ()
    resolved: Tuple[str, ...] = ()
    resolved_checked: bool = False

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "url": self.url, "allowed": self.allowed,
            "refusals": [dict(r) for r in self.refusals],
            "resolved": list(self.resolved),
            "resolved_checked": self.resolved_checked,
            "note": ("La fenêtre de re-résolution DNS reste ouverte : elle est "
                     "réduite, pas supprimée."),
        }


def check_url(url: str, resolve: bool = True) -> UrlVerdict:
    """
    Dit si une URL a le droit d'être appelée, sans l'appeler.

    Args:
        url: L'URL à examiner.
        resolve: Si le nom d'hôte doit être résolu et ses adresses vérifiées.
            `False` ne vérifie que la forme littérale — utile hors ligne, et
            **le verdict le déclare** pour que personne ne le prenne pour un
            contrôle complet.

    Returns:
        Un `UrlVerdict`. Chaque refus nomme son motif et son explication.

    Note:
        Une résolution qui échoue **refuse**. Ne pas savoir où mène un nom n'est
        pas une permission d'y aller — c'est la même règle que `UNKNOWN` n'est
        pas `ALLOWED`, appliquée au DNS.
    """
    refus: List[Dict[str, str]] = []
    analyse = urlparse(str(url or ""))

    if analyse.scheme not in SCHEMES_AUTORISES:
        refus.append({
            "refusal": SCHEMA_REFUSE,
            "reason": (f"Schéma « {analyse.scheme} » non autorisé. Autorisés : "
                       f"{list(SCHEMES_AUTORISES)}."),
        })

    if analyse.username or analyse.password:
        refus.append({
            "refusal": IDENTIFIANTS_DANS_L_URL,
            "reason": ("L'URL porte des identifiants. Ils fuiraient dans les "
                       "journaux, la provenance et le cache."),
        })

    hote = (analyse.hostname or "").strip()
    if not hote:
        refus.append({"refusal": HOTE_ABSENT,
                      "reason": "L'URL n'a pas d'hôte."})
        return UrlVerdict(url=str(url), allowed=False, refusals=tuple(refus))

    adresses: List[str] = []
    resolution_faite = False

    try:
        litterale = ipaddress.ip_address(hote)
    except ValueError:
        litterale = None

    if litterale is not None:
        adresses = [hote]
        if _est_interne(litterale):
            refus.append({
                "refusal": ADRESSE_INTERNE,
                "reason": f"« {hote} » appartient à une plage interne.",
            })
    elif resolve:
        adresses, erreur = _resoudre(hote)
        resolution_faite = True
        if erreur is not None:
            refus.append({
                "refusal": RESOLUTION_IMPOSSIBLE,
                "reason": (f"« {hote} » ne se résout pas ({erreur}). Ne pas "
                           "savoir où mène un nom n'est pas une permission "
                           "d'y aller."),
            })
        else:
            internes = [a for a in adresses
                        if _est_interne(ipaddress.ip_address(a))]
            if internes:
                refus.append({
                    "refusal": ADRESSE_INTERNE,
                    "reason": (f"« {hote} » résout vers {internes}, dans une "
                               "plage interne. C'est le trou que "
                               "`web-search-mcp` nomme dans sa propre "
                               "docstring."),
                })

    return UrlVerdict(url=str(url), allowed=not refus, refusals=tuple(refus),
                      resolved=tuple(adresses),
                      resolved_checked=resolution_faite)


def guard_url(url: str, resolve: bool = True) -> str:
    """
    Rend l'URL si elle est appelable, lève sinon.

    Args:
        url: L'URL à vérifier.
        resolve: Voir `check_url`.

    Returns:
        L'URL, inchangée.

    Raises:
        UrlRefused: Avec **tous** les motifs, pas seulement le premier. Corriger
            un refus pour découvrir le suivant fait perdre deux fois le temps.
    """
    verdict = check_url(url, resolve=resolve)
    if not verdict.allowed:
        motifs = " ; ".join(r["reason"] for r in verdict.refusals)
        raise UrlRefused(f"URL refusée : {motifs}")
    return verdict.url


def as_data(content: Optional[str], origin: str,
            provider_id: str = "") -> Dict[str, Any]:
    """
    Enveloppe un contenu récupéré pour qu'il entre comme **donnée** (STEP 6).

    Args:
        content: Le contenu récupéré, conservé tel quel.
        origin: D'où il vient — une URL, un identifiant de source. Requis :
            c'est ce qui distingue deux sources dans la même invite.
        provider_id: Le fournisseur qui l'a rapporté, quand il est connu.

    Returns:
        L'enveloppe sérialisée, plus `provider_id` et `is_instruction: False`.

    Note:
        Le niveau est **toujours** `EXTERNAL`, jamais négociable par l'appelant.
        Un fournisseur de recherche rapporte ce qu'il a trouvé ailleurs ; même
        exécuté localement, le contenu vient d'un tiers. Laisser choisir le
        niveau reviendrait à laisser l'appelant décider qu'un README est une
        consigne.

        `security/trust.py` fait le travail : il relève les tournures qui
        s'adressent à un modèle, neutralise les balises, et fait voyager les
        soupçons avec le texte.
    """
    enveloppe = wrap(content, TrustLevel.EXTERNAL, origin)
    serialise = enveloppe.to_dict()
    serialise["provider_id"] = provider_id
    serialise["is_instruction"] = False
    serialise["note"] = (
        "Contenu récupéré : une donnée avec une origine, jamais une "
        "instruction. Il ne passe devant aucune consigne système, aucune "
        "permission et aucune règle de sécurité."
    )
    return serialise


def safety_report() -> Dict[str, Any]:
    """
    Ce que la couche de sûreté garantit, et ce qu'elle ne garantit pas.

    Returns:
        Le vocabulaire, les règles tenues, et les limites déclarées.
    """
    return {
        "allowed_schemes": list(SCHEMES_AUTORISES),
        "refusals": list(MOTIFS_DE_REFUS),
        "retrieved_content_level": TrustLevel.EXTERNAL.value,
        "reused_modules": ["security.trust"],
        "rules": [
            "Une adresse interne est refusée, littérale **ou** résolue.",
            "Une résolution impossible refuse : ne pas savoir n'est pas "
            "permettre.",
            "Des identifiants dans l'URL sont refusés : ils fuiraient dans les "
            "journaux et la provenance.",
            "Un refus nomme tous ses motifs, pas seulement le premier.",
            "Le contenu récupéré entre toujours en EXTERNAL, et l'appelant ne "
            "peut pas en décider autrement.",
        ],
        "not_guaranteed": [
            "La fenêtre de re-résolution DNS reste ouverte : le contrôle la "
            "réduit, il ne la ferme pas. La fermer demande de se connecter à "
            "l'adresse déjà vérifiée, ce qui appartient au client HTTP.",
            "`robots.txt` n'est pas relu ici : la politesse reste dans "
            "`acquisition/fetcher.py`, où elle est déjà tenue.",
            "Aucune récupération n'a lieu dans ce module.",
        ],
    }
