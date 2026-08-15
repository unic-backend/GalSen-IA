# Darra J — phase plan

Programme : **DARRA J — moteur d'intelligence éducative nationale**
(directive du propriétaire, 20 VOLETs).
Base gelée : `1a586bc`, 4480 tests, `ruff` propre.

**État** : VOLETs 1 à 8 terminés.
**Suivant** : VOLET 9 — quiz et évaluation.

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
V9   Quiz et évaluation                               → 2 phases
V10  Mode enseignant                                  → 1 phase
V11  Mode élève                                       → 1 phase
V12  Mode parent                                      → 1 phase
V13  Confidentialité et autorisation                  → 2 phases
V14  Graphe éducatif                                  → 2 phases
V15  Modèle de maîtrise                               → 1 phase
V16  Couche multilingue éducative                     → 1 phase
V17  Laboratoire d'évaluation                         → 2 phases
V18  Échelle et résilience                            → 1 phase
V19  Auditabilité institutionnelle                    → 1 phase
V20  Aptitude à la production                         → 1 phase
```

**Total : 28 phases.** Terminées : 12.

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

## La règle qui tient tout le programme

Le curriculum canonique est **vide**, et il le reste tant qu'une autorité n'a
rien fourni. Les fixtures portent `NON_OFFICIAL_TEST_DATA` dans leur autorité et
`is_official` rend `False` pour elles — la marque survit à la sérialisation, donc
à la copie et au stockage.

L'état honnête visé à la fin du programme :

> **ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING.**
