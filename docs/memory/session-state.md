# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session
**2026-08-18 — VOLET créatif repris : C13 et C14 livrés (35 phases sur 38).**
Programme en cours : **Universal Creative Intelligence, directive V4** →
`docs/creative/phase-plan.md`. Il était à l'arrêt après C12, non par blocage
mais par fin de quota du compte précédent.

C13 (§24–§26) : registre de langues **en données** (`corpus/creative/languages.yaml`,
19 langues), alternance codique par segment. Défaut corrigé : la couche vocale
validait contre les 4 langues des sous-titres — sérère et lingala, qui sont les
tests d'or 5 et 6 de §63, étaient **refusés**.
C14 (§27–§33) : échelle observation → validation, base de connaissance avec
frontière privé/global, boucle d'acquisition. La fréquence plafonne à
`CORROBORATED` ; `VALIDATED` exige un humain nommé, `OFFICIAL` une autorité
extérieure. Aucun entraînement sur les conversations, et c'est vérifiable.

**Puis phase 15.1** (C15, §36) : `src/creative/routing.py` — appariement par
capacités. Ferme ce que C04 laissait ouvert : `select()` prenait le premier
inscrit. Règle centrale : **un classement n'a lieu que si tous les candidats
portent le chiffre**, sinon `UNRANKED`. Et `UNKNOWN` n'est pas `UNMET`.

**Cadence : une phase par tour** depuis le 2026-08-18 (budget de contexte).

**Puis phase 15.2** (§43) : `src/creative/pipelines.py` — les deux architectures
planifiées, **aucune recommandée**. L'étape audio de A est satisfaite *sans
fournisseur* quand l'enregistrement est gardé ; la traiter autrement pousserait
vers B là où B est le mauvais choix. Mesuré sur les 9 fournisseurs déclarés :
les deux `BLOCKED`, sur des étapes différentes. **C15 est terminé.**

**Puis phase 16.1** (§52) : `src/creative/resources.py`. Règle unique — **une
ressource non mesurée vaut `None`, jamais `0`** : `0 Gio` conclut, `None`
interdit de conclure. Mesuré ici : 4 cœurs, 15,7 Gio de RAM, 27,5 Gio libres,
GPU absent (`torch` manquant) donc **VRAM `NOT_MEASURED`**. Rien ne se décharge
en silence : `admit()` nomme ce qu'il faudrait libérer, l'appelant décide.

**Le plan annonçait 38 phases : c'était une erreur d'addition, il y en a 43.**
Recompté et corrigé le 2026-08-18. 38 faites, 5 restantes.

**Puis phase 16.2** (§53–§55) — **C16 terminé**. `src/creative/jobs.py` se
raccorde à `RenderQueue` (`src/media/queue/jobs.py`) : même identité, état lu
dans la file, jamais recopié. Il ajoute ce qu'elle ne peut pas savoir — le
fournisseur et **les références qui ont conditionné l'artefact**, sans quoi la
révocation d'ADR-025 ne peut atteindre aucune vidéo. `src/creative/cache.py` :
toute lecture rend la fraîcheur avec la valeur, il n'existe **pas** de méthode
rendant la valeur seule, et rien n'expire au temps.

**Puis phase 17.1** (§70, §72) : **4 routes `/creative`, pas 15.** Une route
n'existe que si une fonction réelle la sert ; les 11 autres préfixes proposés
sont rendus par `/creative/surface` — soit la route existante qui les sert déjà,
soit ce qui manque. `/creative/readiness` **calcule** l'état à l'appel :
`ORCHESTRATION READY — GENERATION BLOCKED (NO GPU, NO PROVIDER CLEARED)`.
Routes publiées : 136 → **144**, re-mesurées.

**Puis phase 17.2** (§62–§64) : `src/creative/golden.py` — les 25 scénarios
exécutés contre le code vivant. **Deux verdicts, jamais trois** : `VERIFIED`
(19) et `BLOCKED` (6 : 1, 3, 9, 10, 15, 18). Un `BLOCKED` **est** une assertion
— « la capacité manque et la plateforme le rapporte au lieu d'inventer » —, pas
un test sauté. Le jeu complet tourne en < 1 s, sans modèle ni réseau (§62).
§64 : les 15 langues de validation sont toutes nommables, **0 comprise, 0
parlée**, et aucune architecture par langue.

**Puis phase 17.3** (§65, §66) — **C17 terminé**. `src/creative/mvp.py` +
`scripts/creative_slice.py` : les 13 étapes parcourues, **7 ont réellement eu
lieu**, 2 `BLOCKED`, 2 `NOT_MEASURABLE`, 2 `NOT_REACHED`. `produced_video` est
`False` et `final_video` reste **dans le total** — le retirer ferait paraître la
chaîne complète. Toute l'orchestration (6 premières étapes) aboutit ; c'est la
génération qui manque.

**Prochaine étape** : **C18 — rapport final (§73, §76)**, 1 phase. **Ce sera la
dernière : 42 faites sur 43.**

**Bloqué** : rien côté code. Sur cette machine : pas de GPU, pas de `torch`,
`huggingface.co` injoignable → génération, diarisation, ASR et lip-sync restent
`BLOCKED`, 8 licences de poids `UNKNOWN` (`docs/creative/feasibility.md`).
Et `git push origin v0.1.0`, seul échec de CI, qui appartient au mainteneur.

---

### Sessions précédentes
**2026-08-18 — ADR-029 tranchée (option C) : la plateforme a des comptes, avec mots de passe.**
Routes `/auth/register|login|refresh` montées, `/auth/me` accepte jeton **ou** clé.
Trois défauts corrigés avant montage, dont un **secret de signature en dur dans le dépôt**
qui laissait forger un jeton d'administrateur. ADR-010 amendée, pas contredite.
Fusionnée dans `main` par la PR #26.

**2026-08-17 — Coding Engine et interopérabilité portés depuis la seconde ligne de développement.**
`src/coding_engine/` (OpenHands, Aider, SWE-agent derrière une abstraction native, ADR-028),
`src/code_edit/` (blocs d'édition) et `src/interop/` (OpenGAP, ADR-023). Aucun code des
projets externes recopié, aucune dépendance ajoutée, exécution passée par `src/sandbox`.
Fusionnée dans `main` par la PR #25.

**2026-08-16 — Le moteur média universel est terminé** — 20 VOLETs, 32 phases sur 32.
Rapport final → `docs/media/final-report.md`. `src/media/` : 26 modules, 483 tests.
État calculé : 10 `READY`, 6 `BLOCKED`, 1 `ABSENT` (aucune synthèse vocale n'existe
dans ce dépôt — trouvé en parcourant la chaîne, jamais rangé parmi les dépendances
manquantes).

**Bloqué / à surveiller (hérité)**
- `ffmpeg` complet, `ffprobe`, `torch`, GPU et `whisper` absents de cet environnement.
- Licence de WanGP non inspectée.
- Mandataire réseau : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
