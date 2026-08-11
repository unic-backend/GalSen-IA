"""
Validation des variables d'environnement au démarrage (VOLET 03, chapitre 05).

Le chapitre l'exige en une ligne — « validate environment variables at startup » —
et rien ne le faisait : une valeur mal écrite était découverte plus tard, par un
comportement inattendu, ou jamais. `GALSEN_STORAGE_BACKEND=sqllite` faisait
silencieusement repartir la plateforme en mémoire, donc sans persistance.

Ce module **rapporte, il ne bloque pas**. Une variable absente est légitime : la
plupart sont optionnelles et leur absence désactive proprement une capacité. Ce
qui est signalé, c'est une variable *présente* et *inexploitable* — le seul cas
où l'opérateur croit avoir configuré quelque chose qui ne s'applique pas.
"""

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# Valeurs acceptées pour les variables à choix fermé.
BACKENDS = ("in-memory", "sqlite")
BOOLEENS = ("true", "false", "1", "0", "yes", "no")
SECURITES_SMTP = ("none", "starttls", "ssl")


@dataclass
class ProblemeConfiguration:
    """Une variable présente dont la valeur ne peut pas être appliquée."""

    variable: str
    valeur: str
    raison: str
    consequence: str

    def to_dict(self) -> Dict[str, str]:
        """Sérialise le problème pour un journal ou une réponse d'API."""
        return {
            "variable": self.variable,
            # La valeur d'un secret n'est jamais reproduite : seule sa forme est en cause.
            "value": self.valeur if not _est_secret(self.variable) else "***",
            "reason": self.raison,
            "consequence": self.consequence,
        }


def _est_secret(variable: str) -> bool:
    """Indique si la variable porte un secret, à ne jamais recopier dans un journal."""
    return any(marqueur in variable for marqueur in ("KEY", "TOKEN", "PASSWORD", "SECRET"))


def _entier_positif(valeur: str) -> Optional[str]:
    """Vérifie un entier strictement positif ; retourne la raison de l'échec."""
    try:
        if int(valeur) <= 0:
            return "doit être un entier strictement positif"
    except ValueError:
        return "n'est pas un entier"
    return None


def _nombre_positif(valeur: str) -> Optional[str]:
    """Vérifie un nombre strictement positif ; retourne la raison de l'échec."""
    try:
        if float(valeur) <= 0:
            return "doit être un nombre strictement positif"
    except ValueError:
        return "n'est pas un nombre"
    return None


def _parmi(*acceptees: str) -> Callable[[str], Optional[str]]:
    """Construit un contrôle de valeur fermée, insensible à la casse."""

    def controle(valeur: str) -> Optional[str]:
        if valeur.strip().lower() not in acceptees:
            return f"valeur inconnue, attendu : {', '.join(acceptees)}"
        return None

    return controle


# Contrôles par variable : la fonction retourne la raison du refus, ou None.
# La seconde valeur dit ce qui se passe quand la valeur est inexploitable — c'est
# ce que l'opérateur a besoin de savoir, plus que la règle violée.
CONTROLES: Dict[str, Tuple[Callable[[str], Optional[str]], str]] = {
    "GALSEN_STORAGE_BACKEND": (
        _parmi(*BACKENDS),
        "le stockage repart en mémoire : rien n'est persisté d'un redémarrage à l'autre",
    ),
    "GALSEN_RATE_LIMIT_ENABLED": (
        _parmi(*BOOLEENS),
        "le limiteur de taux prend sa valeur par défaut",
    ),
    "GALSEN_RATE_LIMIT_AUTHENTICATED_RPM": (_entier_positif, "la limite par défaut s'applique"),
    "GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM": (_entier_positif, "la limite par défaut s'applique"),
    "GALSEN_RATE_LIMIT_BURST_MULTIPLIER": (_nombre_positif, "le multiplicateur par défaut s'applique"),
    "GALSEN_LOG_MAX_BYTES": (_entier_positif, "la taille de rotation par défaut s'applique"),
    "GALSEN_LOG_BACKUP_COUNT": (_entier_positif, "le nombre d'archives par défaut s'applique"),
    "GALSEN_KNOWLEDGE_REVALIDATION_DAYS": (
        _entier_positif,
        "le délai de revalidation par défaut (180 jours) s'applique",
    ),
    "GALSEN_SMTP_PORT": (_entier_positif, "l'envoi d'e-mail échouera à la connexion"),
    "GALSEN_SMTP_SECURITY": (
        _parmi(*SECURITES_SMTP),
        "le mode de sécurité SMTP par défaut s'applique",
    ),
    "GALSEN_THREAT_WINDOW_SECONDS": (
        _entier_positif,
        "la fenêtre de détection par défaut (300 s) s'applique",
    ),
    "GALSEN_THREAT_FAILURE_THRESHOLD": (
        _entier_positif,
        "le seuil de détection par défaut (10 échecs) s'applique",
    ),
    "GALSEN_NOTIFICATION_DEDUP_SECONDS": (
        _entier_positif,
        "la fenêtre de regroupement par défaut (300 s) s'applique",
    ),
    "GALSEN_NOTIFICATION_RETENTION_DAYS": (
        _entier_positif,
        "la durée de rétention par défaut (90 jours) s'applique",
    ),
    "GALSEN_OPENAI_COMPATIBLE_CONTEXT": (
        _entier_positif,
        "la taille de contexte annoncée est ignorée, le modèle peut être refusé par le sélecteur",
    ),
}


def validate_environment(environnement: Optional[Dict[str, str]] = None) -> List[ProblemeConfiguration]:
    """
    Contrôle les variables présentes dans l'environnement.

    Args:
        environnement: table à contrôler ; `os.environ` par défaut.

    Returns:
        La liste des problèmes, vide si tout est exploitable. Une variable absente
        ou vide n'est jamais un problème : la plupart sont optionnelles, et une
        absence désactive proprement la capacité correspondante.
    """
    table = os.environ if environnement is None else environnement
    problemes: List[ProblemeConfiguration] = []

    for variable, (controle, consequence) in CONTROLES.items():
        valeur = table.get(variable)
        if valeur is None or not str(valeur).strip():
            continue
        raison = controle(str(valeur))
        if raison:
            problemes.append(ProblemeConfiguration(
                variable=variable, valeur=str(valeur), raison=raison, consequence=consequence,
            ))
    return problemes


def log_environment_problems(logger) -> List[ProblemeConfiguration]:
    """
    Contrôle l'environnement et journalise chaque problème trouvé.

    Appelé au démarrage. Rien n'est interrompu : une plateforme qui refuse de
    démarrer pour une limite de taux mal écrite est moins utile qu'une plateforme
    qui démarre en le disant.
    """
    problemes = validate_environment()
    for probleme in problemes:
        detail = probleme.to_dict()
        logger.warning(
            "Configuration ignorée — %s=%s : %s. Conséquence : %s",
            detail["variable"], detail["value"], detail["reason"], detail["consequence"],
        )
    return problemes
