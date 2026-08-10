"""
Configuration de la plateforme GalSen IA.

Regroupe ce qui décide du comportement au démarrage à partir de l'environnement,
sans que les moteurs aient à connaître la provenance de leurs réglages.
"""

from .environment import (
    ProblemeConfiguration,
    log_environment_problems,
    validate_environment,
)

__all__ = [
    "ProblemeConfiguration",
    "log_environment_problems",
    "validate_environment",
]
