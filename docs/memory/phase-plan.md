# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **MASTER UPDATE DIRECTIVE V4 — MoneyPrinterTurbo comme fournisseur ajouté**
Plan complet     : `docs/providers/phase-plan.md`
Phases           : 15
Phase courante   : **M01.1 — en attente de confirmation**
Terminées        : M00.1, M00.2
Cadence          : **deux phases par tour** (demandé par le propriétaire le 2026-08-19)

---

## Programme précédent, terminé

**Universal Creative Intelligence (directive V4, 81 sections) : 44 phases sur 44.**
Rapport final → `docs/creative/final-report.md`. Plan → `docs/creative/phase-plan.md`.
Ne pas le rouvrir ; §1 du nouveau programme interdit de reconstruire ce qui marche.

## M00 — fait. `docs/providers/audit.md`

- Le rapport date du 2026-08-16, **29 commits en arrière** : 5 chiffres périmés
  (131→142 routes, 5369→6191 tests, 27→30 ADR, 14→15 moteurs ; les agents
  concordent). **Aucune contradiction de fond** — toutes les affirmations
  vérifiables du rapport tiennent encore.
- **Trois** abstractions de fournisseurs, pas deux : `model_engine` (modèles de
  langue), `media/providers` (contrat de génération), `creative/providers`
  (licence comme entrée de routage). La troisième a été trouvée en auditant.
- `creative/providers.py` déclare **étendre** `media/providers/base.py` (ADR-024),
  donc la superposition est déjà tranchée — ce qui dérisque M05.

## Ce que M01 fera

Auditer les systèmes vidéo, références, identité et audio **existants** (§36
STEP 4-6, §21) : les vérifier contre le code, jamais les réécrire.
