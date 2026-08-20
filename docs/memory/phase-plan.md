# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **aucun**
Dernier terminé  : **OPENCLAW COMPATIBILITY & SAFE INTEGRATION** — 19 phases,
                   **ADR-034**. Rapport → `docs/openclaw/feasibility-gates.md`
Phase courante   : **aucune** — le programme est fini, décision rendue
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète.

---

## La décision, pour ne pas la re-déduire

**OpenClaw est audité et n'est pas intégré.** Trois des douze portes du §19
répondent `NON` :

- **Le bac à sable** — désactivé par défaut, passerelle elle-même non isolée,
  `tools.elevated` sur l'hôte. Leurs mots : *« This is not a perfect security
  boundary. »* La couche qu'exige le §8 demande des espaces de noms et des
  cgroups que `src/sandbox/policy.py` consigne déjà comme absents.
- **L'isolation multi-utilisateurs** — *« Session IDs select routing; they do not
  authorize one tenant against another. »* L'alternative par conteneur est
  bloquée sur les mêmes privilèges, sur un Fleet **expérimental**.
- **La complexité** — la matrice du §5 rend **zéro `INTEGRATE`** : treize des
  quatorze capacités existent déjà ici.

**Zéro ligne de `src/` modifiée, zéro dépendance, zéro test touché.** Le §21
n'est pas entré : il était conditionnel à une approbation qui n'est pas venue.

## Le seul manque réel, et ce qui n'est pas autorisé

Le manque est un **canal**, pas un runtime : des canaux conversationnels
bidirectionnels, contre trois canaux de notification à sens unique.
`src/connectors/` a déjà le contrat. **Chiffrer un connecteur WhatsApp est
recommandé comme programme séparé — et n'est autorisé ni par l'audit ni par
ADR-034.**

## Ce qui vaut au-delà d'OpenClaw

ADR-014 met le mode souverain à vrai et **n'enregistre pas** les fournisseurs
hébergés. **Tout runtime subordonné portant son propre magasin d'identifiants
est un trou dans cette garantie que le test actuel ne peut pas voir**, puisqu'il
éprouve le chemin de modèle de GalSen IA.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases. ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases. ADR-031.
4. **Research Orchestration Integration** — 18 phases. ADR-032.
5. **Live Context Engine / Call.md** — 27 phases. ADR-033. **PR #31 ouverte.**
6. **OpenClaw Compatibility & Safe Integration** — 19 phases. ADR-034.
