# État du projet GalSen IA — rapport au propriétaire

**Mesuré le 2026-08-14**, branche `claude/galsen-ia-phases-ukwz7p`.
Chaque chiffre de ce rapport vient d'une commande exécutée, pas d'une estimation.
Ce qui n'a pas été mesuré est écrit comme non mesuré.

Ce fichier remplace toute version antérieure : il n'y a qu'un état du projet à la fois.
Le détail des blocages de mise en ligne reste dans `docs/deployment/reste-a-faire.md`.

---

## 1. Où nous en sommes, en une page

La plateforme est **construite et testée**. Elle n'est pas **en service**, et
l'écart entre les deux tient à des choses qui ne dépendent pas du code.

*Mis à jour le 2026-08-14 : une couche de connaissance sénégalaise existe désormais —
14 régions, 45 départements, 212 objets sectoriels, 271 fragments tous avec provenance, et
un corpus wolof de 2105 phrases. Ce qui manque n'est plus « du contenu » en général, mais
les documents **institutionnels**, et le blocage est réseau.*

| Mesure | Valeur | Commande |
|---|---|---|
| Tests | **3238 passent, 8 ignorés** | `python -m pytest -q` |
| Style | **propre** | `ruff check src tests` |
| Fichiers Python dans `src/` | 319 | — |
| Agents au registre | 17 | `agents/` |
| Outils au catalogue | 22 dont 21 activés | catalogue d'outils |
| Routes d'API | 76 | `src/api/` |
| Décisions d'architecture (ADR) | 22, dont **ADR-020 encore `proposed`** ; ADR-021 accepté | `docs/architecture/decisions/` |
| CI GitHub | **1 seul échec**, l'étiquette `v0.1.0` non poussée | run 31704148980 |
| Entités administratives sénégalaises | **14 régions, 45 départements** | `scripts/ingest_all_senegal.py` |
| Objets de connaissance sectoriels | **212** (8 jeux acquis) | `scripts/ingest_senegal_domains.py` |
| Fragments récupérables / avec provenance | **271 / 271** | `knowledge_report()` |
| Domaines peuplés | **6 sur 16** | idem |
| Corpus wolof | **2105 phrases** | `scripts/ingest_wolof.py` |
| Documents **institutionnels** sénégalais | **0** — les 9 domaines `.sn` sont refusés par le mandataire | `scripts/activate_senegal_sources.py` |
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

### 3.3 Les sources institutionnelles sénégalaises sont injoignables **depuis cet environnement**

*Mis à jour le 2026-08-14.* Le chemin d'acquisition existe et est testé de bout en bout
(ADR-021). Il ne peut atteindre aucune institution sénégalaise : les neuf domaines `.sn`
inscrits au registre répondent `CONNECT → 403` **avant qu'aucune requête n'atteigne les
sites**. C'est le mandataire de l'environnement, pas un refus des sites — et les deux
demandent des actions opposées.

Mesurable en une commande :

```bash
python scripts/activate_senegal_sources.py
curl -sS "$HTTPS_PROXY/__agentproxy/status"   # section recentRelayFailures
```

Conséquence : histoire, culture, agriculture, pêche, élevage, mines, tourisme, éducation,
santé et juridique **ne contiennent rien**, et le disent. Les remplir de mémoire
fabriquerait des faits sur un pays réel — servir une affirmation inventée à un agriculteur
serait le pire usage possible de ce dépôt.

Ce qui a pu être acquis l'a été depuis des redistributions publiques joignables (Banque
mondiale, ISO, UN/LOCODE, OurAirports), **au rang de ce qui a été récupéré** et jamais à
celui de l'institution en amont.

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

### Action 3 — Lancer le pilote d'acquisition depuis une machine sans ce mandataire

*Mis à jour le 2026-08-14.* Le travail n'est plus de fournir des documents à la main : le
chemin d'acquisition est construit et testé. Il lui faut un réseau qui laisse passer.

Sur ton PC :

```bash
python scripts/activate_senegal_sources.py     # doit dire « reachable », pas « blocked »
# puis, pour la ou les sources dont tu as lu les conditions d'utilisation,
# dans corpus/sources/senegal.yaml :
#   enabled: true
#   allowed_content_types: [pdf, html]
#   access_policy: { terms_reviewed: "2026-08-14" }
python scripts/acquisition_pilot.py plan
# approuver la demande, puis
python scripts/acquisition_pilot.py run --approval <id>
```

**Lire les conditions d'utilisation reste à toi** : `robots.txt` dit ce qu'un agent peut
atteindre, pas ce qu'on a le droit d'en faire. Aucun programme ne peut le faire
honnêtement à ta place.

Règle inchangée : **un document sans source déclarée n'entre pas.**

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
