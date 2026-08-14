# Rapport de travaux — GalSen IA

**Période : 2026-08-13 → 2026-08-14.** 19 commits, branche `claude/galsen-ia-phases-ukwz7p`.
Tout ce qui suit est **mesuré** : chaque chiffre vient d'une commande exécutée. Ce qui n'a
pas été mesuré est écrit comme non mesuré.

État de la suite : **3241 tests passent, 8 ignorés, 0 échec.** `ruff` propre.
(Point de départ de la période : 2921 tests.)

---

## 1. En une phrase

La plateforme est passée de « un moteur de connaissance vide et une acquisition
impossible » à « une chaîne d'acquisition complète, sous portillon humain, avec une
première couche de connaissance sénégalaise et wolof réellement acquise et citable ».

Ce qui reste ouvert n'est plus du code.

---

## 2. Ce qui a été construit

### 2.1 L'acquisition de connaissance sous portillon (ADR-021)

**Le problème de départ** : le dépôt refusait d'acquérir quoi que ce soit, sur un
déclencheur qui disait « on construira l'acquisition quand un corpus sénégalais existera ».
C'était **circulaire** — rien ne pouvait produire ce corpus tant que l'acquisition
n'existait pas. Le report était un refus déguisé en mesure.

ADR-021 corrige le déclencheur et autorise la construction, en l'encadrant.

La chaîne, dans l'ordre, chaque étape testée séparément :

| Étape | Ce qu'elle fait | La règle qu'elle tient |
|---|---|---|
| 1. Registre | Rangs `TIER_A`→`TIER_D`, politique d'accès, `enabled` | **Inscrire n'est pas activer** — défaut `false` |
| 2. Enregistrement | Machine à états `DISCOVERED`→`INGESTED` | Un candidat n'est **pas** une connaissance |
| 3. Récupérateur | Agent véridique, `robots.txt`, débit par hôte | Un agent déguisé vide `robots.txt` de son sens |
| 4. Portillon | Décision **avant** la requête, approbation par lot | L'accord porte l'empreinte du lot exact |
| 5. Découverte | Plan de site, fil, index déclaré, semis | Profondeur 1, même domaine, **jamais** d'exploration |
| 6. Métadonnées + langue | Titre, date, éditeur ; détection fr/en/wo/ff | Une date ambiguë rend `unknown` |
| 7. Barrière de confiance | Enveloppe `EXTERNAL` obligatoire | **Seul chemin** vers `PARSED` |
| 8. Qualité | Quasi-doublons + dix contrôles | Seuls trois peuvent refuser |
| 9. Manifeste | Proposition en `DRAFT` | **N'ingère rien** |
| 10. Pilote | `scripts/acquisition_pilot.py`, deux commandes | Le portillon est **entre** les deux |

**Aucune source n'est activée. La chaîne ne peut donc atteindre aucun site.** C'est la
règle qui fonctionne, pas une panne.

### 2.2 Le wolof

- **Orthographe CLAD** (`src/wolof/clad.py`) : alphabet officiel de 27 lettres, décret
  n° 2005-992. Normalisation déterministe et idempotente qui **ne touche aucune lettre** —
  `ë`, `ñ`, `ŋ` traversent toute la chaîne intacts.
- **Corpus réellement acquis** : UD_Wolof-WTB téléchargé, **2107 phrases extraites,
  2105 enregistrements**, 2 doublons écartés et comptés. Texte brut **et** normalisé
  conservés côte à côte.
- **Détection de langue mesurée** : marqueurs dérivés du corpus (fréquence sur 2105
  phrases). Résultat : **0 faux positif sur 2105 phrases** ; par groupes de 3 phrases,
  671/701 correctes, 0 fausse.

### 2.3 Le moteur de connaissance sénégalais

- **14 régions, 45 départements**, tous **dérivés** de geoBoundaries. Le rattachement
  département → région est **calculé** (centroïde surfacique + lancer de rayon), jamais
  déclaré : 45/45 rattachés, 0 approximation.
- **8 jeux de données acquis**, **212 objets sectoriels**, **271 fragments récupérables,
  100 % avec provenance**.
- **6 domaines peuplés sur 16** : géographie, administration, langues, économie,
  institutions publiques, transport.

### 2.4 Le RAG multilingue

`corpus/languages/aliases.yaml` : **16 concepts, 115 termes** (48 fr, 21 wo, 46 en).
L'expansion **ajoute et ne retire jamais**, donc elle ne peut pas faire perdre une
correspondance qui marchait avant. Latence mesurée : **0,1 à 0,5 ms**.

| Question | Résultat |
|---|---|
| « Quelle est la monnaie du Sénégal ? » | ✅ `XOF` |
| « Ban xaalis lañuy jëfandikoo ci Senegaal ? » | ✅ `XOF` |
| « péey Senegaal » | ✅ `Dakar` |
| « askaan ci Senegaal 2020 » | ✅ `16 789 219` |
| « currency of Senegal » | ✅ `XOF` |
| « Quelle est l'histoire du royaume du Cayor ? » | ⬜ `UNKNOWN` |
| « mbéy gerte ci Senegaal » | ⬜ `UNKNOWN` |

**Les deux derniers sont le résultat correct** : ces domaines sont vides, et élargir la
recherche ne les remplit pas.

---

## 3. Ce que j'ai refusé de faire, et pourquoi

C'est la partie la plus importante de ce rapport.

### 3.1 Les 45 départements

La directive du projet annonçait **46 départements**. La source acquise en porte **45**.
Le chiffre suit la source. Ajuster le jeu de données à la valeur attendue aurait été la
fabrication la plus facile de tout ce chantier, et la plus invisible.

### 3.2 « Keur Massar, décret n° 2021-687 »

Cherché dans **les 8 sources acquises** : introuvable. Statut **`UNVERIFIED_CLAIM`** — ni
confirmé, ni infirmé. L'inscrire parce qu'une directive l'affirme fabriquerait un fait
administratif sur un pays réel à partir d'une affirmation sans source.

Ce qui trancherait : le Journal officiel ou l'ANSD — les deux injoignables (§4).

### 3.3 Les dix domaines vides

Histoire, culture, agriculture, pêche, élevage, mines, tourisme, éducation, santé,
juridique. Aucune source joignable ne les porte. J'ai **cherché** les miroirs (trois dépôts
UNESCO, geoBoundaries `gbAuthoritative` et `gbHumanitarian`) : 404 ou refusés.

Ils restent vides, **chacun avec sa raison écrite**. « Rien n'a été acquis » et « le
Sénégal n'a pas d'agriculture » sont deux phrases très différentes.

### 3.4 Le chef-lieu, la population, la superficie des régions

La source ne les porte pas. Un chef-lieu est une **décision administrative**, pas une
propriété géométrique : le déduire d'un centroïde serait une invention. Ils valent
`UNKNOWN`, et les fragments récupérés **nomment leurs lacunes dans leur propre texte**.

### 3.5 Le sérère

Aucune liste de marqueurs n'existe pour lui, **délibérément**. Je ne connais pas ses mots
outils ; en inventer produirait un détecteur qui se trompe avec assurance. Un sérère pris
pour du wolof serait pire qu'un `unknown` honnête.

---

## 4. Le blocage principal, mesuré

**Les neuf domaines institutionnels sénégalais sont injoignables depuis cet
environnement.** Le mandataire réseau refuse la connexion (`CONNECT → 403`) **avant
qu'aucune requête n'atteigne les sites**.

```bash
python scripts/activate_senegal_sources.py
curl -sS "$HTTPS_PROXY/__agentproxy/status"   # section recentRelayFailures
```

Même refus pour la Banque mondiale en direct, l'UNESCO, la FAO, l'OMS, HDX, Wikidata.

**Ce n'est pas un refus des sites**, et le code porte la distinction
(`blocked_by_environment` ≠ `refused_by_site`) parce que les deux demandent des actions
opposées : changer de machine, ou changer de source. Rien n'a été contourné.

Ce qui a pu être acquis l'a été depuis des redistributions publiques joignables (Banque
mondiale via GitHub, ISO, UN/LOCODE, OurAirports), **au rang de ce qui a été récupéré**
(`TIER_C_SECONDARY`) et jamais à celui de l'institution en amont.

---

## 5. Les défauts trouvés en construisant

Neuf, tous corrigés. Ceux qui comptent :

| Défaut | Comment il a été trouvé | Pourquoi il était sérieux |
|---|---|---|
| `retrieval_date` posée nulle part | Premier passage de bout en bout | **Aucun document ne pouvait atteindre `VERIFIED`** — les tests de chaque étage passaient |
| La récupération répondait à côté | Questions de bout en bout | « Histoire du Cayor » rendait un département, avec l'air de répondre |
| La règle du pluriel française amputait le wolof | Test d'alias | « xaalis » devenait « xaali » ; l'alias ne se reconnaissait plus |
| `unknown` traité comme une déclaration de langue | Test « un document sain doit passer » | Tout document sans langue déclarée partait en quarantaine |
| Le fragment suivant s'ouvrait au milieu d'un mot | Test de découpage | « ari » au lieu de « ñaari » |
| `languages.py` affirmait qu'aucun détecteur n'existait | Relecture après l'étape 6 | Vrai la veille, faux depuis |

Le premier mérite d'être souligné : **seul un enchaînement complet pouvait le montrer.**
Les tests unitaires de chaque étage passaient tous.

---

## 6. Ce qui te revient

Cinq actions. Rien d'autre ne bloque.

1. **Lancer le pilote depuis une machine sans ce mandataire.** C'est le seul moyen
   d'atteindre les institutions sénégalaises.
   ```bash
   python scripts/activate_senegal_sources.py     # doit dire « reachable »
   # activer la source dont tu as lu les conditions, dans corpus/sources/senegal.yaml
   python scripts/acquisition_pilot.py plan
   python scripts/acquisition_pilot.py run --approval <id>
   ```
   **Lire les conditions d'utilisation reste à toi** : `robots.txt` dit ce qu'un agent peut
   atteindre, pas ce qu'on a le droit d'en faire.

2. **`ollama serve`** — génération et récupération sémantique toujours non mesurées.

3. **`git push origin v0.1.0`** depuis un clone normal — seul test rouge de la CI.

4. **Trancher trois décisions** : ADR-020 (option B recommandée), la date de retrait de
   `/cloud/*`, la cible de déploiement.

5. **Faire relire les termes wolof par un locuteur** (`corpus/languages/aliases.yaml` et
   `markers.yaml`). Ils sont marqués `reviewed: false` et chaque verdict porte la réserve.

---

## 7. Verdict

Ce qui pouvait être bâti et vérifié sans réseau ni décision l'a été. **3241 tests passent,
aucun affaibli, aucun supprimé.** Chaque refus est nommé, chaque lacune est publiée, et
aucune affirmation sur le Sénégal n'a été écrite de mémoire.

Le reste attend une machine avec du réseau, un modèle qui tourne, et trois arbitrages.
