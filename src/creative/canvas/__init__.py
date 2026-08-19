"""
Le canvas créatif : un graphe côté serveur, sans opinion sur son rendu (ADR-031).

Quatre modules, et c'est tout ce que les audits ont laissé à construire :

| Module | Ce qu'il porte |
|---|---|
| `ports.py` | le vocabulaire de types transporté par une arête |
| `graph.py` | les nœuds, les arêtes, la légalité, l'ordre |
| `privacy.py` | `ProviderPrivacyPolicy` — le seul type réellement absent |
| `readiness.py` | l'état de chaque nœud, calculé, jamais écrit |

Un nœud **appelle** `reference/`, `world.py`, `direction.py`, `cinema.py`,
`verification.py`, `routing.py`, `jobs.py`, `style.py` et `intent.py`. Il n'en
réécrit aucun : K00 a compté trois registres et deux systèmes de provenance
déjà en place, et §3 interdit d'en ajouter.
"""
