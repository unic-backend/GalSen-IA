**En cours** : rien — priorité #7 en pause à un point vérifié.
**Terminé** : **Conseil Agricole — première slice verticale de la priorité #7**.
Outil `AgriAdviceTool` réparé (API synchrone `select_model_for_task()`+`generate()`,
bug de coroutine asynchrone + méthode inexistante), endpoint `POST /agri/advice`
dans `src/api/server.py` (fr/wo, options model_id/max_tokens, RBAC `model:generate`,
validations 422/401, succès 200), **17 tests** dans `tests/test_agri_advice.py`.
Suite complète : **914 passed, 5 failed** (les 5 échecs sont les mêmes pré-existants
de `test_model_engine.py` : Ollama actif → LocalProvider READY, catalogue 9 < 10).
Génération réelle vérifiée via Ollama (qwen2.5-coder:14b).
**Prochaine étape** : phase suivante de la priorité #7 — page « Conseil Agricole »
dans le dashboard web (`src/frontend/`, déjà monté sur `/admin`) qui appelle
`POST /agri/advice` ; ou clôturer la feature côté API et passer au backlog
(rotation des logs, modernisation du catalogue, migration des `test_*.py` legacy).
**Bloqué** : rien. NB : la suppression des sondes temporaires (`probe_agri.py`,
`tests/probe_test.py`) est refusée par le système de permissions malgré
l'autorisation de l'utilisateur — à réessayer. La localisation du travail
« application mobile » reste à éclaircir avec l'utilisateur.
