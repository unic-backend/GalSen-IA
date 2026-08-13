# État du projet GalSen IA — rapport au propriétaire

**Mesuré le 2026-08-13**, commit `a89993b`, branche `claude/galsen-ia-phases-ukwz7p`.
Chaque chiffre de ce rapport vient d'une commande exécutée, pas d'une estimation.
Ce qui n'a pas été mesuré est écrit comme non mesuré.

Ce fichier remplace toute version antérieure : il n'y a qu'un état du projet à la fois.
Le détail des blocages de mise en ligne reste dans `docs/deployment/reste-a-faire.md`.

---

## 1. Où nous en sommes, en une page

La plateforme est **construite et testée**. Elle n'est pas **en service**, et
l'écart entre les deux tient à trois choses qui ne dépendent pas du code.

| Mesure | Valeur | Commande |
|---|---|---|
| Tests | **2925 passent, 8 ignorés** | `python -m pytest -q` |
| Style | **propre** | `ruff check src tests` |
| Fichiers Python dans `src/` | 319 | — |
| Agents au registre | 17 | `agents/` |
| Outils au catalogue | 22 dont 21 activés | catalogue d'outils |
| Routes d'API | 76 | `src/api/` |
| Décisions d'architecture (ADR) | 21, dont **ADR-020 encore `proposed`** | `docs/architecture/decisions/` |
| CI GitHub | **1 seul échec**, l'étiquette `v0.1.0` non poussée | run 31704148980 |
| Documents sénégalais dans la base | **0** | manifeste de connaissance |
| Modèle qui répond | **aucun** — `/generate` rend 503 | `scripts/proactive_scan.py` |

Autrement dit : tout ce qui pouvait être bâti et vérifié sans toi l'a été.
Ce qui reste demande **une machine, des documents et trois décisions** — c'est-à-dire toi.

---

## 2. Ce qui est terminé

**Les fondations** (VOLETs 01 à 34) : moteurs, mémoire, audit, approbation,
persistance SQLite (ADR-005), routage de modèles par coût, récupération sémantique,
ingestion documentaire, bac à sable, MCP, agent d'ordinateur personnel, infrastructure
d'entraînement.

**VOLET 36 — architecture de connaissance, 8 chapitres sur 8.** Les points qui comptent :

- **La barrière de confiance couvre les 9 chemins d'entrée externe** (RAG, MCP, recherche
  web, navigateur, API tierce, ticket GitHub, PDF, OCR, fichier disque). Il y en avait
  **un seul** avant. Un texte venu de l'extérieur arrive annoncé comme **donnée avec son
  origine**, jamais comme instruction.
- **Trois langues nationales** — wolof, pulaar, sérère — déclarables, filtrables,
  retrouvables. La normalisation ne leur applique plus la règle du pluriel française.
- **Entités et relations avec provenance obligatoire** : rien n'entre sans source, et
  c'est un refus, pas un avertissement.
- **Deux agents définis par leur refus** : `verifier` (sans passage → `cannot_verify`,
  jamais `supported`) et `senegal` (sujet national sans source nationale → refus).
- **Les capacités différées sont mesurées** à chaque scan au lieu de dormir dans un
  document : base vectorielle, base graphe, stockage objet, files, acquisition automatique.

**VOLET 35 — profondeur sénégalaise, 10 chapitres sur 12.**

- **La fiabilité vient du registre** (`corpus/sources/senegal.yaml`), plus du document qui
  la revendique. Une catégorie d'autorité (`official`, `government`, `peer_reviewed`)
  n'est acceptée que pour un domaine inscrit. Les réseaux sociaux et plateformes vidéo
  sont **refusés avec leur raison**, jamais rétrogradés en silence.
- **La récupération lit la portée** : droit, administration et langues **ne retombent
  jamais** sur la connaissance mondiale. Sujet national sans source locale → pas de
  réponse, et la raison est dite.
- **Les contradictions sont rapportées, jamais résolues.** Aucun gagnant désigné : le plus
  récent n'est pas automatiquement le bon.
- **La collecte est décidée, jamais exécutée** : registre, `robots.txt` appliqué, licence
  (inconnue → consultation seule), approbation humaine. Rien n'est téléchargé.
- **La santé a sa propre politique** : plancher de sources plus haut, avertissement sur
  chaque réponse, et **le refus de la posologie, du diagnostic et de la prescription est
  du code**, appliqué après la génération — pas une consigne d'invite.

---

## 3. Ce qui est bloqué, et sur qui

Quatre points. **Aucun n'est un problème de code**, et aucun ne peut être levé ici.

### 3.1 Aucun modèle ne répond (critère C1) — bloquant principal

`/generate` rend 503. Sans modèle local, la plateforme sert ses outils, sa mémoire, son
audit et son API — mais pas ce qu'un utilisateur appelle « l'IA ». Cela bloque aussi la
mesure de la récupération sémantique, en wolof comme ailleurs.

### 3.2 L'étiquette `v0.1.0` n'est jamais partie

Elle existe en local, pas sur le dépôt. C'est **le seul test rouge de la CI**. Le
mandataire de cet environnement refuse les étiquettes (403, réessayé le 2026-08-13) et
aucun outil d'API disponible ici n'en crée. Le test n'est ni ignoré ni affaibli : il dit
la vérité, et l'affaiblir effacerait la seule trace du travail restant.

### 3.3 La base contient **0 document sénégalais**

Les chapitres 11 et 12 du VOLET 35 — le premier vrai corpus sénégalais, puis le corpus
mondial — demandent de **vrais documents déclarés dans un manifeste**. Les écrire ici
reviendrait à fabriquer de la connaissance. Servir une affirmation inventée à un
agriculteur serait le pire usage possible de ce dépôt : c'est refusé par construction.

### 3.4 Trois décisions attendent ton arbitrage

| Décision | Où | Ce qui est proposé |
|---|---|---|
| **ADR-020** — rétention des données d'analyse | `docs/architecture/decisions/020-analytics-retention.md` | Trois options A/B/C ; l'option **B** est recommandée, après C4 |
| **Fin de vie de `/cloud/*`** | API | Une date à fixer ; sans date, la surface reste indéfiniment |
| **Cible de déploiement (C4)** | `docs/deployment/` | Où la plateforme tourne réellement |

Tant que ces trois-là ne sont pas tranchées, le code reste correct mais la plateforme
n'a pas de destination.

---

## 4. Ce que tu dois faire, dans l'ordre

Cinq actions. Les trois premières sont mécaniques, les deux dernières demandent une
décision. **Rien d'autre ne bloque.**

### Action 1 — Démarrer le modèle local (30 minutes)

```bash
ollama serve
ollama pull qwen2.5-coder:14b     # ou tout modèle à contexte >= 8192
python scripts/proactive_scan.py  # doit ne plus dire « aucun modèle ne peut répondre »
```

C'est l'action au plus fort effet : elle débloque la génération, la récupération
sémantique et la mesure du wolof d'un seul coup.

### Action 2 — Pousser l'étiquette (2 minutes)

Depuis un clone normal, **pas depuis cet environnement** :

```bash
git clone https://github.com/unic-backend/GalSen-IA
cd GalSen-IA
git push origin v0.1.0
```

La CI passe au vert au run suivant.

### Action 3 — Fournir les premiers vrais documents sénégalais

Rassemble des documents que tu peux **citer** : Journal officiel, textes de l'ANSD, de
l'ISRA, de l'ANACIM, des impôts et domaines. Déclare-les dans le manifeste décrit par
`docs/knowledge/README.md` — un document, une source, une portée, un sujet.

Règle du projet, à ne pas contourner : **un document sans source déclarée n'entre pas.**
Si sa source n'est pas au registre (`corpus/sources/senegal.yaml`), inscris-la d'abord.

C'est ce qui débloque les chapitres 11 et 12, et c'est ce qui transforme la plateforme
d'un moteur vide en une IA qui connaît le Sénégal.

### Action 4 — Trancher ADR-020

Lis `docs/architecture/decisions/020-analytics-retention.md`, choisis A, B ou C, et dis-le.
L'option B est recommandée. Le fichier passe alors de `proposed` à `accepted`.

### Action 5 — Fixer la cible de déploiement et la date de fin de `/cloud/*`

Où la plateforme tourne (machine, VPS, hébergeur) et à quelle date l'ancienne surface
`/cloud/*` est retirée. Deux phrases suffisent ; sans elles, la mise en ligne n'a pas
d'adresse.

---

## 5. Ce que je ne peux pas faire à ta place, et pourquoi

C'est délibéré, pas une limite technique :

- **Écrire le corpus sénégalais.** Une connaissance inventée qui a l'air vraie est pire
  qu'une base vide, parce qu'elle sera crue.
- **Marquer une capacité comme fonctionnelle sans l'avoir exécutée.** Un test qui épingle
  une valeur fabriquée rend la fabrication permanente.
- **Rendre le test de l'étiquette vert.** Il serait vert et faux.
- **Décider à ta place** ce qui engage la direction du projet.

---

## 6. Verdict

Le code est prêt. La plateforme ne l'est pas — il lui manque **un modèle qui tourne, des
documents réels et trois décisions**. Ces trois manques sont nommés, mesurés, et chacun a
une action précise en face.

Ce qui est fait est vérifié : 2925 tests exécutés dans cette session, aucun affaibli,
aucun supprimé. Ce qui ne marche pas est écrit comme ne marchant pas.
