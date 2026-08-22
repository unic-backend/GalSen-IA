# Démarrer GalSen IA

Écrit le 2026-08-22, après avoir mesuré ce qui marche et ce qui ne marche pas.

---

## En une ligne

```
Demarrer_GalSen.bat
```

Double-clic. Le script vérifie chaque prérequis, dit ce qui manque, et refuse de
démarrer à moitié.

---

## Ce que tu verras

| Adresse | Quoi |
|---|---|
| `http://localhost:8000/ui` | **L'interface** — santé, connecteurs, clés |
| `http://localhost:8000/ui/studio.html` | Le Media Studio |
| `http://localhost:8000/docs` | Les 142 routes, essayables depuis le navigateur |
| `http://localhost:8000/health` | L'état réel de chaque sous-système |

---

## La seule chose qui bloque l'IA aujourd'hui

**Mesuré le 2026-08-22** (`python scripts/demonstration.py`) :

```
subsystems               OK      9 disponibles, 0 dégradés
knowledge_routing        OK
world_knowledge          OK
routine_fires_workflow   OK      3 agents exécutés, 1,1 s
trail                    OK
generation               NOT_CONFIGURED   ← ici
acquisition              NOT_CONFIGURED
```

**`generation` est la seule raison pour laquelle ton IA ne répond pas.** Ce n'est
pas une panne : aucun fournisseur de modèle n'a jamais été branché. L'API répond
`503` **avec le motif**, elle n'invente pas de réponse.

Le script `Demarrer_GalSen.bat` s'en occupe : il installe le modèle si Ollama est
là, et te le dit clairement s'il ne l'est pas.

**Une seule contrainte à connaître : le contexte du modèle doit être ≥ 8192.**
En dessous, le sélecteur refuse — et il dit lequel manquait.

---

## Si tu préfères à la main

```bash
pip install -r requirements.txt
ollama serve                       # dans un terminal
ollama pull qwen2.5-coder:14b      # ~9 Go, une seule fois
python -m uvicorn src.api.server:app --port 8000
```

---

## Vérifier que ça répond vraiment

Ne me crois pas — la preuve existe déjà dans le dépôt :

```bash
python -m pytest tests/test_generation_end_to_end.py -v
```

Ce test **s'ignore** tant qu'aucun fournisseur ne répond, et **s'exécute** dès
qu'un répond. S'il passe, ton IA génère. S'il s'ignore, elle ne génère pas
encore. C'est le seul juge.

---

## Ce que la plateforme fait déjà, sans modèle

Ces cinq-là ont tourné à la mesure ci-dessus :

- **9 sous-systèmes** répondent
- **Les agents s'exécutent** — 3 agents, un tour complet, 1,1 s
- **Le routage de connaissance** — droit et administration ne retombent jamais
  sur la connaissance globale
- **La trace d'audit** — un travail se suit de bout en bout
- **142 routes** servies, avec authentification et permissions

---

## `acquisition` : `NOT_CONFIGURED` aussi, et c'est voulu

23 sources sont inscrites, **aucune activée** (ADR-021). En plus, le mandataire
réseau de l'environnement de développement refuse les domaines institutionnels
sénégalais (`CONNECT → 403`, mesuré).

Rien ne peut être acquis, **et rien ne sera inventé**. C'est la règle qui
fonctionne, pas une panne. Depuis ta machine le proxy ne s'applique pas — activer
une source reste une décision à prendre, pas un défaut à corriger.

---

## Deux choses que personne n'a encore faites

- **Déployer sur un serveur** (critère C4). Le `Dockerfile` et le `compose`
  existent ; **personne n'a jamais atteint cette API par le réseau.**
- **Pousser l'étiquette `v0.1.0`** — `git push origin v0.1.0` depuis un clone
  normal. C'est l'unique test rouge en CI, et publier une release est ta décision,
  pas une réparation.

---

## Si le moteur de codage refuse tout

Normal depuis PR #34 : sans `GALSEN_CODING_WORKSPACE_ROOTS`, il refuse **tout**.
Avant, il acceptait n'importe quel dossier de la machine.

```
set GALSEN_CODING_WORKSPACE_ROOTS=C:\Users\toi\projets
```
