"""
Récupérer un document, poliment et sans mentir (ADR-021, étape 3).

C'est le seul module du projet qui envoie une requête à quelqu'un d'autre. Tout
ce qu'il contient existe pour une raison qui n'est pas technique : le serveur
d'en face appartient à une institution qui n'a rien demandé.

## Ce qui n'était pas possible avant

`src/tools/browser/tool.py` récupère des pages depuis longtemps. Il ne pouvait
pas servir ici, et pas pour une question de code :

- il annonce `Mozilla/5.0 … Chrome/91`, **ce qu'il n'est pas**. Un site ne peut
  pas appliquer une règle à un agent qui se déguise, ce qui vide `robots.txt` de
  son sens avant même de le lire ;
- il n'a ni limite de débit, ni plafond de taille, ni liste de types acceptés ;
- il suit les redirections **n'importe où**, ce qui traverse la limite « même
  domaine » sans qu'aucune ligne ne la franchisse explicitement.

## Cinq refus

1. **Un agent qui se fait passer pour un navigateur est refusé** — dans le code,
   pas dans une consigne : `_verifier_l_agent()` lève.
2. **`robots.txt` est récupéré avant la page**, et appliqué par l'évaluateur qui
   existe déjà (`knowledge_engine/collection.robots_disallows`).
3. **Une redirection hors du domaine est refusée**, jamais suivie.
4. **Un type de contenu non déclaré est refusé.** Une liste vide veut dire
   « rien n'est permis », pas « tout ».
5. **HTTP en clair est refusé**, sauf sur la boucle locale — la seule exception,
   et elle est bornée par l'adresse, pas par un drapeau qu'un appelant pourrait
   passer.

## Ce que ce module ne décide pas

Il ne décide pas **si** un document doit être collecté : c'est
`collection.decide()` et l'approbation humaine, en amont. Il exécute une
décision déjà prise, et refuse d'exécuter ce qui sort du cadre.
"""

import os
import time
from dataclasses import dataclass, field
from ipaddress import ip_address
from typing import Any, Dict, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..knowledge_engine.collection import robots_disallows

#: Agent déclaré. Véridique par construction : il dit ce qu'il est et où
#: écrire. Surchargeable par l'environnement pour y mettre un contact réel.
AGENT_PAR_DEFAUT = "GalSenIA-Acquisition/0.1 (+https://github.com/unic-backend/GalSen-IA)"

#: Marques d'un agent qui se fait passer pour un navigateur. Leur présence est
#: un refus : `robots.txt` ne veut rien dire face à un agent déguisé.
MARQUES_DE_DEGUISEMENT = ("mozilla", "chrome", "safari", "firefox", "edge/", "webkit")

#: Plafond de taille, en octets. Un document institutionnel dépasse rarement
#: quelques mégaoctets ; au-delà, c'est probablement autre chose.
TAILLE_MAXIMALE = 25 * 1024 * 1024

#: Délai d'attente par requête, en secondes.
DELAI = 30.0

#: Débit par défaut si la source n'en déclare pas, en requêtes par seconde.
DEBIT_PAR_DEFAUT = 0.2


class FetchRefused(ValueError):
    """La récupération est refusée, et le message dit laquelle des règles s'y oppose."""


class _RefusDeRedirection(HTTPRedirectHandler):
    """
    Suit une redirection **dans le même domaine**, refuse les autres.

    Sans cela, la limite « même domaine » de l'ADR-021 se franchit sans qu'aucune
    ligne du projet ne la franchisse : le serveur redirige, `urllib` suit, et le
    pipeline se retrouve ailleurs sans l'avoir décidé.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Refuse une redirection qui change d'hôte."""
        if _hote(req.full_url) != _hote(newurl):
            raise FetchRefused(
                f"Redirection hors du domaine refusée : {_hote(req.full_url)} → "
                f"{_hote(newurl)}. La limite « même domaine » est dans l'ADR-021."
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass
class FetchResult:
    """Ce qu'une récupération rapporte, y compris quand elle ne rapporte rien."""

    url: str
    status: int
    body: bytes = b""
    content_type: str = ""
    etag: str = ""
    last_modified: str = ""
    size: int = 0
    unchanged: bool = False
    headers: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Retourne le résultat sans son corps, pour un journal ou un rapport."""
        return {
            "url": self.url,
            "status": self.status,
            "content_type": self.content_type,
            "etag": self.etag,
            "last_modified": self.last_modified,
            "size": self.size,
            "unchanged": self.unchanged,
        }


def _hote(url: str) -> str:
    """Retourne l'hôte d'une URL, en minuscules."""
    return (urlparse(str(url or "")).hostname or "").lower()


def _est_locale(hote: str) -> bool:
    """
    Indique si un hôte est la boucle locale.

    C'est la seule exception à l'exigence de HTTPS, et elle sert aux tests : un
    serveur de test n'a pas de certificat, et exiger un vrai hôte pour tester la
    récupération ferait des tests qui appellent des tiers.
    """
    if hote in ("localhost", "localhost.localdomain"):
        return True
    try:
        return ip_address(hote).is_loopback
    except ValueError:
        return False


def user_agent() -> str:
    """Retourne l'agent déclaré, depuis l'environnement ou par défaut."""
    return os.environ.get("GALSEN_ACQUISITION_USER_AGENT", "").strip() or AGENT_PAR_DEFAUT


def _verifier_l_agent(agent: str) -> str:
    """
    Refuse un agent qui se fait passer pour un navigateur.

    Raises:
        FetchRefused: Si l'agent porte une marque de déguisement.
    """
    minuscule = agent.lower()
    for marque in MARQUES_DE_DEGUISEMENT:
        if marque in minuscule:
            raise FetchRefused(
                f"L'agent déclaré contient « {marque} » : il se fait passer pour un "
                "navigateur. Un site ne peut pas appliquer une règle à un agent "
                "déguisé, et la conformité à robots.txt devient un mot vide."
            )
    if not agent.strip():
        raise FetchRefused("Un agent vide ne dit pas qui appelle.")
    return agent


class HostRateLimiter:
    """
    Une attente par hôte, pas une attente globale.

    Un débit global ralentirait tout le monde pour ménager un seul site ; un
    débit par hôte fait ce qui est demandé — ne pas charger **ce** serveur.
    """

    def __init__(self) -> None:
        self._dernier: Dict[str, float] = {}

    def wait(self, hote: str, debit: float) -> float:
        """
        Attend ce qu'il faut avant d'appeler cet hôte, et retourne l'attente.

        Args:
            hote: L'hôte visé.
            debit: Requêtes par seconde autorisées pour cet hôte.
        """
        if debit <= 0:
            raise FetchRefused(f"Débit nul ou négatif pour « {hote} » : rien ne peut passer.")
        intervalle = 1.0 / debit
        precedent = self._dernier.get(hote)
        attente = 0.0
        if precedent is not None:
            attente = max(0.0, intervalle - (time.monotonic() - precedent))
            if attente:
                time.sleep(attente)
        self._dernier[hote] = time.monotonic()
        return attente


#: Limiteur partagé par le processus : deux appels au même hôte depuis deux
#: endroits du code doivent se ralentir l'un l'autre, sinon la limite ne limite
#: que chaque appelant pris séparément.
_LIMITEUR = HostRateLimiter()


def _ouvrir(url: str, entetes: Dict[str, str], delai: float) -> Tuple[int, Any]:
    """
    Ouvre une URL et retourne son code et sa réponse.

    Un 304 et un 404 ne sont pas des pannes : ce sont des réponses, et les
    traiter comme des exceptions obligerait chaque appelant à rattraper.
    """
    ouvreur = build_opener(_RefusDeRedirection)
    requete = Request(url, headers=entetes)
    try:
        reponse = ouvreur.open(requete, timeout=delai)
        return reponse.status, reponse
    except HTTPError as erreur:
        return erreur.code, erreur


def _verifier_le_schema(url: str) -> None:
    """Refuse ce qui n'est ni HTTPS, ni la boucle locale en clair."""
    decoupee = urlparse(url)
    if decoupee.scheme == "https":
        return
    if decoupee.scheme == "http" and _est_locale(_hote(url)):
        return
    raise FetchRefused(
        f"Schéma « {decoupee.scheme or 'aucun'} » refusé pour {url}. "
        "HTTPS est exigé : en clair, ni l'origine ni le contenu ne sont garantis."
    )


def fetch_robots(base_url: str, delai: float = DELAI) -> str:
    """
    Récupère le `robots.txt` d'un hôte, **avant** toute page.

    Returns:
        Le contenu du fichier, ou une chaîne vide s'il est absent — c'est sa
        sémantique, et inventer une interdiction empêcherait de collecter une
        source parfaitement ouverte.
    """
    hote = _hote(base_url)
    if not hote:
        raise FetchRefused(f"« {base_url} » n'a pas d'hôte : rien à interroger.")

    schema = urlparse(base_url).scheme or "https"
    url = f"{schema}://{urlparse(base_url).netloc}/robots.txt"
    _verifier_le_schema(url)
    _LIMITEUR.wait(hote, DEBIT_PAR_DEFAUT)

    code, reponse = _ouvrir(url, {"User-Agent": _verifier_l_agent(user_agent())}, delai)
    try:
        if code != 200:
            return ""
        return reponse.read(TAILLE_MAXIMALE).decode("utf-8", errors="replace")
    except URLError:
        return ""
    finally:
        if hasattr(reponse, "close"):
            reponse.close()


def fetch(
    url: str,
    *,
    allowed_content_types: Optional[list] = None,
    robots_txt: Optional[str] = None,
    rate_limit_rps: float = DEBIT_PAR_DEFAUT,
    etag: str = "",
    last_modified: str = "",
    max_bytes: int = TAILLE_MAXIMALE,
    delai: float = DELAI,
) -> FetchResult:
    """
    Récupère un document, une fois, en respectant ce que le site autorise.

    Args:
        url: L'adresse visée.
        allowed_content_types: Types déclarés par la source (`pdf`, `html`…).
            **Vide veut dire « rien n'est permis »** : un type non déclaré est
            un type que personne n'a relu.
        robots_txt: Le fichier déjà récupéré. S'il n'est pas fourni, il est
            **récupéré d'abord** — jamais supposé permissif.
        rate_limit_rps: Débit autorisé pour cet hôte.
        etag, last_modified: Pour un GET conditionnel. Un document inchangé
            coûte alors un 304 et rien d'autre.
        max_bytes: Plafond de taille. Dépassement = refus, pas troncature : un
            document tronqué est un document qui ment sur son contenu.

    Returns:
        Le résultat, avec `unchanged=True` sur un 304.

    Raises:
        FetchRefused: Agent déguisé, schéma en clair, `robots.txt` interdisant,
            redirection hors domaine, type non déclaré, ou taille dépassée.
    """
    agent = _verifier_l_agent(user_agent())
    _verifier_le_schema(url)

    hote = _hote(url)
    types = [str(t).lower().strip() for t in (allowed_content_types or [])]
    if not types:
        raise FetchRefused(
            f"Aucun type de contenu déclaré pour {hote}. Une liste vide veut dire "
            "« rien n'est permis » : déclarer `allowed_content_types` dans le registre."
        )

    if robots_txt is None:
        robots_txt = fetch_robots(url, delai=delai)
    interdit = robots_disallows(robots_txt, url, agent=agent)
    if interdit:
        raise FetchRefused(
            f"robots.txt interdit « {interdit} » pour cet agent. La règle est "
            "appliquée, pas consultée pour information."
        )

    entetes = {"User-Agent": agent, "Accept-Encoding": "identity"}
    if etag:
        entetes["If-None-Match"] = etag
    if last_modified:
        entetes["If-Modified-Since"] = last_modified

    _LIMITEUR.wait(hote, rate_limit_rps)
    code, reponse = _ouvrir(url, entetes, delai)

    try:
        if code == 304:
            return FetchResult(url=url, status=304, unchanged=True)
        if code != 200:
            raise FetchRefused(f"Réponse HTTP {code} pour {url}.")

        type_de_contenu = (reponse.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if not _type_accepte(type_de_contenu, types):
            raise FetchRefused(
                f"Type « {type_de_contenu or 'non déclaré'} » non autorisé pour cette "
                f"source ; déclarés : {', '.join(types)}."
            )

        corps = reponse.read(max_bytes + 1)
        if len(corps) > max_bytes:
            raise FetchRefused(
                f"Document au-delà du plafond ({max_bytes} octets). Il est refusé, "
                "pas tronqué : un document tronqué ment sur son contenu."
            )

        return FetchResult(
            url=url,
            status=200,
            body=corps,
            content_type=type_de_contenu,
            etag=(reponse.headers.get("ETag") or "").strip(),
            last_modified=(reponse.headers.get("Last-Modified") or "").strip(),
            size=len(corps),
            headers={
                "Content-Type": type_de_contenu,
                "Content-Length": str(len(corps)),
            },
        )
    finally:
        if hasattr(reponse, "close"):
            reponse.close()


#: Correspondance entre un type déclaré au registre et les types MIME réels.
TYPES_MIME = {
    "pdf": ("application/pdf",),
    "html": ("text/html", "application/xhtml+xml"),
    "xml": ("application/xml", "text/xml", "application/rss+xml", "application/atom+xml"),
    "text": ("text/plain",),
    "json": ("application/json",),
    "csv": ("text/csv",),
    "geojson": ("application/geo+json", "application/vnd.geo+json"),
    # Git LFS sert son contenu en `application/octet-stream`, quel que soit le
    # format réel du fichier. Le type doit donc être **déclarable** — mais il
    # reste déclaré source par source : accepter l'octet brut partout ferait
    # entrer n'importe quoi sous couvert de « le serveur n'a pas dit ».
    "binary": ("application/octet-stream",),
}


def _type_accepte(mime: str, declares: list) -> bool:
    """Indique si un type MIME correspond à l'un des types déclarés."""
    for declare in declares:
        if mime in TYPES_MIME.get(declare, (declare,)):
            return True
    return False


def fetcher_report() -> Dict[str, Any]:
    """Décrit ce que le récupérateur applique, pour qui veut le vérifier sans lire le code."""
    return {
        "user_agent": user_agent(),
        "impersonation_refused": list(MARQUES_DE_DEGUISEMENT),
        "max_bytes": TAILLE_MAXIMALE,
        "default_rate_limit_rps": DEBIT_PAR_DEFAUT,
        "timeout_seconds": DELAI,
        "https_required": True,
        "https_exception": "boucle locale uniquement, pour les tests",
        "cross_domain_redirects": "refused",
        "robots_txt": "fetched before the page, applied — not consulted",
        "content_types": sorted(TYPES_MIME),
        "note": (
            "Ce module exécute une décision déjà prise (registre, robots, licence, "
            "approbation). Il ne décide pas qu'un document doit être collecté."
        ),
    }
