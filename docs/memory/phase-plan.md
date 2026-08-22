# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **SUPERPOWERS COMPATIBILITY & INTEGRATION AUDIT**
                   Brief du propriétaire, 2026-08-22, 28 sections (§0 à §27)
Chapitres        : **17 exécutables** (5 sections sont des règles, pas des chapitres)
Phases           : **24**
Phase courante   : **9 (§13, sécurité) — en attente de confirmation**
Terminées        : **1.1 → 3.1** (6 sur 24). Reconnaissance complète des deux
                   côtés ; commit `b36e082` (v6.3.0), **MIT**, **zéro dépendance
                   déclarée**, 29 322 lignes de prose contre 4 012 de code ;
                   télémétrie **vérifiée dans le code**, une image, trois opt-outs
                   testés ; comparaison **A–X complète** : 9 domaines où GalSen IA est
                   déjà plus fort, 5 où Superpowers l'est, 6 orthogonaux,
                   **1 conflit direct** (cadence autonome vs protocole de phases).
                   **§7 fait** : 14 skills notés, **5 à adopter**, 3 à considérer,
                   6 à laisser. **Aucun candidat en « importer »** — rien ici ne
                   peut importer du markdown. **§9 et §10 faits** : zéro test de
                   comportement d'agent côté GalSen IA (15 règles jamais éprouvées),
                   et `find-polluter.sh` est le **seul** candidat « composant isolé ».
                   **§11 et §12 faits** — une affirmation de la 3.2 corrigée :
                   GalSen IA **a** un relecteur (`coder → reviewer`), il lui manque
                   la **boucle**
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète.

**§27, condition d'arrêt absolue** : cet audit **n'implémente rien**. Aucune
copie, aucune installation, aucune modification de `src/`, des agents, du moteur
créatif, de la génération vidéo, du reference entity engine, du `WorldState`, de
la mémoire, du registre de fournisseurs, du routeur de modèles, des frontières de
sécurité ni de l'auto-réparation. Le VOLET s'arrête au **portillon de décision**
et attend une autorisation explicite.

---

## Le plan

```
Ch. 01  §2  Reconnaissance GalSen IA              → 3 phases
            1.1 accès à la source + agents, skills, commandes, hooks
            1.2 orchestration, mémoire, planification, tâches, auto-réparation
            1.3 tests, débogage, vérification, revue, CI, git, sécurité, ADR

Ch. 02  §1+§3  La source officielle                → 2 phases
            2.1 accès, commit exact ou UNKNOWN, licence, métadonnées
            2.2 skills/, agents/, hooks/, commands/, bootstrap, mise à jour

Ch. 03  §4  Comparaison architecturale, A à X      → 3 phases
            3.1 A–H   agents, skills, plan, spec, TDD, debug, vérif, revue
            3.2 I–P   sous-agents, parallélisme, git, mémoire, contexte,
                      hooks, sécurité, permissions
            3.3 Q–X   observabilité, auto-réparation, autonomie, approbation,
                      reprise, tests, doc, tâches longues
            (9 questions par domaine, dont « reproductible nativement ? »)

Ch. 04  §7  Analyse skill par skill                → 2 phases
            4.1 inventaire réel des skills, jamais une liste supposée
            4.2 skill → équivalent → écart → valeur → coût → recommandation

Ch. 05  §9   Tests                                 → 1 phase (indivisible)
Ch. 06  §10  Débogage                              → 1 phase (indivisible)
Ch. 07  §11  Sous-agents                           → 1 phase (indivisible)
Ch. 08  §12  Contexte et mémoire                   → 1 phase (indivisible)
Ch. 09  §13  Audit de sécurité                     → 1 phase (indivisible)
Ch. 10  §14  Matrice de licences                   → 1 phase (indivisible)
Ch. 11  §15  Dépendances                           → 1 phase (indivisible)
Ch. 12  §16  Télémétrie et vie privée              → 1 phase (indivisible)
Ch. 13  §17  Matrice de duplication                → 1 phase (indivisible)
Ch. 14  §18  Performance et complexité             → 1 phase (indivisible)
Ch. 15  §19  Trois architectures (A, B, C)         → 1 phase (indivisible)
Ch. 16  §20  Portillon de décision                 → 1 phase (indivisible)

Ch. 17  §21–§26  Le rapport                        → 2 phases
            17.1 `docs/research/superpowers-audit.md`, ses 18 points
            17.2 le format final de §26, puis ARRÊT
```

**Total : 24 phases.** Je commence par la 1.1 et je m'arrête après.

---

## Cinq sections ne produisent aucune phase, et c'est délibéré

§0, §5, §6, §8 et §27 ne sont pas des chapitres : ce sont des **contraintes qui
lient chaque phase**. Les compter comme des phases aurait gonflé le plan sans
produire de travail.

- **§0 / §27** — audit d'abord, aucune implémentation, aucun arrêt-condition
  franchi.
- **§5** — une bonne idée ne justifie pas un import. L'ordre de préférence est
  *réimplémenter nativement* avant *importer*.
- **§6** — séparer dépendance de développement et dépendance de production. La
  première peut être acceptable, la seconde exige une décision d'architecture.
- **§8** — la vérification proportionnée à la tâche, sans cérémonie inutile sur
  le trivial.

---

## Ce qui est déjà mesuré, avant la première phase

`raw.githubusercontent.com/obra/superpowers` → **200**.
`api.github.com/repos/obra/superpowers` → **403**.
`github.com/obra/superpowers` → **403**.

Le contenu est donc lisible **fichier par fichier**, mais l'énumération des
dossiers ne l'est pas par l'API. C'est exactement le chemin qui avait servi à
lire les douze licences de l'audit OSS. La phase 1.1 doit d'abord établir un
accès qui donne **l'arborescence et le commit exact** — `add_repo` puis un clone
est la voie prévue pour ça — faute de quoi §1 impose d'écrire `UNKNOWN` pour la
version examinée plutôt que de l'inventer.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Les quatre constats de l'audit OSS** — 4 phases. PR #34 et #35 fusionnées.
2. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. ADR-037 : zéro `INTEGRATE` sur
   douze. `docs/oss-ecosystem/final-report.md`
3. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
4. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases. ADR-030.
5. **Creative Canvas & Cinema Orchestration** — 17 phases. ADR-031.
6. **Research Orchestration Integration** — 18 phases. ADR-032.
7. **Live Context Engine / Call.md** — 27 phases. ADR-033. **PR #31 fusionnée.**
8. **OpenClaw Compatibility & Safe Integration** — 19 phases. ADR-034 :
   **ne pas intégrer**.
9. **DeepSeek Harness Compatibility Audit** — 14 phases. ADR-035 : quatrième
   back-end de codage, **implémentation non autorisée**.
10. **Finalisation** — ADR-036 (Apache-2.0). **PR #32 fusionnée.**

**Le précédent qui compte** : deux audits de compatibilité sur trois se sont
conclus par *ne pas intégrer*, et le troisième par *intégration non autorisée*.
Un audit dont la conclusion est écrite d'avance n'en est pas un — mais un audit
qui conclut `GO` parce que le sujet est populaire non plus.
