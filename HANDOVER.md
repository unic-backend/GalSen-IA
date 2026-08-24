# HANDOVER — GalSen IA

**Écrit le 2026-08-24, après une session où la plateforme a répondu pour la
première fois avec son propre modèle.**

Ce fichier existe pour qu'une IA qui reprend le projet sache où il en est **sans
poser de questions au propriétaire**. Il ne remplace pas `docs/memory/` — il le
corrige là où il est périmé, et il porte ce qui n'a été mesuré nulle part
ailleurs.

Lis-le en entier avant d'agir. Il fait 150 lignes.

---

## 1. Ce qu'est le projet, en cinq lignes

GalSen IA est une plateforme d'IA **souveraine** (elle tourne sur la machine de
l'utilisateur, aucun fournisseur hébergé n'est enregistré — ADR-014), pensée
d'abord pour le Sénégal. Sa promesse tient en une phrase : **elle dit « je ne
sais pas » plutôt que d'inventer.** Chaque réponse porte son état d'ancrage
(`GROUNDED` / `UNGROUNDED` / `NOT_CHECKED`) et la raison.

39 ADR, ~7 000 tests, 143 routes, licence Apache-2.0, étiquette `v0.1.0`.

---

## 2. LA CORRECTION LA PLUS IMPORTANTE

**`docs/memory/session-state.md` est périmé sur un point décisif.** Il affirme :

> *« Rendre le chat conversant demande une étape de rédaction : non autorisée,
> non faite. »*

**C'est faux depuis le 2026-08-23.** L'étape de rédaction **existe**, sur la
branche `claude/galsen-ia-phases-ukwz7p`, portée par deux commits :

```
02967d5  fix(chat): the anti-fabrication rule was suppressing answers the model could give alone
2a5bd08  fix(local-provider): a generation timeout that silently changed model
```

Elle **fonctionne**, vérifié le 2026-08-24 (§4). Elle n'est simplement **pas
fusionnée sur `main`**. Ne la reconstruis pas.

---

## 3. Démarrer la plateforme — la séquence qui marche

Machine du propriétaire : **Windows**, terminal **Invite de commandes** (cmd),
projet dans `C:\GalSen IA`.

**Piège vérifié** : la syntaxe PowerShell `$env:X="y"` **ne fait rien dans cmd**.
Une session entière a été perdue sur des `401 Unauthorized` pour cette raison.

Dans cmd, dans le dossier du projet :

```
set GALSEN_API_KEYS=admin-galsen:admin
```

```
python -m uvicorn src.api.server:app --reload
```

`uvicorn` seul n'est pas dans le `PATH` : **toujours `python -m uvicorn`**.

Ollama tourne déjà sur `http://127.0.0.1:11434` — aucune variable à déclarer,
`local_provider.py` a cette valeur par défaut.

---

## 4. La preuve que ça marche, mesurée

Depuis une **seconde** fenêtre (PowerShell ou cmd) :

```
Invoke-RestMethod -Uri "http://127.0.0.1:8000/chat" -Method Post -Headers @{"X-API-Key"="admin-galsen"} -ContentType "application/json" -Body '{"message":"Explique en trois phrases ce que veut dire BA13 dans le batiment"}'
```

Rendu réel, 2026-08-24 :

```
answer     : BA13 désigne une plaque de plâtre standard dont l'épaisseur est
             précisément de 13 millimètres...
generated  : True
model_used : qwen3.5:9b
grounding  : UNGROUNDED — 5 élément(s) trouvé(s), aucun vérifié : ce sont des
             sources externes, pas des connaissances validées de la plateforme
deliberation : retries=0, stop_reason=verified, corrected=False
elapsed_seconds : 209,87
```

**Attention au test avec « bonjour »** : un mot-clé l'attrape et rend une
salutation toute faite en 28 ms, `generated: False`, sans appeler le modèle.
Ce n'est pas une panne. Pour éprouver la génération, pose une vraie question.

---

## 5. Latence — mesurée, ne pas re-supposer

| Mesure | Valeur |
|---|---|
| Une génération Ollama seule (`/api/generate`) | **147,5 s** |
| Un tour `/chat` complet | **209,9 s** |
| Surcoût de la plateforme | **~62 s** |

**Le goulot est le modèle sur CPU**, pas l'architecture. 4 cœurs, aucun GPU,
~1-2 jetons/seconde.

Modèles installés :

```
qwen3.5:9b          6,6 Go   (~5,9 bits/poids → déjà quantifié, ~Q5)
qwen2.5-coder:14b   9,0 Go
```

**Ne recommande pas un modèle plus petit** : le propriétaire l'a refusé, et il a
raison — un 3B perd le raisonnement. **Ne recommande pas une requantification** :
Q5 → Q4_K_M gagnerait 15-20 %, pas la moitié.

Les deux vrais leviers : **le streaming** (perçu, pas total) et **un GPU**.

---

## 6. Les trois défauts trouvés le 2026-08-24

### D1 — `api.post is not a function` · l'interface est cassée

`src/web/static/js/chat.js:176` appelle `await api.post("/chat", {...})`.
`src/web/static/js/api-client.js` **n'expose aucune méthode `post`** : son objet
`api` (ligne 133) ne contient que des fonctions par domaine, toutes construites
sur `appeler(chemin, { methode, corps })` (ligne 75).

L'appel a été écrit avant l'entrée correspondante dans le client. **`/ui/` est
donc inutilisable** — la bulle part, rien ne revient.

Correctif : ajouter une entrée `chat` dans l'objet `api` appelant
`appeler("/chat", { methode: "POST", corps })`, et pointer `chat.js` dessus.

### D2 — `/chat` n'écrit aucun événement d'audit

Le `run_id` rendu par `/chat` n'est retrouvé **dans aucune des trois sources**
de `/observability/trail/{id}` : `routine_runs`, `audit_events`,
`workflow_runs` — tous `NONE`, `found_in: []`. Vérifié sur
`run_832c65e9b329`.

Conséquence : **impossible de savoir où passent les 209 secondes** par les
outils de la plateforme elle-même. Le trou est dans la traçabilité, pas dans la
mesure.

### D3 — Swagger `/docs` rend une page blanche

FastAPI charge Swagger depuis un CDN internet. Bloqué ici → page vide avec le
titre chargé. **Ne pas diagnostiquer une panne d'API à partir de ça.** Utiliser
`Invoke-RestMethod` comme au §4.

---

## 7. Ce qu'il faut faire ensuite, dans l'ordre

1. **Fusionner `claude/galsen-ia-phases-ukwz7p` sur `main`** — la rédaction n'y
   est toujours pas, et c'est là qu'elle doit vivre. C'est le geste qui a le
   plus de valeur et le moins de risque.
2. **Corriger D1** — une entrée dans `api-client.js`. Sans ça l'interface reste
   morte et le propriétaire croit que rien ne marche.
3. **Ajouter le streaming** (SSE) à `POST /chat`, et le consommer dans
   `chat.js`. Le total ne bouge pas ; les premiers mots arrivent en 3-5 s au
   lieu de 3 min d'écran vide. **C'est ce qui rend l'IA utilisable.**
4. **Corriger D2** — écrire les événements d'audit des tours de `/chat`.

Aucun de ces quatre points ne touche à l'architecture.

---

## 8. Règles du dépôt à ne pas enfreindre

Elles sont dans `CLAUDE.md` et `.claude/rules/`. Les quatre qui comptent :

- **Répondre au propriétaire en français.** Commentaires de code en français,
  documentation technique et messages de commit en anglais.
- **Une phase par tour**, sauf cadence convenue (actuellement **deux**). Ouvrir
  un VOLET produit un plan de phases **et rien d'autre**.
- **Ne jamais déclarer un travail fini sans l'avoir lancé.** Une suite lancée
  avec `| tail -4` cache ses échecs : un run a rapporté « 25 failed » dont 3
  seulement étaient visibles.
- **N'implémente que ce qui est demandé** (`spec-driven-governance.md`). Une
  amélioration possible n'est pas une exigence.

---

## 9. Comment parler à ce propriétaire

Appris à ses dépens dans la session du 2026-08-24 :

- **Une commande par bloc.** Jamais trois dans le même. Il copie d'un clic ;
  un bloc à éditer avant de l'exécuter est un bloc qui produit une erreur.
- **Nommer le terminal.** cmd et PowerShell n'ont pas la même syntaxe, et il
  travaille dans les deux.
- **Réponses courtes.** Il a dit deux fois qu'il se noyait dans « des tonnes de
  mots ». Le résultat d'abord, l'explication après, et seulement si elle change
  quelque chose.
- **Lancer le serveur avant d'écrire un document.** Une session entière est
  passée en audits pendant qu'il voulait juste parler à son IA. C'est ce qui l'a
  poussé à vouloir tout abandonner.

---

## 10. État à cette date

| | |
|---|---|
| `main` | `dc09303` (PR #36 fusionnée) |
| Étiquette `v0.1.0` | poussée, pointe sur `dc09303` |
| Branche portant la rédaction | `claude/galsen-ia-phases-ukwz7p` — **non fusionnée** |
| Autre branche | `feature/model-evaluation` — harnais d'évaluation + `rapport2.json` |
| Suite | `1 failed, 6967 passed` avant l'étiquette ; l'échec était l'étiquette |
| C1 (un modèle répond) | **tenu** depuis le 2026-08-24 |
| C4 (atteignable par le réseau) | **ouvert** — dernier critère de sortie |

Le reste — corpus sénégalais, GPU, déploiement — dépend de documents, de
matériel et d'un hébergeur, pas de code.
