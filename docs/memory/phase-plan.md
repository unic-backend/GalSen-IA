# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 15 terminé
**Phase courante** : —
**Terminées** : toutes (12 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 15 — API Gateway : terminé   → docs/architecture/gateway.md
  La passerelle n'est pas un service séparé : c'est l'application FastAPI, et
  ses contrôles sont des dépendances déclarées route par route — un dispositif
  qui tombe en panne en silence. Les 63 routes sont désormais énumérées et
  verrouillées par des tests (authentification, limiteur, ordre des
  intergiciels).
  Deux défauts réels corrigés : quatre routes recopiaient le texte de
  l'exception dans leur 500 (hôte interne, chemin de fichier) ; aucun moyen
  n'existait d'annoncer qu'une route allait disparaître.
  ADR-011 : pas de préfixe `/v1` (une promesse de stabilité qu'un prototype ne
  tient pas), dépréciation annoncée par les en-têtes RFC 8594.
  Absents et non simulés : coupe-circuit, reprises, mesure de disponibilité,
  TLS applicatif, et les instances de gouvernance que le projet n'a pas.
```

**Restants** : 17 à 25 — soit 9 VOLETs, dont 5 portent un sujet déjà traité avec
un contenu différent (18, 19, 20, 21, 24) et 17 qui recoupe 13 à 46 %. Le VOLET
01 n'a jamais eu de plan de phases formel.

**Prochaine action** : par ordre numérique, **VOLET 17 — Agent Framework Engine**.
