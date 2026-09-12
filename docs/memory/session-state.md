# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-09-12 (les tests de capacité absente ne mesurent plus la machine ; la suite est verte)

**En cours** : rien.

**Terminé** — commit `f8e7dc7`, poussé sur `claude/arena-personal-ai-qh66ix` :
- Instrument de l'absence dans `conftest.py` : `module_absent(*noms)` (un `None`
  dans `sys.modules` lève `ImportError` comme un paquet absent) et
  `capacite_forcee` (pour ce qui ne tient pas à un import : le binaire `ffmpeg`,
  le registre de transcription du VOLET 32). `tests/test_capacite_absente.py`
  prouve l'instrument lui-même — 7 tests, 3 sabotages.
- Les 24 échecs et 6 erreurs du 10/09 sont corrigés à la source : ils venaient de
  tests qui affirmaient une absence en comptant sur le bac à sable.
- Quatre affirmations devenues fausses corrigées **dans `src/`** : `_s09` de
  `golden.py` **exigeait** qu'une sonde manque et **levait** (c'est lui qui
  emportait les 6 erreurs), la note de `language_coverage()`, la docstring et
  `BLOCAGES["ffmpeg"]` de `moneyprinterturbo.py`.
- `faster-whisper` : `DECLARATIONS_D_EXECUTION` dans `test_requirements.py`
  admet `requirements-audio.txt`, exclut `-dev` et `-training` nommément, avec
  deux contre-tests.
- **Mesuré le 12/09, après la dernière édition : 7394 passés, 11 ignorés, 3
  désélectionnés, 0 échec, 0 erreur** (9 min 07). `ruff check src tests scripts
  agents conftest.py` propre. Aucun test supprimé ni affaibli : 215 → 223
  collectés dans les fichiers touchés, plus 7 nouveaux.

**Prochaine étape** : la P0 de `priorities.md` — `ollama serve` avec un modèle
de contexte ≥ 8192, sur la machine du propriétaire. Rien dans le dépôt ne
l'attend.

**Bloqué** : rien. Deux constats notés sans être corrigés — `CLAUDE.md` affirme
encore que le `ffmpeg` de cette machine est `--disable-everything` (mesure du
17/08, fausse dans ce bac à sable) ; `capabilities.clear_cache()` vide un cache
que rien n'écrit (P3 de `pending-work.md`).

---

### Sessions précédentes

**2026-08-24 — les dix épreuves** : mission « RUN THE FIRST REAL MODEL TEST »,
harnais câblé sur le **vrai** `/chat` (`src/model_engine/evaluation_suite.py`,
`scripts/models/evaluate.py`), branche `claude/galsen-ia-phases-ukwz7p`, PR #37.
**Aucun modèle n'a répondu ici** : `llama-cpp-python` s'installe, mais
`ollama.com`, `huggingface.co`, `hf-mirror.com`, `modelscope.cn`, `gpt4all.io`
→ `000`, `github.com/…/releases` → `403`. Aucun paquet pypi n'embarque de
poids utilisables (tinyllama, smollm, llm-gguf, minillm testés : code seul).
Prochaine étape restée sur la machine du propriétaire : `ollama serve` +
`ollama pull qwen3.5:9b` + `scripts/models/evaluate.py`. Mesuré alors :
7371 passés, 9 ignorés, 3 désélectionnés, 0 échec.

**2026-08-24 — Phase 3 (ADR-042)** : `role_preferences` tranche entre égaux,
Qwen3.5 reconnu, quatre familles serveur préparées avec les commandes vLLM
officielles recopiées.

**2026-08-24 — P3, le chat critique sa réponse (ADR-041)** et `src/skills/`
branchée. Banc des critiques : 66,7 % de détection, 0 % de fausse alerte.

**2026-08-24 — Routage des modèles (ADR-040)** : il ne sélectionnait pas, il
prenait le premier de la liste. Six causes mesurées. Dix types de tâche et huit
intentions atteignent cinq modèles distincts.

**2026-08-23 — `/chat` rédige (ADR-039)**, 19 phases. `src/chat/` compose une
réponse et appelle `ModelManagerImpl`. « bonjour » : 1 092 ms → 77 ms.
Puis bibliothèque de compétences (`src/skills/`, idée d'Odyssey, MIT) — **non
branchée**.

**2026-08-22 — AUDIT #01 `codebase-memory-mcp`**, 16 phases → `KEEP FOR RESEARCH`.
Rapport : `docs/research/codebase-memory-mcp-audit.md`. Rien installé, rien intégré.

**2026-08-20 — Audit OSS (22 phases, ADR-037)**, PR #33 : douze projets, **zéro
`INTEGRATE`**, 16 documents, zéro ligne de `src/` touchée. *Le troisième audit
externe d'affilée à trouver le défaut ici plutôt que chez son sujet.*

**2026-08-20 — Branche parallèle abandonnée** : `claude/galsen-ia-phases-ukwz7p`
avait **refait** le programme Creative Intelligence déjà fusionné en PR #28.

**2026-08-20 — Finalisation, PR #32** : ADR-036 (Apache-2.0).
**2026-08-19/20 — OpenClaw (ADR-034 : ne pas intégrer)** et **DeepSeek Harness
(ADR-035 : implémentation non autorisée)**.
**2026-08-19 — Live Context (ADR-033)**, 27 phases, PR #31.
**2026-08-19 — Creative Canvas (ADR-031), Research Orchestration (ADR-032)**, PR #29.
**2026-08-18/19 — Universal Creative Intelligence, MoneyPrinterTurbo (ADR-030)**,
PR #28. **MPT ne génère pas de vidéo.**
**2026-08-18 — ADR-029 : la plateforme a des comptes.** PR #26.
**2026-08-17 — Coding Engine et interopérabilité** (ADR-028, ADR-023). PR #25.
**2026-08-16 — Moteur média universel**, 32 phases. Aucune synthèse vocale ici.

**Hérité, toujours vrai**
- Ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` vide — mesuré par `capture.py`.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
- **2026-08-29 — PR #38** : plan de phase ARENA → GalSen IA (VOLET 65),
  fusionné dans `main` le 2026-09-02. GalSen IA absorbe ARENA sous
  `src/arena/`, licence Apache-2.0 commune, transfert fichier par fichier
  (sans historique Git — 6 secrets dans l'historique d'ARENA), rotation de
  clés préalable et séparée.
