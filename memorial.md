# Mémorial GalSen IA

Ce fichier décrit l'état du projet pour un agent qui arrive froid.

**Tous les nombres ci-dessous ont été comptés le 2026-08-19, pas recopiés.**
Un mémorial qui vieillit sans le dire est pire qu'un mémorial absent : il oriente
vers une plateforme qui n'existe plus. La version précédente annonçait 8 engines,
10 agents et « ~300 tests, tout est in-memory » — trois affirmations devenues
fausses.

---

## Où lire quoi, avant d'agir

| Fichier | Ce qu'il donne |
|---|---|
| `CLAUDE.md` | les règles et l'état publié, guardé par des tests |
| `docs/memory/session-state.md` | où la dernière session s'est arrêtée |
| `docs/memory/phase-plan.md` | le VOLET en cours et la phase en attente |
| `docs/architecture/overview.md` | l'architecture mesurée |
| `docs/architecture/decisions/` | les 33 ADR — aucune ne se contredit depuis la mémoire |

`docs/memory/completed-work.md` est un journal en ajout seul : le **chercher**,
jamais le lire en entier.

---

## État mesuré au 2026-08-19

| | Compté |
|---|---|
| Engines enregistrés (`EngineRegistry.available_engines()`) | **15** |
| Sous-systèmes sondés à part (`integration/degradation.SOUS_SYSTEMES`) | **9** |
| Agents (`agents/registry.yaml`) | **17** |
| Outils déclarés (`tools/tools.yaml`) | **24** — 13 exécutables sans surveillance |
| Routes API (`APIRoute` sur `src.api.server.app`) | **142** |
| ADR | **33** |
| Tests | **6 582 passent**, 12 ignorés, **1 échec** |

L'unique échec est `test_release_check` : l'étiquette **`v0.1.0` n'a jamais été
poussée** — `git ls-remote --tags origin` rend zéro étiquette. Il tombe
identiquement sur `main` ; ce n'est pas une régression, c'est un geste
d'exploitant qui n'a pas été fait.

**La persistance existe** (ADR-005, SQLite) : chaque engine portant un état
choisit son magasin par `GALSEN_STORAGE_BACKEND` (`in-memory` par défaut,
`sqlite` pour persister) et `GALSEN_DATA_DIR`. L'audit et l'approbation sont
inclus.

---

## Les paquets de `src/`

```
acquisition  agent  analytics  api  approval_engine  audit_engine  auth
client  code_edit  coding_engine  config  connectors  creative  darra_j
demonstration  document_intelligence_engine  embeddings  integration  interop
knowledge_engine  mcp  media  memory_engine  model_engine  multimodal
observability  plugins  proactive  research  router  routines  sandbox
security  services  storage  tool  tools  training
vision_intelligence_engine  web  wolof
```

Les cinq plus récents, chacun avec son rapport final :

| Paquet | Programme | Rapport |
|---|---|---|
| `src/creative/` | Universal Creative Intelligence, 44 phases | `docs/creative/final-report.md` |
| `src/media/` | Moteur média universel, 32 phases | `docs/media/final-report.md` |
| `src/darra_j/` | Intelligence éducative, 28 phases | `docs/darra-j/final-report.md` |
| `src/creative/canvas/` | Creative Canvas, 17 phases, ADR-031 | `docs/canvas/final-report.md` |
| `src/research/` | Research Orchestration, 18 phases, ADR-032 | `docs/research/final-report.md` |

---

## Ce que la plateforme ne fait pas, et le dit

C'est la partie la plus utile pour un agent froid, parce qu'elle évite de
promettre ce qui n'existe pas.

- **Rien ne génère d'image ni de vidéo.** 17 étapes média : 10 `READY`,
  6 `BLOCKED`, 1 `ABSENT`. La synthèse vocale est **absente**, pas manquante :
  aucune installation ne la produit ici.
- **Aucun fournisseur de modèle n'est configuré** : la génération répond
  `unavailable` tant qu'aucune clé n'est présente.
- **Aucun fournisseur de recherche externe ne tourne** : les deux candidats
  audités sont `BLOCKED`, et trois des programmes que l'un d'eux orchestre
  n'ont **aucune licence**.
- **Aucun curriculum sénégalais n'a été intégré** : aucun n'était disponible, et
  aucun n'a été écrit depuis la mémoire du modèle.
- **`ffmpeg` réel absent** : celui de cette machine est compilé
  `--disable-everything` et répond `-version` comme un complet.
- **Neuf domaines institutionnels sénégalais** sont refusés par le mandataire
  (`CONNECT → 403`, mesuré — ce n'est pas un refus des sites).

---

## Les règles qui expliquent le code

Elles reviennent partout et rendent le dépôt lisible :

1. **Une capacité se mesure en interrogeant l'outil**, jamais en vérifiant qu'un
   binaire existe.
2. **`UNKNOWN` n'est pas `NO`**, et n'est jamais une permission.
3. **Aucun classement sur un chiffre absent** — `None` veut dire *non mesuré*,
   jamais *zéro*.
4. **Le contenu externe est une donnée avec une origine**, jamais une
   instruction (`src/security/trust.py`).
5. **Rien n'entre dans la connaissance sans source**, et une approbation n'est
   jamais accordée par l'absence de quelqu'un pour refuser.
6. **Une capacité inachevée rapporte son état** ; elle ne rend jamais un
   résultat plausible.
7. **Un rapport porte sa date de mesure.** Un chiffre déduit se corrige par une
   exécution, pas par une addition.

---

## Le Cerveau local

| Composant | Détail |
|---|---|
| Serveur REST | `serveur_cerveau.py` — FastAPI, port 8000 |
| Modèle local | `qwen2.5-coder:14b` via Ollama (`localhost:11434`) |
| Lanceur | `Lancer_Claude_Gratuit.bat` |
| Prompt système | `prompts/systeme.md` |

Endpoints : `/health`, `/chat`, `/engines`, `/models`, `/reinitialiser`.
Documentation : `http://localhost:8000/docs`.

Chaque engine est chargé dans un `try/except` : le Cerveau fonctionne **même si
certains engines sont indisponibles**, et `/health` dit lesquels.

---

## Gestes qui appartiennent à l'exploitant

Aucun ne peut être fait depuis cet environnement.

1. **`git push origin v0.1.0`** — le seul test rouge, en quatre programmes.
2. **Installer un `ffmpeg` réel** — débloque cinq choses d'un coup.
3. **`ollama serve`** — ouvre la génération et la récupération sémantique.
4. **Installer un fournisseur de recherche** (`pip install web-search-mcp`) —
   transformerait cinq mesures `NOT_MEASURED` en chiffres.
5. **Supprimer `feature/service-unit-tests`** — cet environnement refuse la
   suppression de références distantes (403).
