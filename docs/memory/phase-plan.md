# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **RESEARCH ORCHESTRATION INTEGRATION**
Plan complet     : `docs/research/phase-plan.md`
Phases           : 18
Phase courante   : **R04.1 — en attente de confirmation** (abstraction
                   ResearchProvider)
Terminées        : R00.1, R00.2, R01.1, R01.2, R02, R03 — quatre audits dans
                   `docs/research/`
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente en vigueur depuis le 2026-08-19** :
`.claude/rules/post-integration-validation.md` — toute phase se termine par une
validation de non-régression complète, jamais par une compilation. La nouvelle
directive la redit mot pour mot à la fin ; elle s'appliquait déjà.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases.
   `docs/providers/final-report.md`, ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases.
   `docs/canvas/final-report.md`, ADR-031.

## Ce que les sondes ont déjà établi

**Les deux dépôts sont joignables, portent un vrai `LICENSE`, et sont en
Python.**

| Dépôt | Licence | Manifeste |
|---|---|---|
| `Panniantong/Agent-Reach` | **MIT**, © 2025 Agent Eyes | `pyproject.toml` |
| `sydasif/web-search-mcp` | **MIT**, © 2026 Syed Asif | `pyproject.toml` |

**C'est l'inverse du programme précédent**, où quatre dépôts sur cinq étaient en
JavaScript et deux n'avaient aucune licence. Ici du code pourrait réellement être
adoptable — même langage, même empaquetage, licence lisible des deux côtés.

R02 n'est donc pas une porte qui se fermera d'évidence : c'est un vrai audit de
dépendances, et la directive l'exige séparément. Le programme MoneyPrinterTurbo a
trouvé exactement ce piège — un dépôt MIT dont le chemin de capacité réel était
LGPL-3.0.

## Ce que R00 doit établir avant toute proposition de module

La plateforme est déjà dense ici : `src/knowledge_engine/` porte plus de
vingt-huit modules — dont `citations.py`, `freshness.py`, `contradictions.py`,
`knowledge_security.py`, `knowledge_cache.py`, `knowledge_validator.py` — plus
`src/services/search/`, `src/mcp/`, `src/connectors/` et `src/acquisition/`
(chemin d'acquisition sous contrôle humain, ADR-021, dix contrôles qualité).

Le programme précédent a mesuré que **neuf des onze sous-systèmes réclamés
existaient déjà**. Le pari honnête ici est que la proportion est au moins aussi
élevée. R00 classe chaque capacité — `EXISTING`, `EXTENSION_REQUIRED`,
`NEW_COMPONENT_REQUIRED`, `DEPRECATED`, `UNKNOWN` — avant qu'un seul module
nouveau soit proposé.

## Ce qui ne doit pas être reconstruit

Trois registres de fournisseurs et deux systèmes de provenance existent déjà.
STEP 9 le redit : *ne pas créer d'architecture de provenance concurrente*.
