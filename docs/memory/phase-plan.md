# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **MASTER UPDATE DIRECTIVE V4 — MoneyPrinterTurbo comme fournisseur ajouté**
Plan complet     : `docs/providers/phase-plan.md`
Phases           : 15
Phase courante   : **aucune — programme terminé**
Terminées        : M00.1 → M09 (15 phases sur 15)
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

## M02 — fait. `docs/providers/moneyprinterturbo-research.md`

**MoneyPrinterTurbo ne génère pas de vidéo.** Vérifié dans la source, pas le
README : `search_videos_pexels/pixabay` télécharge des rushes de banques
d'images, `moviepy` + `ffmpeg` les assemble. C'est un outil de **composition**,
pas de génération. Aucun modèle ne produit de pixel.

**Conséquence décisive** : MPT exige un **vrai `ffmpeg`** — exactement le
blocage de 4 des 6 étapes média d'ici. Il **ne tournerait pas non plus** sur
cette machine. Un adaptateur écrit ici rapporterait `BLOCKED`, comme `wangp.py`.

**Licence : MIT**, lue à la source. Premier candidat des deux programmes dont la
licence a pu être lue.

**14 capacités sur 26 sont `UNSUPPORTED`** — et §23 avait prédit exactement
cette liste : ni identité, ni références, ni continuité, ni contrôle caméra.
Elles restent la responsabilité de GalSen IA.

**Le cadrage s'inverse** : le meilleur argument d'intégration n'est pas la vidéo
— il n'en fait pas — mais **le TTS et l'ASR**, les deux capacités que cette
plateforme mesure `ABSENT` et `UNAVAILABLE`.

## M03 et M04 — faits. `licence-matrix.md`, `alternatives.md`

**Le dépôt est MIT ; l'arbre de dépendances ne l'est pas.**
`edge-tts` — c'est-à-dire **la capacité même pour laquelle on voudrait MPT** —
est **LGPL-3.0**, et le SDK Azure est **propriétaire**. C'est exactement la
confusion que §30 existe pour empêcher.

**Les droits sur la sortie sont `UNKNOWN`** : les rushes viennent de Pexels et
Pixabay, et personne ici n'a lu leurs conditions. Une vidéo produite ainsi puis
vendue reposerait sur des termes que nul n'a lus. Le fournisseur doit donc
déclarer `commercial=UNKNOWN` — et le routeur existant le refusera pour tout
travail commercial, ce qui est le comportement déjà construit (ADR-024).

**Porte §40 n°10 : la seule qui n'est pas verte**, et de façon intéressante —
licence bonne pour le code, non résolue pour ce qu'on veut vraiment.

**M04 : le TTS de MPT n'est ni le seul ni le plus permissif.** `kokoro-tts` est
**MIT et local** ; `edge-tts` est LGPL-3.0 et appelle un service distant. Et
`whisperx` (BSD-2) couvre en plus la **séparation de locuteurs**, que cette
plateforme rapporte `BLOCKED` sans aucune implémentation. Couverture wolof /
sérère / pulaar : **`UNKNOWN` pour tous**, non vérifiée.

## M05 et M06.1 — faits. ADR-030 acceptée

**La décision qui a le plus de conséquence : une tâche nouvelle,
`stock_assembly`.** Déclarer `text_to_video` aurait été une erreur de catégorie
réelle — un routeur aurait choisi cet assembleur pour « génère une scène avec mon
ami » et rendu des rushes d'un inconnu. Deux actes, deux noms.

Reste décidé : registre **créatif** (le seul qui lit une licence avant de
choisir), invocation **`API`** (`edge-tts` est LGPL-3.0 : lier n'est pas
appeler), `commercial=UNKNOWN` (droits sur la sortie non lus), et **aucune
dépendance ajoutée**.

`src/media/providers/moneyprinterturbo.py` : `health()` rapporte les **trois**
conditions manquantes ensemble (service, ffmpeg, banque d'images) avec le geste
qui répare chacune ; `generate()` **refuse**, comme `wangp`. 20 tests.

## M06.2 et M07 — faits

**Le routeur créatif sélectionne un fournisseur pour la première fois** des deux
programmes. Trois demandes, trois réponses distinctes :

| Demande | Réponse |
|---|---|
| `stock_assembly`, non commercial | **`SELECTED` moneyprinterturbo** |
| `stock_assembly`, **commercial** | `NO_PROVIDER` — droit non établi |
| `text_to_video` | `NO_PROVIDER` — jamais offert comme générateur |

Le refus commercial marche **sans une ligne de code de plus**, comme ADR-030
l'avait prévu.

**Un vrai défaut trouvé par cette entrée** : `availability()` traitait
`min_vram_gb = 0` comme un besoin de VRAM et écartait un fournisseur qui n'a
besoin d'aucun GPU. `0` (besoin établi et nul) et `None` (non déclaré) sont deux
informations. Corrigé étroitement : seul un besoin **strictement positif**
déclenche la mesure, et un test garde que les candidats à GPU restent écartés.

**§29 (repli), dit honnêtement** : aucun autre fournisseur ne sert
`stock_assembly`, donc un échec de MPT donne `NO_PROVIDER`. Ce n'est pas un repli
qui fonctionne — c'est l'absence de second candidat, et le routeur refuse de
substituer plutôt que de servir autre chose.

## M08 — fait. `docs/providers/golden-mapping.md`

**19 des 22 tests de §38 étaient déjà couverts** — par `golden.py` (25 scénarios)
et par les tests de M06/M07. En réécrire un aurait gonflé le compte sans ajouter
une ligne de couverture. **3 écrits** : MPT-06, MPT-07, MPT-08.

**MPT-07 a trouvé un vrai défaut dans ma propre déclaration** : l'adaptateur
annonçait 1920×1080, et les bornes sont comparées **axe par axe** — un
1080×1920 vertical était donc refusé sur sa hauteur, c'est-à-dire **le cas
d'usage principal** de MPT. Corrigé à 1920 sur les deux axes, avec
l'imprécision nommée dans le code.

**MPT-06 écrit honnêtement** : aucun second fournisseur ne sert
`stock_assembly`, donc le test affirme le **refus de substituer**, pas un repli
qui marche. Un second test garde qu'il n'y a qu'un servant — le jour où il y en
aura deux, c'est là qu'on le verra.

**Écart relevé (§35), non résolu** : `min_vram_gb = None` veut dire « aucun GPU
requis » côté média et « rien n'a été déclaré » côté routage créatif. Les deux
se défendent isolément ; adjacents, c'est un piège. Écrit pour que le prochain ne
le découvre pas à ses dépens.

## M09 — fait. Programme terminé. `docs/providers/final-report.md`

**15 phases sur 15.** La phrase à retenir : **MoneyPrinterTurbo ne génère pas de
vidéo**, et l'avoir su *avant* d'écrire l'adaptateur est toute la valeur des 19
étapes d'audit que §36 impose d'abord. Écrit en premier, il aurait été déclaré
`text_to_video`, et un routeur aurait fini par servir les rushes d'un inconnu à
qui demandait son ami.

**Mesuré** : `pytest -q` → **6 233 passent, 1 échec** (`v0.1.0`, antérieur).
39 tests ajoutés. Sondes : santé 3,5 ms, routage 0,44 ms sur 10 candidats.
Aucun GPU requis — seul chemin vidéo des deux programmes dans ce cas.

**Trois gardes du dépôt ont attrapé des défauts à moi**, tous à raison : le
chargeur du corpus (une valeur sans dire comment elle a été établie), le compte
d'ADR (30 → **31**), et **trois variables d'environnement introduites sans être
documentées**.

**Reste dû, nommé plutôt qu'oublié** : une décision TTS à part entière
(`kokoro-tts` est MIT et local, `edge-tts` est LGPL-3.0), `whisperx` pour la
séparation de locuteurs, l'écart `None` entre couches média et créative, et la
lecture des conditions Pexels/Pixabay.

**Blocage unique** : `ffmpeg`. Le même que quatre étapes média — une seule
installation hors dépôt débloque cinq choses à la fois.
