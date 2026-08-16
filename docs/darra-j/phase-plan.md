# Darra J — phase plan

Programme : **DARRA J — moteur d'intelligence éducative nationale**
(directive du propriétaire, 20 VOLETs).
Base gelée : `1a586bc`, 4480 tests, `ruff` propre.

**État** : **les 20 VOLETs sont terminés** — 28 phases sur 28.
**Rapport final** : `docs/darra-j/final-report.md`.

---

## Ce que la cartographie a mesuré (VOLET 1)

Détail → `docs/darra-j/integration-map.md`. Le résultat en une ligne : **la
majorité de l'architecture demandée existe déjà**, et la directive XLIX avait
raison de prévenir de ne pas le supposer absente.

| Réutilisé tel quel | Ce qui reste à construire |
|---|---|
| rangs de sources (`SourceTier`), états d'acquisition avec validation **humaine**, portillon d'approbation (ADR-006), RBAC + isolation, couches de mémoire, routage `UNKNOWN`, provenance des entités, wolof mesuré, barème d'évaluation, stockage ADR-005, indépendance du modèle, audit et piste de bout en bout, harnais d'auto-réparation | objets canoniques de curriculum, résolution déterministe, registre de versions, cohérence entre usagers, enregistrements de conflit, rôles éducatifs, modèle de maîtrise, graphe éducatif |

**8 composants neufs sur 20 VOLETs** : le reste est du branchement.

---

## Les 20 VOLETs, et leur découpage

```
V1   Découverte et cartographie                       → 1 phase   ✅
V2   Modèle canonique de curriculum                   → 1 phase   ✅
V3   Versionnement et provenance                      → 2 phases  ✅
V4   Récupération déterministe                        → 2 phases  ✅
V5   Cadre d'ingestion                                → 2 phases  ✅
V6   Pare-feu anti-hallucination                      → 1 phase   ✅
V7   Cohérence entre usagers                          → 1 phase   ✅
V8   Moteur d'explication pédagogique                 → 2 phases  ✅
V9   Quiz et évaluation                               → 2 phases  ✅
V10  Mode enseignant                                  → 1 phase   ✅
V11  Mode élève                                       → 1 phase   ✅
V12  Mode parent                                      → 1 phase   ✅
V13  Confidentialité et autorisation                  → 2 phases  ✅
V14  Graphe éducatif                                  → 2 phases  ✅
V15  Modèle de maîtrise                               → 1 phase   ✅
V16  Couche multilingue éducative                     → 1 phase   ✅
V17  Laboratoire d'évaluation                         → 2 phases  ✅
V18  Échelle et résilience                            → 1 phase   ✅
V19  Auditabilité institutionnelle                    → 1 phase   ✅
V20  Aptitude à la production                         → 1 phase   ✅
```

**Total : 28 phases.** Terminées : **28**.

---

## Ce que le VOLET 3 a trouvé

Un défaut réel, trouvé en **rejouant un import** plutôt qu'en relisant le code :
`ingested_at` entrait dans l'empreinte d'une version. Deux imports du même décret
officiel paraissaient donc différents, et le registre refusait un import
identique — c'est-à-dire qu'il refusait exactement le cas normal d'une reprise.
La provenance ne compte désormais dans l'empreinte que par ses **champs
documentaires** : ce que l'autorité a publié, pas ce que nous en avons fait.

---

## Ce que les VOLETs 7 et 8 ont trouvé

Deux défauts de forme, l'un évité, l'autre corrigé.

**VOLET 7** — comparer les `unit_id` aurait suffi à faire passer le test de la
directive VI, et n'aurait rien garanti : deux enregistrements aux mêmes
coordonnées portent le **même** identifiant même si leurs titres officiels
diffèrent. L'identité comparée est donc `unit_id:content_hash`, et un test pin
exactement ce cas (`test_un_titre_reecrit_change_l_identite_pas_l_identifiant`).

**VOLET 8** — la réponse « sans explication » rendait moins de clés que la
réponse nominale : un appelant lisant `language` ou `level_name` aurait échoué
**précisément** quand le modèle avait manqué, c'est-à-dire au pire moment. Les
deux formes sont désormais identiques, et un test les compare.

---

## Ce que les VOLETs 9 et 10 ont trouvé

**Un trou réel, et il était petit.** `record_decision()` exige un décideur nommé
— mais acceptait n'importe quelle chaîne, y compris le nom de la plateforme.
Darra J pouvait donc prendre une décision scolaire puis l'enregistrer sous son
propre nom : elle serait passée de « ne décide pas » à « décide et le note ».
`is_platform_identity()` ferme le trou, **mot par mot** et jamais par
sous-chaîne : « ia » est contenu dans « Mariama », et refuser une décision parce
que la personne s'appelle Mariama aurait été un défaut bien pire que celui
qu'on fermait. Deux jeux de tests pinnent les deux sens.

**Une régression, trouvée par la suite complète.** Le libellé d'attribution
valait `GALSEN_IA_DARRA_J` — la forme exacte d'une variable d'environnement, et
`tests/test_config_environment.py` l'a lu comme une variable non documentée. Le
libellé était le fautif, pas le test : il est devenu `GalSen IA — Darra J`.

---

## Ce que les VOLETs 11 et 12 ont trouvé

**Un défaut trouvé en confrontant la promesse au code.** `parent_report()`
affirmait rendre `INSUFFICIENT_EVIDENCE` « tel quel » ; `child_progress()` ne
rendait que des décomptes bruts. Un parent lisant « 1 sur 1 » y aurait lu une
maîtrise là où il n'y a aucune mesure — et c'est un parent qui le lit. Le
verdict est désormais rendu, et **recalculé sur le cumul** : deux devoirs de
deux items mesurent quatre items, alors que chacun pris seul dirait « pas
assez ». Les deux sens sont pinnés.

**Une garantie construite plutôt que promise.** La vue élève d'un quiz
(`student_quiz`) est bâtie champ par champ à partir d'une liste positive, jamais
obtenue en retirant la clé de correction. Un test compare les champs de
`QuizItem` à ceux de la vue : tout champ non déclaré visible est absent, **y
compris ceux qui n'existaient pas quand la vue a été écrite**.

`src/darra_j/access.py` porte la frontière commune aux deux modes. Les rôles
éducatifs eux-mêmes rejoignent `src/api/rbac.py` au VOLET 13 : c'est une garde,
pas un second système de permissions.

---

## Ce que le VOLET 13 a trouvé

**Un élargissement silencieux, évité de justesse.** `Role.ADMIN` était calculé
par compréhension — *toutes* les permissions. Déclarer `curriculum:publish`
aurait donc suffi à rendre GalSen IA capable de publier un curriculum officiel,
c'est-à-dire exactement ce que la directive lui refuse, sans que personne l'ait
décidé. `PERMISSIONS_HORS_PLATEFORME` soustrait explicitement les permissions
qui appartiennent à quelqu'un d'extérieur : publier un programme (une autorité
éducative) et lire le travail d'un enfant (ceux qui lui sont rattachés).

L'invariant existant `test_admin_has_all_permissions` a donc été **resserré**,
pas assoupli : l'administrateur a toutes les permissions *de la plateforme*, et
la liste des exceptions est nommée et pinnée.

**Trois gardes existantes ont attrapé la même omission**, et c'est ce qu'elles
avaient été écrites pour faire : ajouter six rôles à `rbac.Role` sans les
déclarer ailleurs les aurait fait tomber en silence au minimum.

| Garde | Ce qu'elle a attrapé |
|---|---|
| `tests/test_tool_authorization.py` | six rôles sans plafond d'outils |
| `tests/test_knowledge_security.py` | six rôles absents de la table de sensibilité |
| `tests/test_rbac.py` | l'invariant « admin a tout », devenu faux à dessein |

**L'autorisation est une conjonction.** `src/darra_j/privacy.py` exige la
permission *et* le rattachement, et rapporte les deux refus séparément :
« ce rôle ne lit aucun apprenant » et « pas cet enfant-là » sont deux faits, et
les confondre rendrait le second impossible à diagnostiquer. Aucune permission
n'ouvre un apprenant non rattaché — elle n'a pas été créée.

---

## Ce que les VOLETs 14 et 15 ont trouvé

Aucun défaut à corriger cette fois — deux pièges évités, et il vaut mieux les
écrire que les oublier.

**Un graphe est l'artefact le plus convaincant qu'une plateforme puisse
produire**, et personne ne lit une arête en demandant qui l'a décidée. Chaque
arête porte donc `derived_from` : l'unité **et** le champ officiel dont elle
vient. Les prérequis officiels sont du texte (« La division euclidienne »), pas
des identifiants ; le rapprochement est une **égalité exacte** sur le titre
replié. « La division » et « La division euclidienne » restent donc deux titres,
et le second est rendu `DANGLING` avec son texte littéral. La leçon avait déjà
été payée une fois (`find_country`, VOLET 69).

Un cycle de prérequis publié est **rendu**, jamais coupé : couper produirait un
ordre plausible et cacherait un défaut institutionnel pour toujours.

**Tout modèle de maîtrise a la même défaillance discrète** : il produit un
niveau pour tout le monde, parce qu'un niveau est ce qu'on lui a demandé, et
« pas assez de données » finit arrondi au niveau le plus bas. `NOT_MEASURED` et
`INSUFFICIENT_EVIDENCE` sont donc **hors échelle**, et sous le plancher le ratio
n'est pas rendu du tout — deux réponses justes sur deux rendraient `1.0`, qui se
lirait comme un niveau. Aucun total non plus : un nombre unique se lit comme une
note.

Le graphe gagne sa place au VOLET 15 : `SECURE` sur les fractions alors que rien
n'a jamais été mesuré sur la division qu'elles exigent officiellement est une
affirmation fragile. L'état est **qualifié**, pas abaissé — inventer une
pénalité serait aussi fabriqué qu'inventer le niveau.

---

## Ce que les VOLETs 16 et 17 ont trouvé

**Un défaut réel, et il touchait le wolof.** La table d'alias ne conservait que
la forme **repliée** d'un terme : `mbéy` était stocké `mbey`, `péey` stocké
`peey`. Le repliement est correct pour *comparer* — c'est ce que fait
`expand_terms` — mais `translate` sert à **montrer** un terme à quelqu'un, et
rendait donc du wolof mal orthographié, alors que `ë`, `ñ` et `ŋ` sont des
lettres du standard CLAD et jamais des accents. La table garde désormais les
deux formes : `written` pour l'affichage, `terms` pour la recherche. Deux tests
pinnent les deux usages dans `tests/test_multilingual.py`.

**La réserve portait sur le mauvais bout du pont.** Une question posée en wolof
qui atteint un enregistrement par un terme français repose entièrement sur la
liste wolof non relue ; ne regarder que le terme d'arrivée déclarait la
correspondance sûre alors que c'est le **premier** pas qui ne l'est pas.

**Le laboratoire d'évaluation mesure les garanties, pas la connaissance.** Un
banc d'essai de curriculum a besoin de réponses attendues, elles doivent venir
du registre officiel, et le registre est vide — les écrire de mémoire serait
l'invention que tout ce paquet empêche. Sont donc mesurés aujourd'hui : le taux
d'hallucination (sur un générateur **instrumenté** : on vérifie qu'il n'est pas
appelé), la justesse des refus, la couverture de provenance, la cohérence entre
rôles et la fuite de note. Un taux sans cas rend `NOT_MEASURABLE`, jamais 100 % :
une suite vide qui affiche un score parfait fabrique de la confiance à partir
d'une absence. Ce qui n'est pas mesurable est **nommé avec sa raison**.

---

## Ce que les VOLETs 18, 19 et 20 ont trouvé

**Deux clés devinées au lieu d'être lues.** La sonde de résilience lisait
`registry_report()["published"]` — clé qui n'existe pas : le `.get(..., 0)`
aurait rendu 0 en silence pour toujours. La piste d'audit cherchait `from`/`to`
dans le journal du registre, qui écrit `de`/`vers` : la recherche n'aurait
jamais rien trouvé, et **chaque** piste aurait déclaré silencieusement qu'aucun
décideur n'avait été consigné — exactement le fait qu'un auditeur vient
vérifier. Les deux ont été trouvés en lisant le code appelé plutôt qu'en
supposant sa forme.

**Une règle du registre redécouverte par un test.** L'essai de concurrence
échouait sur `RegistryRefused : on n'ajoute pas une unité à un curriculum en
vigueur`. Ce n'était pas un défaut de verrou : c'était le registre qui tenait sa
règle. Le test vise désormais une version en préparation, et mesure donc le
verrou au lieu du refus.

**L'aptitude à la production est mesurée, pas déclarée.** Un registre ne
contenant que des fixtures rapporte zéro version officielle — la marque
`NON_OFFICIAL_TEST_DATA` existe précisément pour que cette fonction puisse les
distinguer, et un rapport vert sur un système vide se lit comme un feu vert de
déploiement.

---

## La règle qui tient tout le programme

Le curriculum canonique est **vide**, et il le reste tant qu'une autorité n'a
rien fourni. Les fixtures portent `NON_OFFICIAL_TEST_DATA` dans leur autorité et
`is_official` rend `False` pour elles — la marque survit à la sérialisation, donc
à la copie et au stockage.

L'état honnête visé à la fin du programme :

> **ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING.**
