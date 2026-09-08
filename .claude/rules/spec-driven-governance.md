# GalSen IA — Spec-driven governance — **ABROGÉ le 04/09/2026**

**Cette règle ne s'applique plus. Décision du propriétaire.**

Ce fichier ne contient plus aucune consigne. Il n'est conservé que parce que
plusieurs documents et docstrings du dépôt le citent par son nom.

---

## Ce qui a été retiré

Tout ce qui interdisait d'implémenter, ou obligeait à s'arrêter pour demander
une autorisation :

- « une amélioration possible n'est pas une exigence » et l'obligation de
  classer en `OPTIONAL SUGGESTION — NOT IMPLEMENTED` tout ce qui n'était pas
  demandé mot pour mot ;
- la liste de ce qui ne pouvait « jamais être ajouté » sans demande explicite
  (fonctionnalités, modèles, agents, API, services, dépendances, couches
  d'architecture…) ;
- « la recherche n'autorise pas l'implémentation » ;
- l'arrêt obligatoire dès qu'un problème technique changeait le périmètre ;
- l'obligation de demander plutôt que de trancher quand une demande est
  ambiguë.

## Pourquoi

Le propriétaire a constaté que cette règle servait à refuser du travail
qu'il avait demandé. Elle avait été écrite pour éviter d'inventer des
fonctionnalités que personne ne voulait ; en pratique elle bloquait aussi ce
qu'il voulait vraiment.

## Ce qui n'a **pas** été retiré, et le reste ailleurs

- Ne jamais inventer une mesure, un résultat de test ou une capacité :
  `.claude/rules/verification.md`. **C'est la règle qui compte encore.**
- Ne pas casser l'existant → `.claude/rules/post-integration-validation.md`
- Sécurité, secrets, permissions → `.claude/rules/security.md`

**Ne pas remettre cette gouvernance sans une demande explicite du
propriétaire.**
