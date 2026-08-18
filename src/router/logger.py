"""
Logger utility for the Router Engine.

Configures and provides logging instances based on application configuration.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from .config_loader import ConfigLoader


def _entier_positif(brut, defaut: int, minimum: int = 1) -> int:
    """
    Convertit une valeur d'environnement en entier, sans jamais lever.

    Args:
        brut: La valeur lue, ou None.
        defaut: La valeur retenue si la lecture échoue.
        minimum: Plancher accepté.

    Returns:
        L'entier demandé, ou `defaut` si la valeur est absente, illisible ou
        sous le plancher. Une configuration fautive ne doit pas déboucher sur un
        journal sans limite.
    """
    try:
        valeur = int(str(brut).strip())
    except (TypeError, ValueError):
        return defaut
    return valeur if valeur >= minimum else defaut


class Logger:
    """Gestionnaire de journalisation pour l'application."""

    def __init__(self, config_loader: ConfigLoader):
        """
        Initialise le gestionnaire de journalisation.

        Args:
            config_loader: Instance du chargeur de configuration.
        """
        self.config_loader = config_loader
        self._setup_logging()

    # Bornes du fichier de journal (VOLET_04 ch. 08, critère de sortie C5).
    # `logging.FileHandler` n'a aucune limite : le fichier avait atteint 6,7 Mo
    # et 43 638 lignes, et avait déjà cassé l'agent de supervision une fois
    # avant qu'un `tail` ne soit ajouté. 5 Mo × 3 archives plafonne l'espace à
    # 20 Mo, ce qui reste lisible sur une machine modeste tout en gardant assez
    # d'historique pour une enquête.
    TAILLE_MAX_JOURNAL = 5 * 1024 * 1024
    ARCHIVES_CONSERVEES = 3

    def _setup_logging(self) -> None:
        """Configure le système de journalisation basé sur la configuration."""
        log_level_str = self.config_loader.get('logging.level', 'info').upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        save_history = self.config_loader.get('logging.save_history', False)

        # Configuration de base du logging
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Si la sauvegarde de l'historique est configurée, ajouter un gestionnaire de fichier
        if save_history:
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            log_file = os.path.join(log_dir, "application.log")
            # `RotatingFileHandler` et non `FileHandler` : la croissance sans
            # limite est un incident différé, pas une économie.
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.taille_max_journal(),
                backupCount=self.archives_conservees(),
                encoding='utf-8',
            )
            file_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)

    @classmethod
    def taille_max_journal(cls) -> int:
        """
        Retourne la taille maximale d'un fichier de journal, en octets.

        Réglable par `GALSEN_LOG_MAX_BYTES`. Une valeur absente ou illisible
        retombe sur la valeur par défaut : un journal mal configuré doit rester
        borné, pas redevenir infini.
        """
        return _entier_positif(
            os.environ.get("GALSEN_LOG_MAX_BYTES"), cls.TAILLE_MAX_JOURNAL
        )

    @classmethod
    def archives_conservees(cls) -> int:
        """
        Retourne le nombre d'archives gardées derrière le fichier courant.

        Réglable par `GALSEN_LOG_BACKUP_COUNT`. Zéro est accepté — cela signifie
        « tronquer sans conserver d'historique », un choix légitime sur un
        support très contraint.
        """
        return _entier_positif(
            os.environ.get("GALSEN_LOG_BACKUP_COUNT"),
            cls.ARCHIVES_CONSERVEES,
            minimum=0,
        )

    def get_logger(self, name: str) -> logging.Logger:
        """
        Retourne un logger configuré pour le nom spécifié.

        Args:
            name: Nom du logger (généralement __name__ du module appelant).

        Returns:
            Instance de logging.Logger configurée.
        """
        return logging.getLogger(name)