"""
Logger utility for the Router Engine.

Configures and provides logging instances based on application configuration.
"""

import logging
import os
from typing import Optional
from .config_loader import ConfigLoader


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
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)

    def get_logger(self, name: str) -> logging.Logger:
        """
        Retourne un logger configuré pour le nom spécifié.

        Args:
            name: Nom du logger (généralement __name__ du module appelant).

        Returns:
            Instance de logging.Logger configurée.
        """
        return logging.getLogger(name)