"""
Ce que GalSen IA expose par MCP, et ce qu'elle n'expose pas (VOLET 34, ch. 09).

ADR-017 §6 décide l'ordre : **serveur avant client**. Être appelé garde le risque
de notre côté — nous authentifions, nous autorisons, nous journalisons — là où
être client reviendrait à charger les descriptions d'outils d'autrui dans notre
propre invite, ce qui est la vulnérabilité MCP la plus documentée.

Mais « le risque est de notre côté » ne veut pas dire « exposons tout ».

## La décision de ce fichier

Le catalogue compte vingt et un outils, dont le terminal, l'écran, le contrôle
GUI, l'accès aux fichiers et la base de données. Les exposer tous par MCP
donnerait à un agent extérieur **les mains de la plateforme** : un client MCP
mal intentionné — ou simplement manipulé par une page web — pourrait cliquer,
écrire et lancer des commandes.

L'exposition est donc une **liste blanche**, et elle est courte. Un outil y entre
parce que quelqu'un a décidé qu'il pouvait être appelé de l'extérieur, jamais
parce qu'il existe.

## Ce qui n'entre pas, et pourquoi

| Outil | Raison du refus |
|---|---|
| `terminal` | Exécute des commandes sur la machine hôte |
| `gui`, `screen` | Voir et manipuler l'écran de quelqu'un depuis l'extérieur |
| `filesystem` | Lecture et écriture de fichiers, même confinées |
| `database` | Accès direct au stockage |
| `docker` | Déjà désactivé pour raison de sécurité |
| `email`, `calendar` | Agit au nom de la personne, hors de son regard |
| `api` | Un appelant extérieur relaierait ses propres requêtes par la plateforme |

Ce qui reste est ce qu'un agent extérieur peut utilement demander sans agir sur
la machine : chercher dans la connaissance, chercher sur le web, lire un PDF,
calculer des embeddings.
"""

from typing import Dict, List

#: Outils exposables par MCP. Toute autre entrée du catalogue est refusée.
#: Ajouter un nom ici est une décision de sécurité, pas une commodité.
OUTILS_EXPOSES = (
    "rag",          # chercher dans la base de connaissances
    "memory",       # lire et écrire des mémoires, sous l'identité de l'appelant
    "embeddings",   # calculer des vecteurs
    "web_search",   # chercher sur le web
    "pdf",          # lire un document fourni
    "ocr",          # lire une image fournie
    "metrics",      # état de la plateforme
    "logging",      # état de la plateforme
)

#: Outils explicitement refusés, avec la raison rendue au client. Un refus qui
#: dit pourquoi vaut mieux qu'un outil absent de la liste sans explication.
REFUS = {
    "terminal": "exécute des commandes sur la machine hôte",
    "gui": "manipule l'interface graphique de la personne",
    "screen": "lit l'écran de la personne",
    "filesystem": "lit et écrit des fichiers",
    "database": "accès direct au stockage",
    "docker": "désactivé pour raison de sécurité",
    "email": "agit au nom de la personne, hors de son regard",
    "calendar": "agit au nom de la personne, hors de son regard",
    "api": "relaierait les requêtes d'un tiers par la plateforme",
    "git": "modifie un dépôt",
    "github": "agit sur un dépôt distant",
    "model": "consommerait le budget de génération de la plateforme",
    "agri_advice": "porte des conseils qui demandent une source vérifiée",
    "browser": "récupérerait des pages au nom de la plateforme",
}


def expose(tool_id: str) -> bool:
    """Indique si un outil peut être appelé depuis l'extérieur."""
    return tool_id in OUTILS_EXPOSES


def refusal_reason(tool_id: str) -> str:
    """
    Retourne pourquoi un outil n'est pas exposé.

    Un outil inconnu et un outil délibérément retenu sont deux réponses
    différentes, et les confondre enverrait chercher au mauvais endroit.
    """
    if tool_id in REFUS:
        return f"Outil « {tool_id} » non exposé par MCP : {REFUS[tool_id]}."
    return (
        f"Outil « {tool_id} » non exposé par MCP : il ne figure pas dans la "
        "liste blanche d'exposition. L'y ajouter est une décision de sécurité."
    )


def report(catalogue: List[str]) -> Dict[str, object]:
    """
    Décrit ce que l'exposition laisse passer, sur un catalogue donné.

    Args:
        catalogue: Identifiants des outils déclarés dans la plateforme.
    """
    exposes = [tool_id for tool_id in catalogue if expose(tool_id)]
    retenus = [tool_id for tool_id in catalogue if not expose(tool_id)]
    return {
        "exposed": sorted(exposes),
        "withheld": sorted(retenus),
        "exposed_count": len(exposes),
        "catalogue_count": len(catalogue),
    }
