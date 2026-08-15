"""
Greffon d'exemple : la plus petite chose honnête qu'un greffon puisse faire.

Il écrit un objet JSON sur la sortie standard et s'arrête. Aucun réseau, aucun
fichier, aucune donnée de personne — exactement ce que son manifeste déclare.

La sortie d'un greffon est traitée par la plateforme comme une **donnée avec une
origine**, jamais comme une instruction. Ce fichier peut écrire ce qu'il veut :
cela restera une chaîne.
"""

import json

print(json.dumps({
    "plugin": "exemple-meteo",
    "says": "Ceci est une sortie de greffon, donc une donnée.",
    "does": ["écrire du JSON"],
    "does_not": ["appeler le réseau", "lire un fichier", "toucher une donnée privée"],
}, ensure_ascii=False))
