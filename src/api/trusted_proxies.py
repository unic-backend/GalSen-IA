"""
À qui la plateforme croit quand une requête dit d'où elle vient.

`X-Forwarded-For` était lu sans condition : dès que l'en-tête était présent, sa
première valeur devenait l'identité du client. Sans proxy devant l'application —
c'est-à-dire dans l'état où elle se trouvait — **n'importe quel appelant pouvait
l'envoyer**, changer d'adresse à chaque requête et rendre inopérants les deux
mécanismes qui en dépendent :

- la limite de débit non authentifiée, comptée par adresse ;
- la détection de menaces (VOLET 11), qui signale une source répétant des échecs
  d'authentification.

Un en-tête forgé donnait donc un quota illimité *et* l'invisibilité.

`X-Forwarded-Proto` posait la même question en plus discret : il fait croire à
l'application que la requête est arrivée en HTTPS, ce qui décide de l'envoi de
l'en-tête HSTS.

La règle appliquée ici est la seule sûre : **un en-tête de transfert n'est cru
que s'il vient d'un proxy déclaré.** Sans `GALSEN_TRUSTED_PROXIES`, l'adresse
retenue est celle de la connexion, et les en-têtes sont ignorés — le défaut est
donc correct pour un déploiement sans proxy, et le devient pour un déploiement
avec proxy dès que l'opérateur le déclare.
"""

import ipaddress
import logging
import os
import re
from typing import List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

TRUSTED_PROXIES_VARIABLE = "GALSEN_TRUSTED_PROXIES"

# Adresse retenue quand la requête n'en porte aucune (client de test, socket
# Unix). Nommée : elle apparaît dans les rapports de menaces.
ADRESSE_INCONNUE = "unknown"

# Ce qui ressemble à une adresse mal écrite plutôt qu'à un nom d'hôte.
_RESSEMBLE_A_UNE_ADRESSE = re.compile(r"^[0-9.:/]+$")


def _declarations() -> Tuple[List[ipaddress._BaseNetwork], Set[str]]:
    """
    Retourne les proxys déclarés : réseaux d'adresses et noms exacts.

    Accepte des adresses (`10.0.0.5`), des blocs (`10.0.0.0/8`) et des **noms**
    (`caddy`). Le nom est comparé au pair tel que le serveur le voit — un nom de
    service Docker, une socket. Cette identité vient de la connexion elle-même,
    pas d'un en-tête : un appelant distant ne peut pas la choisir, la propriété
    de sécurité tient donc aussi pour cette forme.
    """
    brut = os.getenv(TRUSTED_PROXIES_VARIABLE, "")
    reseaux: List[ipaddress._BaseNetwork] = []
    noms: Set[str] = set()
    for entree in brut.split(","):
        entree = entree.strip()
        if not entree:
            continue
        try:
            reseaux.append(ipaddress.ip_network(entree, strict=False))
        except ValueError:
            if _RESSEMBLE_A_UNE_ADRESSE.match(entree):
                # « 10.0.0.300 » est une adresse ratée, pas un nom d'hôte : la
                # traiter comme un nom ferait taire une faute de frappe.
                logger.error(
                    "%s : entrée « %s » illisible, ignorée. Les en-têtes de "
                    "transfert de cette source ne seront pas acceptés.",
                    TRUSTED_PROXIES_VARIABLE, entree,
                )
            else:
                noms.add(entree)
    return reseaux, noms


def is_trusted_proxy(adresse: Optional[str]) -> bool:
    """
    Indique si une adresse fait partie des proxys déclarés.

    Args:
        adresse: adresse IP à tester.

    Returns:
        False si l'adresse est absente, illisible, ou hors des réseaux déclarés.
        Le défaut est de ne pas croire.
    """
    if not adresse:
        return False
    reseaux, noms = _declarations()
    if adresse in noms:
        return True
    try:
        ip = ipaddress.ip_address(adresse)
    except ValueError:
        return False
    return any(ip in reseau for reseau in reseaux)


def client_ip(request) -> str:
    """
    Retourne l'adresse du client, sans se laisser dicter par la requête.

    La chaîne `X-Forwarded-For` se lit **de droite à gauche** : chaque proxy
    ajoute son prédécesseur à la fin. On remonte donc la chaîne en écartant les
    proxys déclarés, et on s'arrête au premier hôte qui n'en est pas un — c'est
    le client réel. S'arrêter au premier élément de gauche serait naïf : cet
    élément est justement celui qu'un appelant contrôle.

    Args:
        request: la requête entrante.

    Returns:
        L'adresse du client, ou `"unknown"` si la requête n'en porte aucune.
    """
    pair = request.client.host if request.client else None

    if not is_trusted_proxy(pair):
        # Aucun proxy déclaré devant nous : ce que dit la requête sur son
        # origine n'engage qu'elle.
        return pair or ADRESSE_INCONNUE

    chaine = request.headers.get("X-Forwarded-For", "")
    maillons = [maillon.strip() for maillon in chaine.split(",") if maillon.strip()]
    for maillon in reversed(maillons):
        if not is_trusted_proxy(maillon):
            return maillon

    # Toute la chaîne est composée de proxys déclarés, ou elle est vide :
    # l'adresse la plus honnête reste celle du pair.
    return pair or ADRESSE_INCONNUE


def forwarded_proto(request) -> str:
    """
    Retourne le schéma d'origine de la requête (`http` ou `https`).

    `X-Forwarded-Proto` n'est cru que d'un proxy déclaré, pour la même raison
    que l'adresse : sans cela, un appelant peut faire croire à l'application
    qu'il est en HTTPS et lui faire poser un en-tête HSTS sur une réponse qui
    n'a jamais été chiffrée.
    """
    if request.url.scheme == "https":
        return "https"
    pair = request.client.host if request.client else None
    if is_trusted_proxy(pair):
        return request.headers.get("x-forwarded-proto", "").lower() or "http"
    return "http"
