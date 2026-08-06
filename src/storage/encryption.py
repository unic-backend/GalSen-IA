"""
Chiffrement au repos des données stockées.

Le chapitre 08 du VOLET 02 demande de « chiffrer les données au repos ». Un
fichier SQLite copié depuis une sauvegarde, un disque revendu ou une machine
saisie livrent aujourd'hui les mémoires, les connaissances et les modèles en
clair. Ce module chiffre les champs qui portent le contenu réel.

Trois propriétés commandent la conception :

- **Rien ne casse quand on active le chiffrement.** Une base écrite en clair
  reste lisible : une valeur sans marque est rendue telle quelle. Sans cela,
  activer la protection détruirait les données existantes.
- **Une clé mal formée arrête le démarrage.** Se rabattre silencieusement sur
  l'écriture en clair donnerait l'illusion d'être protégé, ce qui est pire que
  de ne pas l'être.
- **Une valeur illisible n'est jamais rendue.** Si le chiffrement est actif et
  qu'un champ ne se déchiffre pas — mauvaise clé, fichier corrompu —, l'erreur
  remonte. Rendre le texte chiffré comme s'il était le contenu serait une
  invention de plus.

La clé vient de l'environnement (`GALSEN_ENCRYPTION_KEY`), jamais du dépôt
(ADR-004). **La perdre, c'est perdre les données** : aucune récupération n'est
possible, et c'est le prix du chiffrement.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

KEY_VARIABLE = "GALSEN_ENCRYPTION_KEY"

# Marque en tête des valeurs chiffrées. Elle porte une version : changer
# d'algorithme un jour se fera sans deviner le format des valeurs déjà écrites.
ENCRYPTED_PREFIX = "galsen:v1:"


class EncryptionError(RuntimeError):
    """Levée quand une valeur ne peut pas être chiffrée ou déchiffrée."""


class EncryptionKeyError(RuntimeError):
    """Levée quand la clé de chiffrement est absente ou mal formée."""


def generate_key() -> str:
    """
    Produit une clé utilisable, à placer dans `GALSEN_ENCRYPTION_KEY`.

    Destinée à un opérateur qui met en place le chiffrement :

        python -c "from src.storage.encryption import generate_key; print(generate_key())"

    Returns:
        Une clé Fernet en base64 URL-safe.
    """
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode("ascii")


def is_enabled() -> bool:
    """Indique si une clé de chiffrement est configurée, sans la valider."""
    return bool(os.environ.get(KEY_VARIABLE, "").strip())


def _cipher():
    """
    Construit le chiffreur à partir de la clé de l'environnement.

    La clé est relue à chaque appel plutôt que gardée en attribut : elle ne
    subsiste ainsi dans aucun état sérialisable, comme les clés API.

    Raises:
        EncryptionKeyError: Si la clé est absente, mal formée, ou si la
            bibliothèque `cryptography` n'est pas installée.
    """
    brut = os.environ.get(KEY_VARIABLE, "").strip()
    if not brut:
        raise EncryptionKeyError(
            f"Aucune clé de chiffrement : renseignez {KEY_VARIABLE}."
        )

    try:
        from cryptography.fernet import Fernet
    except ImportError as error:  # pragma: no cover - dépend de l'installation
        raise EncryptionKeyError(
            "Le chiffrement au repos demande la bibliothèque 'cryptography' : "
            f"{error}"
        ) from error

    try:
        return Fernet(brut.encode("ascii"))
    except Exception as error:
        # Le message ne contient jamais la clé, seulement le nom de la variable.
        raise EncryptionKeyError(
            f"{KEY_VARIABLE} n'est pas une clé valide. Produisez-en une avec "
            "generate_key(). Le démarrage est interrompu plutôt que d'écrire en "
            "clair en laissant croire à une protection."
        ) from error


def encrypt(value: Optional[str]) -> Optional[str]:
    """
    Chiffre une valeur si le chiffrement est actif.

    Args:
        value: Le texte à protéger. `None` et la chaîne vide traversent tels
            quels : il n'y a rien à protéger, et les chiffrer ferait grossir la
            base sans rien cacher.

    Returns:
        La valeur chiffrée, préfixée, ou la valeur d'origine si le chiffrement
        n'est pas configuré.
    """
    if value is None or value == "" or not is_enabled():
        return value

    try:
        jeton = _cipher().encrypt(value.encode("utf-8")).decode("ascii")
    except EncryptionKeyError:
        raise
    except Exception as error:
        raise EncryptionError(f"Chiffrement impossible : {error}") from error

    return f"{ENCRYPTED_PREFIX}{jeton}"


def decrypt(value: Optional[str]) -> Optional[str]:
    """
    Déchiffre une valeur écrite par `encrypt`.

    Une valeur sans marque est rendue telle quelle : c'est ce qui permet
    d'activer le chiffrement sur une base existante sans la rendre illisible.
    Les anciennes lignes restent lisibles, les nouvelles sont protégées, et une
    réécriture les chiffre au passage.

    Raises:
        EncryptionError: Si la valeur est marquée comme chiffrée mais ne se
            déchiffre pas. Rendre le texte chiffré comme s'il était le contenu
            ferait passer un échec pour une donnée.
    """
    if value is None or not isinstance(value, str):
        return value

    if not value.startswith(ENCRYPTED_PREFIX):
        return value

    jeton = value[len(ENCRYPTED_PREFIX):]
    try:
        return _cipher().decrypt(jeton.encode("ascii")).decode("utf-8")
    except EncryptionKeyError:
        raise
    except Exception as error:
        raise EncryptionError(
            "Valeur chiffrée illisible : la clé ne correspond pas, ou la donnée "
            f"est corrompue ({type(error).__name__})."
        ) from error


def verify_key() -> None:
    """
    Vérifie au démarrage que la clé configurée est utilisable.

    Appelée quand le chiffrement est actif : mieux vaut refuser de démarrer que
    découvrir une clé invalide à la première écriture, une fois des données déjà
    servies.

    Raises:
        EncryptionKeyError: Si la clé est absente ou mal formée.
    """
    if not is_enabled():
        return

    temoin = "galsen"
    if decrypt(encrypt(temoin)) != temoin:  # pragma: no cover - sécurité
        raise EncryptionKeyError("La clé de chiffrement ne fait pas l'aller-retour.")
    logger.info("Chiffrement au repos actif.")
