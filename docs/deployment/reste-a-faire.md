# Ce qui manque pour mettre GalSen IA en ligne

Rapport au propriétaire — **2026-08-12**. Tout ce qui suit est **mesuré** : chaque
ligne nomme la commande ou la source qui l'a produite. Rien n'est estimé.

État général : le code est bâti et testé (**2 666 tests passent en local**), mais
**trois choses empêchent une mise en ligne publique**, et une quatrième vient
d'être découverte en préparant ce rapport.

---

## 1. Bloquants — rien ne doit être annoncé publiquement avant

### 1.1 La CI est rouge, et elle l'est depuis le début

```
Exécutions du workflow « Tests » : 0 succès sur 30
Dernière (commit b53a412) : 4 échecs, 2 664 passent
```

En local la même suite rend `2 666 passent, 7 ignorés`. L'écart vient de
l'environnement, et il porte **quatre** tests :

| Test en échec | Cause réelle | À qui c'est |
|---|---|---|
| `test_release_check.py::test_l_etiquette_de_la_version_courante_existe_bien` | L'étiquette `v0.1.0` **n'est pas sur le dépôt distant** — elle n'existe qu'en local | Vrai manque, voir §1.2 |
| `test_sandbox.py::test_ce_que_le_processus_a_lance_meurt_avec_lui` | Le runner GitHub refuse les `fork` (`Resource temporarily unavailable`) : le processus meurt avant d'être borné | **Mon défaut** — mes tests du bac à sable supposent une machine qui peut forker |
| `test_sandbox.py::test_aucun_descendant_ne_survit_a_une_execution_terminee_par_le_noyau` | Même cause | **Mon défaut** |
| `test_pdf_tool.py::test_pdf_tool_missing_dependencies` | Passe en local, échoue en CI : l'import simulé de `PyPDF2` se comporte différemment selon que le paquet a déjà été chargé | Antérieur à cette session |

**Conséquence pratique :** tant que la CI est rouge, aucune publication
automatique ne partira, et personne ne peut distinguer « ça casse » de « ça casse
comme d'habitude ». C'est le premier chantier, et il est court.

### 1.2 L'étiquette `v0.1.0` n'est jamais partie

```
git tag           → v0.1.0   (local)
sur le dépôt      → absente
```

Le mandataire de cet environnement refuse les étiquettes (403). À faire depuis un
clone normal :

```bash
git push origin v0.1.0
```

Cela referme aussi un des quatre échecs de CI.

### 1.3 La capacité principale ne répond pas (critère C1)

```
python scripts/proactive_scan.py
[blocking] Aucun modèle ne peut répondre : les capacités de génération sont hors service.
```

`/generate` rend **503**. Sans modèle, la plateforme sert ses outils, sa mémoire,
son audit et son API — mais pas ce qu'un utilisateur appelle « l'IA ».

```bash
ollama serve
ollama pull qwen2.5-coder:14b     # ou tout modèle à contexte ≥ 8192
```

### 1.4 La base de connaissances est vide

```python
KnowledgeManagerImpl().search_knowledge("", limit=10000)   → 0 élément
```

Le RAG ne peut rien citer. **Ne rien annoncer sur l'agriculture avant d'avoir
ingéré de vrais documents déclarés** (`docs/knowledge/README.md`) : servir des
affirmations inventées à un agriculteur serait le pire usage possible de ce
dépôt.

---

## 2. Jamais vérifié — « ça se déploie » est une attente, pas un fait

| À faire | Pourquoi ça compte |
|---|---|
| **Construire et démarrer l'image Docker** | Elle n'a jamais tourné : aucune machine avec Docker n'a préparé cette version |
| **TEST 2** — `curl https://$GALSEN_DOMAIN/health` | Le seul test qui prouve que le service répond derrière TLS |
| **TEST 6** — répéter le retour arrière (`docs/deployment/rollback.md`) | Une restauration qu'on n'a jamais jouée n'est pas une restauration |
| Vérifier `curl -I http://$GALSEN_DOMAIN/health` → **308** | Sinon le trafic reste en clair |
| Lancer une sauvegarde et **la sortir du volume** | Une sauvegarde qui vit dans le volume meurt avec lui |

---

## 3. Configuration à écrire avant le premier démarrage

Depuis `.env.example`, dans un `.env` **jamais commité** :

```bash
GALSEN_DOMAIN=            # le nom de domaine, DNS déjà pointé sur la machine
GALSEN_TLS_EMAIL=         # pour recevoir les alertes d'expiration de certificat
GALSEN_API_KEYS=          # clés réelles, forme cle:role:sujet
GALSEN_STORAGE_BACKEND=sqlite     # sinon RIEN ne survit à un redémarrage
GALSEN_DATA_DIR=          # où vivent les données
GALSEN_BACKUP_DIR=        # hors du volume de données
GALSEN_TRUSTED_PROXIES=   # réseau Docker, 172.16.0.0/12 par défaut
```

Ports **80 et 443** ouverts — le 80 n'est pas optionnel, la délivrance du
certificat passe par lui.

---

## 4. Risques connus, à accepter ou à corriger avant d'ouvrir

| Risque | État |
|---|---|
| **Les identités sont déclarées, pas vérifiées** | Une clé prouve une attribution, pas une personne (ADR-010, étape 2) |
| **Une révocation de clé ne survit pas à un redémarrage** | Avec `restart: unless-stopped`, un plantage restaure une clé compromise |
| **7 points de sécurité non garantis** | Listés par `/security/posture` — dont : bac à sable sans isolation réseau ni disque, portillon et audit en mémoire si `sqlite` n'est pas déclaré |
| **Une seule instance** | ADR-009 : la deuxième est refusée au démarrage, volontairement |
| **`flock` et SQLite supposent un disque local** | Sur un montage réseau, ni l'un ni l'autre ne garantit ce qu'il promet |

---

## 5. Capacités partielles — à ne pas promettre dans une communication

| Capacité | Ce qui marche | Ce qui ne marche pas |
|---|---|---|
| Voir l'écran | Le contrat, les refus, l'identité des éléments | Les backends AT-SPI / UIA / macOS demandent une machine de bureau |
| Piloter une interface | Le portillon, les refus, le contrat de geste | Idem |
| Navigateur | `visit`, `get_text`, `get_links` (urllib) | Aucun JavaScript, aucun clic : toute page applicative est hors de portée |
| MCP côté client | Épinglage, inspection des descriptions | Il ne se connecte à aucun serveur |

---

## 6. Ordre recommandé

1. **Réparer la CI** (4 tests : 2 à rendre portables, 1 étiquette à pousser, 1 antérieur).
2. `git push origin v0.1.0`.
3. `ollama serve` + un modèle → ferme C1, débloque toute la génération.
4. Écrire le `.env` (§3), `GALSEN_STORAGE_BACKEND=sqlite` compris.
5. Construire l'image, jouer **TEST 2** puis **TEST 6**.
6. Ingérer un corpus réel avant toute communication sur le contenu.
7. **Beta fermée** avec des personnes que tu connais. Public seulement après.

**Estimation honnête :** les points 1 à 5 tiennent en une journée pour quelqu'un
qui a la machine et le domaine. Le point 6 dépend des documents, pas du code.

---

## Ce que ce rapport ne dit pas

Il ne dit pas si la plateforme **plaît**. Aucun utilisateur réel ne s'en est
encore servi, et aucun test ne mesure cela. Le premier retour d'une vraie
personne apprendra plus que les 2 666 tests réunis.
