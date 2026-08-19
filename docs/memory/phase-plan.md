# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **CREATIVE CANVAS & CINEMA ORCHESTRATION EXTENSION**
Plan complet     : `docs/canvas/phase-plan.md`
Phases           : 17
Phase courante   : **K06.1 — en attente de confirmation** (couche cinéma, §10)
Terminées        : K00.1, K00.2, K01.1, K01.2, K01.3, K02, K03.1, K03.2, K04.1,
                   K04.2, K05.1, K05.2
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente en vigueur depuis le 2026-08-19** :
`.claude/rules/post-integration-validation.md` — toute phase se termine par une
validation de non-régression complète, jamais par une compilation.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases.
   `docs/providers/final-report.md`, ADR-030.

## Ce que les sondes ont déjà établi

Les **5 dépôts sont joignables** (`200`). Mais **2 n'ont aucun fichier de
licence** — ni `LICENSE`, ni `.md`, ni `.txt`, ni `COPYING`, sur `main` **ni**
`master` : `clearsolid/open-higgsfield-ai` et `troy1471-sys/open-higgsfield`.

La directive les annonce MIT tous les deux. **L'absence de licence n'est pas
MIT : c'est tous droits réservés.** K02 est donc une porte, pas une formalité —
deux candidats peuvent être écartés avant qu'une seule idée en soit extraite.

Les deux servent en outre une première ligne de README identique : l'un est
peut-être une copie de l'autre, ce que K01 doit établir.

## K00 — fait. `docs/canvas/audit.md`

**§11 demande 15 types de registre ; l'essentiel existe déjà** en champs sur deux
types. `CreativeProvider` en porte 15, `LicenceRecord` 6. **Trois manques réels
seulement** : `ProviderPrivacyPolicy` (§20 n'a aucun logement — où vont les
médias, sont-ils conservés, l'exécution locale est-elle possible), un **niveau de
confiance par type de nœud** (la frontière existe, la correspondance non), et un
`GenerationResult` partagé (sans objet tant qu'aucun fournisseur ne tourne).

**Sécurité mesurée : 7 failles, et `score: None`** — le module refuse de se noter
*« une note ferait disparaître la faille qui compte derrière la moyenne de celles
qui ne comptent pas »*. Trois touchent ce programme : système de fichiers
(un canvas qui reçoit une photo en hérite), réseau, et **portillon d'approbation
en mémoire** (un redémarrage perd les décisions de consentement).

**L'auto-réparation porte déjà `rollback` et `run_validation`** — c'est ce qui
rend la nouvelle règle permanente implémentable et non velléitaire.

**Deux systèmes de provenance existent, légitimement** : `acquisition/` pour
l'origine d'un *fait*, `creative/jobs.py` pour celle d'un *artefact*. Un nœud de
canvas produit des artefacts : il utilise le second. En écrire un troisième
serait la faute.

**Conclusion : le canvas est un problème de composition, pas de construction** —
l'inverse de ce que suggérerait une implémentation de graphe de nœuds, et la
raison pour laquelle §5 dit de ne pas simplement embarquer OpenCanvas.

## Ce que K01 fera

Auditer les cinq dépôts un par un (§2, §4), en commençant par les trois dont la
licence a été vérifiée — les deux sans licence attendent la porte K02.
