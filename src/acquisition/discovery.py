"""
Trouver des documents là où le site les publie lui-même (ADR-021, étape 5).

Découvrir n'est pas explorer. Ce module lit ce qu'une institution **publie pour
être lu** — son `robots.txt`, son plan de site, son fil de nouvelles, une page
d'index déclarée — et il s'arrête là.

## Ce qui n'existe pas ici, et n'existera pas

- **Aucune exploration.** Profondeur 1 depuis un point d'entrée déclaré. Un lien
  trouvé *dans un document* n'est jamais suivi ; un lien hors du domaine est
  écarté et compté.
- **Aucune recherche libre.** « Cherche sur internet » n'entre par aucune porte :
  les points de départ viennent du registre, qu'une personne a écrit.
- **Aucune source non activée.** `discover()` refuse une source dont
  `enabled` est faux ou dont le rang n'est pas acquérable. C'est ce qui empêche
  ce module d'être un explorateur : aujourd'hui, il ne peut atteindre **aucune**
  source réelle, parce qu'aucune n'est activée.

## Pourquoi la découverte n'attend pas le portillon

Le portillon d'ADR-006 porte sur les **documents** : ce sont eux qui pèsent, se
citent et se conservent. Lire le plan de site d'une institution est autre chose —
c'est exactement le mécanisme par lequel un site annonce ce qu'il veut voir
indexé. Refuser de le lire ne protégerait personne et obligerait à deviner.

Ces lectures restent soumises au reste : source activée, `robots.txt` appliqué,
débit par hôte, même domaine, plafond par exécution.

## Ce que ce module ne voit pas

Un site sans plan de site, sans fil et sans page d'index déclarée ne rend rien —
et le rapport le dit, plutôt que de rendre une liste vide qui ressemble à un
site vide. Le repli, quand il existera, s'appelle « une personne colle des URL »
(mode `seed`), pas « on explore ».
"""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from ..knowledge_engine.source_registry import RANGS_ACQUERABLES
from .fetcher import fetch

#: Plafond par exécution. Un plan de site institutionnel peut porter des
#: dizaines de milliers d'entrées ; en prendre tout serait une exploration avec
#: un autre nom.
PLAFOND_PAR_EXECUTION = 200

#: Nombre de plans de site imbriqués suivis depuis un index. Un index **est** le
#: point d'entrée déclaré ; ses enfants sont donc encore la profondeur 1. Au-delà,
#: ce serait de l'exploration.
PLANS_IMBRIQUES_MAXIMUM = 5

#: Taille au-delà de laquelle un XML n'est pas analysé. `ElementTree` reste
#: exposé à l'expansion d'entités ; le plafond est ce qui borne le dégât, et il
#: est écrit ici plutôt que sous-entendu.
XML_MAXIMUM = 5 * 1024 * 1024

#: Schémas acceptés pour un candidat. Une URL découverte est une **donnée**
#: venue de l'extérieur : `javascript:` ou `data:` n'y ont rien à faire.
SCHEMAS = ("http", "https")

#: Les modes de découverte, dans l'ordre où ils sont essayés.
MODES = ("sitemap", "feed", "index", "seed")

_LIEN_HTML = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"'#>]+)["']""", re.IGNORECASE)
_SITEMAP_ROBOTS = re.compile(r"^\s*sitemap\s*:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


class DiscoveryRefused(ValueError):
    """La découverte est refusée : la source n'est pas activée, ou pas acquérable."""


def _hote(url: str) -> str:
    """Retourne l'hôte d'une URL, en minuscules."""
    return (urlparse(str(url or "")).hostname or "").lower()


def _meme_domaine(url: str, domaine: str) -> bool:
    """
    Indique si une URL relève du domaine déclaré, sous-domaines compris.

    La comparaison porte sur les étiquettes, jamais sur la fin de la chaîne :
    sinon `faux-ansd.sn` passerait pour `ansd.sn`, ce qui est exactement
    l'erreur que le registre corrige déjà ailleurs.
    """
    hote = _hote(url)
    if not hote or not domaine:
        return False
    return hote == domaine or hote.endswith("." + domaine)


def sitemaps_from_robots(robots_txt: str) -> List[str]:
    """Retourne les plans de site annoncés par un `robots.txt`."""
    return [ligne.strip() for ligne in _SITEMAP_ROBOTS.findall(robots_txt or "")]


def _analyser_xml(contenu: bytes) -> Optional[Any]:
    """Analyse un XML, ou rend None — un XML illisible n'est pas une panne."""
    if not contenu or len(contenu) > XML_MAXIMUM:
        return None
    try:
        return ElementTree.fromstring(contenu)
    except ElementTree.ParseError:
        return None


def _sans_espace_de_noms(balise: str) -> str:
    """Retourne le nom local d'une balise, sans son espace de noms."""
    return balise.rsplit("}", 1)[-1].lower()


def urls_from_sitemap(contenu: bytes) -> Tuple[List[str], List[str]]:
    """
    Lit un plan de site.

    Returns:
        `(urls, plans_imbriques)` — un `<sitemapindex>` rend des plans, un
        `<urlset>` rend des documents. Les confondre ferait entrer des plans de
        site dans la base comme s'ils étaient des documents.
    """
    racine = _analyser_xml(contenu)
    if racine is None:
        return [], []

    index = _sans_espace_de_noms(racine.tag) == "sitemapindex"
    adresses = [
        (element.text or "").strip()
        for element in racine.iter()
        if _sans_espace_de_noms(element.tag) == "loc" and (element.text or "").strip()
    ]
    return ([], adresses) if index else (adresses, [])


def urls_from_feed(contenu: bytes) -> List[str]:
    """Lit un fil RSS ou Atom et rend les adresses de ses entrées."""
    racine = _analyser_xml(contenu)
    if racine is None:
        return []

    adresses = []
    for element in racine.iter():
        nom = _sans_espace_de_noms(element.tag)
        if nom != "link":
            continue
        # RSS met l'adresse dans le texte, Atom dans `href`. Lire un seul des
        # deux rendrait la moitié des fils invisibles.
        valeur = (element.get("href") or element.text or "").strip()
        if valeur:
            adresses.append(valeur)
    return adresses


def links_from_html(contenu: bytes, base_url: str) -> List[str]:
    """Retourne les liens d'une page d'index, résolus contre son adresse."""
    texte = contenu.decode("utf-8", errors="replace") if contenu else ""
    return [urljoin(base_url, lien.strip()) for lien in _LIEN_HTML.findall(texte)]


def _retenir(
    adresses: List[str],
    mode: str,
    domaine: str,
    vus: set,
    candidats: List[Dict[str, str]],
    ecartes: List[Dict[str, str]],
    plafond: int,
) -> None:
    """Filtre des adresses et les range en candidats ou en écartés, avec la raison."""
    for adresse in adresses:
        if len(candidats) >= plafond:
            ecartes.append({"url": adresse, "reason": f"Plafond de {plafond} atteint."})
            continue
        if urlparse(adresse).scheme not in SCHEMAS:
            ecartes.append({"url": adresse, "reason": "Schéma non acceptable."})
            continue
        if not _meme_domaine(adresse, domaine):
            ecartes.append({
                "url": adresse,
                "reason": f"Hors du domaine « {domaine} » : profondeur 1, même domaine.",
            })
            continue
        if adresse in vus:
            continue
        vus.add(adresse)
        candidats.append({"url": adresse, "mode": mode})


def discover(
    source: Dict[str, Any],
    *,
    robots_txt: str = "",
    feeds: Optional[List[str]] = None,
    index_pages: Optional[List[str]] = None,
    seeds: Optional[List[str]] = None,
    max_links: int = PLAFOND_PAR_EXECUTION,
    fetch_fn: Callable[..., Any] = fetch,
) -> Dict[str, Any]:
    """
    Découvre des documents candidats pour **une** source activée.

    Args:
        source: L'entrée du registre (`load_registry()["sources"][i]`).
        robots_txt: Le fichier du domaine, déjà récupéré.
        feeds: Fils déclarés, s'il y en a.
        index_pages: Pages d'index déclarées.
        seeds: URL collées par une personne — filtrées comme les autres.
        max_links: Plafond par exécution.
        fetch_fn: Le récupérateur, injectable pour les tests.

    Returns:
        Les candidats avec le mode qui les a produits, les écartés **avec leur
        raison**, et les modes qui n'ont rien rendu. Aucun document n'est
        récupéré ici : ce sont des adresses.

    Raises:
        DiscoveryRefused: Si la source n'est pas activée, ou si son rang n'est
            pas acquérable. C'est ce qui empêche ce module d'être un explorateur.
    """
    nom = source.get("name", "source inconnue")
    if not source.get("enabled"):
        raise DiscoveryRefused(
            f"« {nom} » n'est pas activée. Inscrire une source ne la rend pas "
            "collectable : l'activer est une modification relue du registre."
        )
    if source.get("tier") not in RANGS_ACQUERABLES:
        raise DiscoveryRefused(
            f"« {nom} » est de rang {getattr(source.get('tier'), 'value', '?')} : "
            "une piste, jamais une source. Elle peut faire chercher un document "
            "ailleurs, elle n'est pas collectée."
        )

    domaine = source["domain"]
    types = source.get("allowed_content_types") or []
    debit = (source.get("access_policy") or {}).get("rate_limit_rps", 0.2)
    candidats: List[Dict[str, str]] = []
    ecartes: List[Dict[str, str]] = []
    vus: set = set()
    rendus: Dict[str, int] = {mode: 0 for mode in MODES}

    def _lire(url: str, types_attendus: List[str]) -> bytes:
        """Récupère une ressource de découverte, ou rend vide."""
        try:
            resultat = fetch_fn(
                url, allowed_content_types=types_attendus, robots_txt=robots_txt,
                rate_limit_rps=debit,
            )
            return resultat.body
        except Exception:  # noqa: BLE001 — une ressource absente n'est pas une panne
            return b""

    # 1. Plans de site — le mode le plus fiable, parce que le site le publie
    #    précisément pour être lu.
    for plan in sitemaps_from_robots(robots_txt)[:PLANS_IMBRIQUES_MAXIMUM]:
        if not _meme_domaine(plan, domaine):
            ecartes.append({"url": plan, "reason": "Plan de site hors du domaine."})
            continue
        adresses, imbriques = urls_from_sitemap(_lire(plan, ["xml"]))
        for enfant in imbriques[:PLANS_IMBRIQUES_MAXIMUM]:
            if _meme_domaine(enfant, domaine):
                petites, _ = urls_from_sitemap(_lire(enfant, ["xml"]))
                adresses.extend(petites)
        avant = len(candidats)
        _retenir(adresses, "sitemap", domaine, vus, candidats, ecartes, max_links)
        rendus["sitemap"] += len(candidats) - avant

    # 2. Fils, 3. pages d'index déclarées, 4. semis collés par une personne.
    for url in feeds or []:
        avant = len(candidats)
        _retenir(urls_from_feed(_lire(url, ["xml"])), "feed", domaine, vus, candidats, ecartes, max_links)
        rendus["feed"] += len(candidats) - avant

    for url in index_pages or []:
        avant = len(candidats)
        _retenir(
            links_from_html(_lire(url, ["html"]), url),
            "index", domaine, vus, candidats, ecartes, max_links,
        )
        rendus["index"] += len(candidats) - avant

    avant = len(candidats)
    _retenir(list(seeds or []), "seed", domaine, vus, candidats, ecartes, max_links)
    rendus["seed"] += len(candidats) - avant

    return {
        "source": nom,
        "domain": domaine,
        "allowed_content_types": types,
        "candidates": candidats,
        "dropped": ecartes,
        "by_mode": rendus,
        "modes_without_result": [mode for mode, compte in rendus.items() if compte == 0],
        "depth": 1,
        "note": (
            "Profondeur 1 depuis un point d'entrée déclaré. Aucun lien trouvé dans "
            "un document n'est suivi, aucun lien hors du domaine n'est retenu, et "
            "rien n'est récupéré ici : ce sont des adresses."
        ),
    }


def discovery_report() -> Dict[str, Any]:
    """Décrit ce que la découverte fait et ne fait pas, sans rien découvrir."""
    return {
        "modes": list(MODES),
        "depth": 1,
        "same_domain_only": True,
        "follows_links_inside_documents": False,
        "free_web_search": False,
        "max_links_per_run": PLAFOND_PAR_EXECUTION,
        "nested_sitemaps": PLANS_IMBRIQUES_MAXIMUM,
        "requires_enabled_source": True,
        "not_detected": [
            "un site qui ne publie ni plan de site, ni fil, ni page d'index — il "
            "ne rend rien, et le rapport le dit plutôt que de ressembler à un site vide",
            "un document publié uniquement derrière un formulaire de recherche : le "
            "mode est exclu du pilote (ADR-021)",
            "l'expansion d'entités XML au-delà du plafond de taille : `ElementTree` "
            "y reste exposé, et le plafond est ce qui borne le dégât",
        ],
    }
