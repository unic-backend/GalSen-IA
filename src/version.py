"""
Version de la plateforme GalSen IA — source unique.

Elle vivait à deux endroits qui avaient divergé : `0.1.0` dans l'application
FastAPI, `0.2.0` dans l'étiquette de l'image Docker. Une version qui dépend de
l'endroit où on la lit ne permet plus de dire ce qui tourne en production.

Tout ce qui a besoin du numéro le lit ici. Le Dockerfile ne pouvant pas importer
du Python, il déclare la même valeur en argument de construction, et
`tests/test_version.py` échoue si les deux s'écartent.

Politique de versionnage → `docs/roadmap/roadmap.md`, section « Versioning ».
"""

__version__ = "0.1.0"

# Type de version au sens du VOLET_04 chapitre 03 : prototype, alpha, beta,
# stable ou lts. La plateforme n'a jamais été déployée, n'a pas d'utilisateur et
# sa fonctionnalité principale répond 503 faute de fournisseur configuré : c'est
# un prototype, et l'annoncer autrement serait une promesse que rien ne tient.
__release_type__ = "prototype"
