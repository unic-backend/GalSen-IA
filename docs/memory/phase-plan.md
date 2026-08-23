# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **LINUX KERNEL ARCHITECTURE RESEARCH AUDIT**
                   Brief du propriétaire, 2026-08-23
Chapitres        : **13**
Phases           : **18**
Phase courante   : **1.3 — en attente de confirmation**
Terminées        : **1.1**, **1.2** → `docs/research/linux-kernel-architecture-audit.md`
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Ce que le brief interdit** : copier du code noyau, vendorer un composant,
introduire une dépendance Linux, modifier l'architecture existante. Rien n'est
implémenté pendant cet audit. `RESEARCH → EVALUATE → DOCUMENT → COMPARE →
RECOMMEND`, et pas un pas de plus (`.claude/rules/spec-driven-governance.md`).

---

## Ce qui a été mesuré avant d'écrire ce plan

Un plan qui suppose ses sources accessibles n'est pas un plan. Mesuré le
2026-08-23, depuis cette machine :

| Source | Réponse |
|---|---:|
| `raw.githubusercontent.com/torvalds/linux/…` | **200** |
| `github.com/torvalds/linux` | 403 |
| `docs.kernel.org` | **000** |
| `www.kernel.org` · `git.kernel.org` | 000 |
| `spdx.org` | 000 |

**L'audit est faisable, et par la meilleure source.** `docs.kernel.org` n'est que
le rendu de `Documentation/` dans l'arbre ; cet arbre répond. Vérifié fichier par
fichier : `COPYING` (496 o), `cgroup-v2.rst` (135 502 o), `ftrace.rst`
(145 229 o), `fault-injection.rst` (19 325 o), `credentials.rst` (20 875 o),
`license-rules.rst` (18 477 o).

Ce qui reste hors d'atteinte et devra être dit `UNKNOWN` plutôt que deviné :
le texte SPDX canonique et tout ce qui ne vit que sur `kernel.org`.

---

## Le plan

```
Ch. 01  Audit du GalSen IA réel                  → 3 phases
        1.1 orchestration, agents, ordonnancement, cycle de vie, files ✅
        1.2 ressources, isolation, bac à sable, sécurité, permissions ✅
        1.3 auto-réparation, observabilité, mémoire, config, dégradation

Ch. 02  Étude de l'architecture Linux            → 2 phases
        2.1 processus, ordonnancement, mémoire, namespaces, cgroups, capabilities
        2.2 modules, VFS, traçage, injection de fautes, frontières, synchronisation

Ch. 03  Extraction des principes                 → 2 phases
        3.1 les huit champs, pour les concepts d'isolation et de ressources
        3.2 les huit champs, pour fautes, observabilité et frontières

Ch. 04  Auto-réparation                          → 1 phase (indivisible)
Ch. 05  Gestion des ressources                   → 1 phase (indivisible)
Ch. 06  Isolation des agents                     → 1 phase (indivisible)
Ch. 07  Observabilité                            → 1 phase (indivisible)
Ch. 08  Frontières architecturales               → 1 phase (indivisible)
Ch. 09  Licences                                 → 1 phase (indivisible)
Ch. 10  Preuve qu'aucun code n'a été copié       → 1 phase (indivisible)
Ch. 11  Portes de faisabilité (10 questions)     → 1 phase (indivisible)
Ch. 12  Classement A–F + plus petite implémentation réversible
                                                 → 1 phase (indivisible)

Ch. 13  Rapport final, 22 points                 → 2 phases
        13.1 points 1 à 11
        13.2 points 12 à 22, verdict
```

**Total : 18 phases.**

---

## Ce que je dois te dire avant que tu confirmes

**Le chapitre 01 décide de tout le reste.** Le brief le dit lui-même : *« ne
suppose pas qu'une capacité est absente parce qu'elle porte un autre nom »*.
Cette plateforme a déjà un bac à sable qui applique des limites du noyau
(`src/sandbox/`), une dégradation mesurée (`src/integration/degradation.py`), une
piste d'exécution suivable de bout en bout (`/observability/trail/{id}`) et une
auto-réparation. La plupart des principes Linux vont probablement tomber en
**D — DÉJÀ COUVERT**, et ce sera le résultat, pas un échec de l'audit.

**Deux choses que je ne peux pas mesurer ici**, et qui resteront `UNKNOWN` :
tout ce qui concerne le GPU (cette machine n'en a pas) et le comportement sous
charge réelle (aucun fournisseur de modèle n'y répond).

**Un point d'intendance** : la PR #36 est ouverte et non fusionnée, et je n'ai
autorisation de pousser que sur `claude/galsen-ia-phases-ukwz7p`. Cet audit
produit des documents ; ils atterriront donc dans cette PR, à côté du redesign
chat-first. Si tu préfères qu'ils vivent seuls, fusionne #36 d'abord — c'est ta
décision, pas la mienne, et elle ne bloque pas le démarrage.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **REDESIGN CHAT-FIRST** — 8 chapitres, 11 phases. `POST /chat`, `/ui/` sert la
   conversation, `/ui/admin/` le tableau de bord, menu de 14 domaines.
   **Constat qui reste vrai** : aucun des 17 agents ne rédige ; `/chat` rend le
   refus des agents et ne converse pas encore. L'étape de rédaction qui le
   rendrait conversant **n'est pas autorisée**.
2. **AUDIT #01 `codebase-memory-mcp`** — 16 phases, `KEEP FOR RESEARCH`.
3. **SUPERPOWERS** — audit 24 phases + 11 d'implémentation. **ADR-038**.
4. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. **ADR-037**.
5. **OpenClaw** (ADR-034), **DeepSeek Harness** (ADR-035) : non intégrés.
6. **Live Context** (ADR-033), **Creative Canvas** (ADR-031),
   **Research Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).
