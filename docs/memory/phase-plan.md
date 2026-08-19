# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **MASTER UPDATE DIRECTIVE V4 — MoneyPrinterTurbo comme fournisseur ajouté**
Plan complet     : `docs/providers/phase-plan.md`
Phases           : 15
Phase courante   : **M02.1 — en attente de confirmation**
Terminées        : M00.1, M00.2, M01.1, M01.2
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

## M01 — fait. `docs/providers/capability-matrix.md`

- **17 étapes média : 10 `READY`, 6 `BLOCKED`, 1 `ABSENT`.** Quatre des six
  blocages tiennent à **un `ffmpeg` manquant**, pas à un fournisseur : un
  générateur vidéo ne débloque au mieux que **2 étapes sur 17**.
- `wangp.py` = `ADAPTER_ONLY`, `generate()` **refuse toujours** — classé `KEEP` :
  le retirer effacerait la trace de *pourquoi* la vidéo est bloquée.
- Ingestion de références : `image_analysis` **disponible**, mesure dimensions /
  ratio / couleurs ; refuse visage, corps, géométrie, mouvement. Identité :
  7 dimensions, **7 `NOT_MEASURABLE`**. Aucun fournisseur ne change cela.
- **Classement §21 : 8 KEEP, 3 EXTEND, 1 ADAPT, 0 DEPRECATE, 0 REPLACE.**
  Aucune preuve trouvée pour un quelconque remplacement.
- **Hypothèse à vérifier en M02** : la synthèse vocale est `ABSENT` ici et MPT
  documente un TTS. Si c'en est un, MPT apporterait *l'étape que rien
  n'implémente* — argument d'intégration très différent de « un générateur
  vidéo ». À confronter à la source, pas au README.

## Ce que M02 fera

Rechercher MoneyPrinterTurbo **dans sa source** (§4, §5) : version, architecture,
API, pipeline, TTS, sous-titres, dépendances — et classer chaque capacité en
`SUPPORTED` / `PARTIAL` / `EXPERIMENTAL` / `UNKNOWN` / `UNSUPPORTED`.
