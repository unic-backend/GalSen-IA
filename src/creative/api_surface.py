"""
Ce que la couche créative expose, et ce qu'elle refuse d'exposer (C17, §70).

## Le piège de §70

§70 propose quinze préfixes : `/creative`, `/references`, `/entities`,
`/worlds`, `/scenes`, `/shots`, `/audio`, `/voice`, `/video`, `/jobs`,
`/providers`, `/languages`, `/memory`, `/verification`, `/provenance`.

Les monter tous serait la faute que §72 nomme : *« cent abstractions incomplètes
plutôt qu'un flux qui marche »*. Quinze préfixes dont douze répondraient un objet
vide donneraient une API qui a l'air complète et ne l'est pas — et c'est bien
pire qu'une API petite, parce qu'un appelant construit dessus.

§70 dit d'ailleurs lui-même quoi faire avant d'ajouter quoi que ce soit :
*« check whether an equivalent existing API already exists »*. Cette plateforme
en porte déjà 140.

## La règle appliquée ici

**Une route n'existe que si une fonction réelle la sert.** Chacune de celles
déclarées ci-dessous appelle du code des volets C04 à C16 et rend ce qu'il a
mesuré — y compris quand ce qu'il a mesuré est « bloqué ».

Les noms de §70 qui sont **déjà servis ailleurs** sont listés dans
`surface_map()` avec la route existante, et **ne sont pas remontés** : deux
chemins pour un même geste dérivent, et ce dépôt l'a déjà payé quatre fois.

Ceux qui ne sont servis nulle part sont listés aussi, avec ce qui manque pour
qu'ils le soient. Une API dont on peut lire ce qu'elle ne fait pas encore vaut
mieux qu'une API dont il faut le deviner.
"""

from __future__ import annotations

from typing import Any, Dict, List

#: Les préfixes que §70 propose, dans l'ordre du texte.
PREFIXES_DIRECTIVE = (
    "/creative", "/references", "/entities", "/worlds", "/scenes", "/shots",
    "/audio", "/voice", "/video", "/jobs", "/providers", "/languages",
    "/memory", "/verification", "/provenance",
)

#: Ce qu'un nom de §70 devient ici.
SERVI = "SERVED"
DEJA_SERVI_AILLEURS = "SERVED_ELSEWHERE"
PAS_ENCORE = "NOT_SERVED"


def surface_map() -> List[Dict[str, Any]]:
    """
    Le sort de chaque préfixe de §70, avec sa raison.

    Returns:
        Une entrée par préfixe proposé. `SERVED_ELSEWHERE` nomme la route qui
        le sert déjà — la remonter sous un second chemin ferait diverger les
        deux au premier changement. `NOT_SERVED` nomme ce qui manque, plutôt
        que de monter une route qui répondrait un objet vide.
    """
    return [
        {"prefix": "/creative", "state": SERVI,
         "route": "/creative/readiness",
         "note": "L'état calculé de la couche, comme `/media` le fait déjà."},
        {"prefix": "/providers", "state": SERVI,
         "route": "/creative/providers",
         "note": "Sous `/creative` : un `/providers` racine laisserait croire "
                 "qu'il couvre aussi les fournisseurs de modèles de "
                 "`src/model_engine`, qui sont autre chose."},
        {"prefix": "/languages", "state": SERVI,
         "route": "/creative/languages",
         "note": "Registre, matrice des cinq capacités et couverture des "
                 "langues de validation de §64."},
        {"prefix": "/video", "state": SERVI,
         "route": "/creative/pipelines",
         "note": "Les deux architectures de §43 et l'étape où chacune bute. "
                 "Aucune route ne *génère* : rien ne peut générer ici."},
        {"prefix": "/audio", "state": DEJA_SERVI_AILLEURS,
         "route": "/media/*",
         "note": "Le moteur média porte déjà l'audio, les sous-titres et le "
                 "montage. Un second chemin divergerait."},
        {"prefix": "/jobs", "state": DEJA_SERVI_AILLEURS,
         "route": "/media/queue (RenderQueue)",
         "note": "§53 demande de réutiliser la file existante ; C16 s'y "
                 "raccorde, l'API aussi."},
        {"prefix": "/memory", "state": DEJA_SERVI_AILLEURS,
         "route": "/memory/*",
         "note": "Le moteur de mémoire est monté depuis longtemps."},
        {"prefix": "/references", "state": PAS_ENCORE,
         "missing": "Un magasin persistant et un transfert de médias. "
                    "`ReferenceMemory` est en mémoire (C06) ; l'exposer "
                    "laisserait téléverser le visage d'une personne dans un "
                    "magasin qui disparaît au redémarrage.",
         "note": "Le consentement et la révocation existent en code ; c'est "
                 "la persistance qui manque, pas la règle."},
        {"prefix": "/verification", "state": PAS_ENCORE,
         "missing": "Une mesure d'identité. ADR-026 déclare les dimensions ; "
                    "aucune n'est mesurable sur cette machine.",
         "note": "Une route rendrait un score qu'aucune mesure ne soutient."},
        {"prefix": "/provenance", "state": PAS_ENCORE,
         "missing": "Des artefacts. La provenance est écrite (C16) et n'a "
                    "encore rien à décrire, faute de génération.",
         "note": ""},
        {"prefix": "/entities", "state": PAS_ENCORE,
         "missing": "La persistance, comme pour `/references`.", "note": ""},
        {"prefix": "/worlds", "state": PAS_ENCORE,
         "missing": "La persistance, comme pour `/references`.", "note": ""},
        {"prefix": "/scenes", "state": PAS_ENCORE,
         "missing": "La persistance, comme pour `/references`.", "note": ""},
        {"prefix": "/shots", "state": PAS_ENCORE,
         "missing": "Un plan a besoin d'une scène persistée pour être "
                    "adressable.", "note": ""},
        {"prefix": "/voice", "state": PAS_ENCORE,
         "missing": "Transcription et séparation de locuteurs, toutes deux "
                    "indisponibles ici (sondes mesurées).",
         "note": "L'audio d'origine est conservé sans route : c'est un "
                 "invariant de la chaîne, pas un service."},
    ]


def readiness() -> Dict[str, Any]:
    """
    L'état de la couche créative, **calculé** en interrogeant ses modules.

    Returns:
        L'aptitude, comme `src/media/readiness.py` la calcule pour le média :
        jamais écrite à la main, toujours dérivée de ce que les sondes et les
        registres répondent au moment de l'appel.

    Note:
        Les imports sont locaux et non au module : `api_surface` est importé
        par le serveur au démarrage, et faire remonter les sondes à l'import
        ferait payer une mesure de GPU à chaque démarrage, y compris quand
        personne n'appelle la route.
    """
    from .language.registry import coverage_report
    from .pipelines import compare_pipelines
    from .providers import ProviderRegistry, adapt_declared
    from .research import load_research
    from .resources import measure

    dossier = load_research()
    fournisseurs = adapt_declared(dossier.get("candidates") or [])
    registre = ProviderRegistry()
    for fournisseur in fournisseurs:
        registre.register(fournisseur)

    architectures = compare_pipelines(registre)
    ressources = measure(".")
    couverture = coverage_report()

    realisables = architectures["feasible"]
    if realisables:
        etat = "CREATIVE LAYER READY"
    elif ressources.gpu_available:
        etat = ("ORCHESTRATION READY — NO PROVIDER CLEARED, "
                "GPU PRESENT")
    else:
        etat = ("ORCHESTRATION READY — GENERATION BLOCKED "
                "(NO GPU, NO PROVIDER CLEARED)")

    return {
        "state": etat,
        "providers_declared": len(fournisseurs),
        "pipelines": {
            nom: {"state": plan["state"], "first_block": plan["first_block"]}
            for nom, plan in architectures["plans"].items()
        },
        "feasible_pipelines": realisables,
        "recommended_pipeline": architectures["recommended"],
        "resources": ressources.as_dict(),
        "languages": {
            "validation_languages": couverture["count"],
            "fully_carried": couverture["fully_carried"],
        },
        "note": (
            "L'état est calculé à l'appel, jamais écrit : il suit ce que les "
            "sondes et le registre répondent maintenant. Une couche "
            "d'orchestration prête n'est pas une plateforme qui génère — "
            "aucun fournisseur n'est dégagé, et cette machine n'a pas de GPU."
        ),
    }
